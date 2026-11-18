# Judge audit & Calibration Report

Lệnh thực hiện hiệu chuẩn và kiểm toán:
```bash
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
```

## 1. Kết quả hiệu chuẩn (Calibration Results)

| Tiêu chí | n | κ (Cohen's Kappa) | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| **tone_ok** | 100 | **0.757** | **0.857** | **0.800** | **ĐẠT** (κ=0.757≥0.6, P=0.857≥0.8, R=0.8≥0.7) | **DÙNG** |
| **helpful** | 100 | **0.375** | **1.000** | **0.300** | **KHÔNG ĐẠT** (κ=0.375 < 0.6, R=0.300 < 0.7) | **LOẠI** |

- **tone_ok**: Ma trận nhầm lẫn `{"tp": 24, "fp": 4, "fn": 6, "tn": 66}`. Tỉ lệ lỗi quan sát $P_{obs} = 0.28$, sau hiệu chỉnh Rogan-Gladen đạt $P_{corr} = 0.30$. Chỉ số thỏa thuận liên định lượng κ = 0.757 nằm ở mức đáng tin cậy cao (substantial agreement).
- **helpful**: Ma trận nhầm lẫn `{"tp": 9, "fp": 0, "fn": 21, "tn": 70}`. Tỉ lệ lỗi quan sát chỉ là $0.09$, nhưng tỉ lệ lỗi thực tế sau hiệu chỉnh Rogan-Gladen là $0.30$. Judge bỏ lọt tới 21 trường hợp phản hồi không hữu ích (False Negative = 21, chiếm tới 70% tổng số mẫu lỗi người gắn nhãn).

---

## 2. Kiểm toán thủ công ≥5 case bất đồng (Audit Cases)

| # | Case ID | Nội dung phản hồi (Reply) | Judge nói | Người nói | Ai đúng? | Phân tích & Hành động sửa Rubric |
|---|---|---|---|---|---|---|
| 1 | `H-008` (tone) | *"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."* | PASS | FAIL | **Người đúng** | Xưng hô "anh - em", dùng từ suồng sã "nha", "check" không đạt tiêu chuẩn chuyên nghiệp của dịch vụ khách hàng B2C LogiX (chuẩn là "Dạ, LogiX... anh/chị"). **Sửa rubric**: Thêm tiêu chí cấm xưng hô thân mật tự phát, bắt buộc chuẩn đại từ "LogiX" và "quý khách/anh chị". |
| 2 | `H-017` (tone) | *"Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha."* | PASS | FAIL | **Người đúng** | Dùng từ "bạn ơi", "rồi nha" mang tính chat cá nhân, thiếu tính trang trọng của thông báo tài chính. **Sửa rubric**: Đưa ví dụ tiêu cực (negative few-shot) về việc dùng trợ từ cuối câu thiếu trang trọng ("nha", "nhé", "nghen") vào prompt của judge. |
| 3 | `H-029` (tone) | *"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."* | PASS | FAIL | **Người đúng** | Câu cuối *"không cần nhắn thêm"* có sắc thái cộc lốc, gắt gỏng, thiếu tôn trọng khách hàng. Judge bị đánh lừa bởi từ "Dạ, vui lòng chờ" ở đầu câu. **Sửa rubric**: Hướng dẫn judge chú ý sắc thái kết thúc câu và thái độ phục vụ khách hàng. |
| 4 | `H-042` (tone) | *"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."* | FAIL | PASS | **Người đúng** | Phản hồi đầy đủ, lịch sự, rõ ràng thời hạn hoàn tiền về tài khoản. Judge khắt khe quá mức (báo nhầm FP) có thể do diễn đạt ngắn gọn. **Sửa rubric**: Làm rõ trong rubric rằng câu trả lời ngắn gọn súc tích nhưng đầy đủ kính ngữ ("Dạ... ạ") là PASS. |
| 5 | `HL-015` (helpful) | *"Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ."* | PASS | FAIL | **Người đúng** | Khách hàng hỏi lý do tại sao đơn bị giao trễ và chính sách bồi thường, nhưng phản hồi chỉ thông báo số tiền mà không giải thích điều khoản áp dụng. Judge chỉ thấy có số tiền hoàn là cho PASS. **Sửa rubric**: Tiêu chuẩn helpful phải đối chiếu câu hỏi của ticket với nội dung giải đáp, không chỉ kiểm tra câu có đề cập tiền hay không. |
| 6 | `HL-016` (helpful) | *"Dạ, LogiX thành thật xin lỗi anh/chị vì sự bất tiện này và rất trân trọng sự kiên nhẫn của anh/chị..."* | PASS | FAIL | **Người đúng** | Phản hồi xin lỗi rất văn vẻ, trôi chảy nhưng không đưa ra bất kỳ hành động giải quyết cụ thể nào cho khiếu nại (không tra cứu, không hoàn tiền, không hướng dẫn tiếp theo). Judge bị ảo giác bởi văn phong lịch sự mà đánh giá sai tính hữu ích. |

---

## 3. Kết luận & Quyết định

1. **Tiêu chí bị loại**:
   - Tiêu chí `helpful` **bị loại bỏ hoàn toàn** khỏi quy trình đánh giá và cổng CI gate.
   - **Lý do**: Với κ = 0.375 và Recall = 0.300, judge này bỏ lọt tới 70% lỗi phản hồi vô bổ (`fn = 21` trên tổng số 30 lỗi do người đánh dấu). Nếu đưa vào gate, các bản cập nhật làm giảm trải nghiệm người dùng nghiêm trọng vẫn sẽ lọt qua (False sense of security).
2. **Tiêu chí được chấp thuận**:
   - Tiêu chí `tone_ok` đạt chuẩn hiệu chuẩn (κ = 0.757, P = 0.857, R = 0.800) và có thể sử dụng cho mục đích theo dõi (monitoring) hoặc gate phi chặn (non-blocking warning).
3. **Rủi ro còn lại**:
   - Tập dữ liệu hiệu chuẩn là replay tĩnh được chuẩn bị sẵn, chưa phản ánh đầy đủ phân phối ngôn ngữ đa dạng và các trường hợp edge case của người dùng thực tế. Cần tiếp tục thu thập nhãn con người độc lập (held-out set thật) trong các giai đoạn phát triển tiếp theo.
