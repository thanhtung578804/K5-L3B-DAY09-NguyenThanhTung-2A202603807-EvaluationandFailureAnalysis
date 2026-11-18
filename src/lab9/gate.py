"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


import math


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate."""
    problems = []

    # 1. Any metric value in pr["metrics"] that is NaN or inf
    for k, v in pr.get("metrics", {}).items():
        if isinstance(v, (int, float)) and (math.isnan(v) or math.isinf(v)):
            problems.append(f"metric {k} is NaN or inf ({v})")

    # 2. len(pr["rows"]) != manifest items x len(manifest seeds) (dropped / duplicated rows)
    manifest = pr.get("manifest", {})
    expected_rows = manifest.get("items", 0) * len(manifest.get("seeds", []))
    if len(pr.get("rows", [])) != expected_rows:
        problems.append(f"row count {len(pr.get('rows', []))} != expected {expected_rows}")

    # Check for duplicate (item_id, seed) rows
    pr_keys = [(r.get("item_id"), r.get("seed")) for r in pr.get("rows", [])]
    if len(pr_keys) != len(set(pr_keys)):
        problems.append("duplicate (item_id, seed) rows detected in PR")

    # 3. The (item_id, seed) set of PR differs from the baseline's
    base_keys = {(r.get("item_id"), r.get("seed")) for r in base.get("rows", [])}
    if set(pr_keys) != base_keys:
        problems.append("PR (item_id, seed) set differs from baseline")

    # 4. pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is None
    if pr.get("evaluator_failures"):
        problems.append(f"evaluator_failures non-empty: {len(pr['evaluator_failures'])} failure(s)")

    spec_metrics = [m["id"] for m in spec.get("metrics", [])]
    for r in pr.get("rows", []):
        for mid in spec_metrics:
            if mid in r and r[mid] is None:
                problems.append(f"row {r.get('item_id')}@{r.get('seed')} has None for graded metric {mid}")
                break
        if problems and problems[-1].startswith("row ") and "has None for graded metric" in problems[-1]:
            break

    # 5. An item's slice tags in PR rows differ from the baseline's
    base_item_slices = {r["item_id"]: set(r.get("slices") or []) for r in base.get("rows", [])}
    for r in pr.get("rows", []):
        iid = r.get("item_id")
        if iid in base_item_slices and set(r.get("slices") or []) != base_item_slices[iid]:
            problems.append(f"slice tags for item {iid} modified in PR")
            break

    # 6. base_spec given and a threshold in spec is LOOSER than in base_spec for the same eval-set version
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        spec_m_by_id = {m["id"]: m for m in spec.get("metrics", [])}
        for bm in base_spec.get("metrics", []):
            mid = bm["id"]
            if mid not in spec_m_by_id:
                problems.append(f"metric {mid} disappeared from spec")
                continue
            sm = spec_m_by_id[mid]
            if bm.get("blocking") and not sm.get("blocking"):
                problems.append(f"blocking metric {mid} became non-blocking")
            b_th = bm.get("threshold", {})
            s_th = sm.get("threshold", {})
            if "max" in b_th and ("max" not in s_th or s_th["max"] > b_th["max"]):
                problems.append(f"threshold max for {mid} loosened: {s_th.get('max')} > {b_th['max']}")
            if "min" in b_th and ("min" not in s_th or s_th["min"] < b_th["min"]):
                problems.append(f"threshold min for {mid} loosened: {s_th.get('min')} < {b_th['min']}")
            if b_th.get("no_significant_drop") and not s_th.get("no_significant_drop"):
                problems.append(f"no_significant_drop dropped for {mid}")
            if "max_increase" in b_th and ("max_increase" not in s_th or s_th["max_increase"] > b_th["max_increase"]):
                problems.append(f"threshold max_increase for {mid} loosened: {s_th.get('max_increase')} > {b_th['max_increase']}")

        spec_slices_by_name = {s["name"]: s for s in spec.get("slices", [])}
        for bs in base_spec.get("slices", []):
            sname = bs["name"]
            if sname not in spec_slices_by_name:
                problems.append(f"slice {sname} disappeared from spec")
                continue
            ss = spec_slices_by_name[sname]
            if bs.get("blocking") and not ss.get("blocking"):
                problems.append(f"blocking slice {sname} became non-blocking")
            if "min" in bs and ("min" not in ss or ss["min"] < bs["min"]):
                problems.append(f"slice {sname} min loosened: {ss.get('min')} < {bs['min']}")
            if bs.get("no_significant_drop") and not ss.get("no_significant_drop"):
                problems.append(f"slice {sname} no_significant_drop dropped")

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice."""
    blocked, lines = [], []
    bs_config = spec.get("bootstrap", {})
    for s in spec.get("slices", []):
        name = s["name"]
        mid = s["metric"]
        blocking = s.get("blocking", False)
        th_min = s.get("min")
        no_drop = s.get("no_significant_drop", False)

        pr_items = per_item(pr, mid, slice_name=name)
        val = (sum(pr_items.values()) / len(pr_items)) if pr_items else None
        verdict = "ok"
        note = ""
        if val is None:
            verdict = "missing"
        elif th_min is not None and val < th_min:
            verdict = "fail"

        if no_drop and pr_items:
            base_items = per_item(base, mid, slice_name=name)
            keys = sorted(set(pr_items) & set(base_items))
            if keys:
                d, lo, hi = stats.paired_bootstrap(
                    [pr_items[k] for k in keys],
                    [base_items[k] for k in keys],
                    n_resamples=bs_config.get("n_resamples", 1000),
                    rng=bs_config.get("rng", 2027),
                )
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"

        sid = f"slice:{name}/{mid}"
        if verdict != "ok" and blocking:
            blocked.append(sid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if blocking else "warn")
        th_desc = json.dumps({k: v for k, v in s.items() if k not in ("name", "metric", "blocking")})
        val_str = f"{val:.4f}" if val is not None else "None"
        lines.append(f"  {sid:<22} {val_str:<8} {th_desc:<40} {note:<28} {label}")

    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
