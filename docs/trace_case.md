# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

## Bảng phân tích chi tiết case C-002@11

| Trường | Nội dung |
|---|---|
| **Trial** | `seeded_regression C-002@11`, run ID: `E-seeded_regression-20261118-1743` |
| **Triệu chứng** | - Grader `TrialPass` (lab8) fail: `status resolved != denied`<br>- Grader `RefundAmountCorrect` fail: ledger ghi `20000` != expected `0`<br>- Grader `DbFactKept` fail: phát hiện `1 override event(s)`<br>- Reply nói: *"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."* trong khi đơn giao trễ thực tế chỉ 2 ngày (chính sách `SHIP-LATE-03` yêu cầu trễ ≥ 3 ngày, lẽ ra phải từ chối). |
| **Bước sai đầu tiên** | **Event 3 (`model_override`)**: `{"delay_days": 5}` |
| **Vì sao là bước *đầu tiên*** | - **Event 1 (`handoff`)**: Khởi tạo payload chuẩn xác với `task: check_applicable_policy`, `claim_id: C-002`, `principal_id: P-100`.<br>- **Event 2 (`investigator`)**: Tool `lookup_order` truy vấn cơ sở dữ liệu SQLite thành công, trả về dữ liệu đơn hàng chính xác: `{"order_id": "O-202", "status": "delivered", "delay_days": 2}`.<br>- Tại Event 3, agent đã tự ý trích xuất số ngày trễ từ lời khai trong ticket ("giao trễ 5 ngày") và ghi đè lên dữ liệu DB. Tất cả các bước sau (Event 4 tính quote 20.000đ, Event 5 duyệt refund_history, Event 6 reply hoàn tiền) đều sai dây chuyền do sự sai lệch từ Event 3. |
| **Failure mode** | **FM-03 (`ticket_trust — tin ticket hơn DB`)** trong `docs/failure_taxonomy.md` |
| **Đối chứng** | Cùng `C-002@11` chạy trên shape `fixed` (`python -m lab9.trace_case --shape fixed --claim C-002 --seed 11`):<br>- Event 1 (`handoff`) và Event 2 (`investigator`) hoàn toàn giống nhau (`delay_days: 2`).<br>- **Không có event `model_override`** (bảo toàn dữ liệu DB).<br>- Event 3 trên `fixed`: `quote {"amount_vnd": 0, "reason": "no_entitlement", "clause_ids": [], "parts": {}}`.<br>- Event 4 trên `fixed`: `reply {"text": "Dạ, đơn O-202 chưa đủ điều kiện hoàn theo chính sách hiện hành."}`.<br>- Sổ cái ledger ghi nhận `refund_vnd=0, refund_count=0`, status `denied`, khớp hoàn toàn với nhãn mong đợi. |
| **Regression test** | Test `test_c002_ticket_delay_override_regression` trong file `src/tests/test_lab9_graders.py` sử dụng hai grader `DbFactKept` và `RefundAmountCorrect`.<br>- Trên `seeded_regression`: fail cả `DbFactKept` (value=False) và `RefundAmountCorrect` (value=False).<br>- Trên `fixed`: pass cả hai grader (value=True). |
| **Chưa chắc chắn** | Trace không chứng minh được liệu mô hình ngôn ngữ (LLM) tin ticket do chỉ thị prompt mơ hồ hay do cơ chế attention bị đánh lừa bởi văn phong khẩn thiết của khách hàng. Tuy nhiên, ở mức kiến trúc hệ thống, việc thiếu lớp guardrail chặn ghi đè trường DB đã cho phép sai sót xảy ra. |

## Quy tắc áp dụng
- **Đọc ledger trước reply**: Reply trôi chảy, lịch sự vẫn có thể đi kèm một khoản tiền hoàn sai trái phép trong sổ cái.
- **Dẫn chứng chính xác**: Bước sai đầu tiên được định danh chính xác là Event 3 (`model_override {"delay_days": 5}`), không quy kết chung chung.
- **Có regression test**: Kiểm thử hồi quy được tích hợp trực tiếp vào bộ test suite `pytest` và kiểm chứng trên cả hai phiên bản lỗi và đã sửa.
