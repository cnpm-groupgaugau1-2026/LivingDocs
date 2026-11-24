# Grounding Evidence Extraction & Context Attachment Engine

<http://localhost:3000/drift-demo>

**Grounding Evidence Extraction & Context Attachment Engine (Sub-feature 5.3)** đóng vai trò như một "điều tra viên thu thập vật chứng": sau khi 5.1 tìm ra lỗi và 5.2 chấm điểm mức độ nguy hiểm, 5.3 sẽ **cắt đúng từng dòng bằng chứng từ Tài liệu Markdown và cây mã nguồn AST**, giải thích chính xác nút lệnh nào đang gây lỗi, rồi đóng gói thành một bộ ngữ cảnh chuẩn (**AI Grounding Payload**) để bước AI tự động sửa tài liệu ở giai đoạn sau không bao giờ bịa đặt sai sự thật.

Trên giao diện, mỗi thẻ lỗi sẽ được gắn 1 trong **3 trạng thái neo bằng chứng**:

- **Neo kép Doc ↔ AST (**`verified_dual_anchor`** — Xanh lá):** Hàm có mặt ở cả tài liệu và mã nguồn; hệ thống chỉ điểm chính xác tới từng dòng bên trong thân hàm (ví dụ dòng `raise` lỗi hoặc dòng gọi hàm ghi database).
- **Gợi ý hàm đổi tên AST (**`candidate_match_found`** — Vàng):** Tên hàm cũ trong tài liệu không còn, nhưng AST tìm thấy hàm mới có tên gần giống và đính kèm luôn code của hàm mới đó làm bằng chứng đối chiếu.
- **Chỉ neo ở Tài liệu (**`doc_only_missing_target`** — Đỏ):** Tệp hoặc hàm đã bị xóa hẳn khỏi mã nguồn; hệ thống đính kèm dòng tài liệu bị sai kèm danh sách các hàm hợp lệ duy nhất đang tồn tại trong module để khóa chặt phạm vi sửa của AI.

**Bước 1 — Kiểm tra tổng quan tỷ lệ neo bằng chứng ở Kịch bản 1 (**`1. Tổng hợp cả 3 loại Drift`**):**

- Nhìn lên góc trên bên phải của thẻ thống kê (`5.3 Grounding Anchors`).

- **Kết quả :** Hệ thống báo `Đã neo: 6/6 • Neo kép AST: 5` (5 lỗi của hàm `process_payment` neo được cả hai đầu Tài liệu ↔ AST, còn 1 lỗi của hàm đã xóa `legacy_reconcile_invoice` chỉ neo ở phía Tài liệu)

**Bước 2 — Kiểm tra khả năng "soi tận dòng lệnh AST" trên từng thẻ lỗi:**

- Kéo xuống **thẻ số 1 (**`CRITICAL • 89/100`** — Mâu thuẫn hành vi **`read-only`**)**, nhìn vào khung tối màu **Bằng chứng AST** bên phải của phần `5.3 Grounding Evidence`.

- **Kết quả :** Dù cả hàm `process_payment` dài 5 dòng, hệ thống vẫn khoanh sáng riêng **dòng 4** (`db.save_transaction(...)`) kèm nhãn `Node Proof: ast.Call(func='db.save_transaction', lineno=4)` và dòng chú thích giải thích ngay bên dưới.
- Kéo tiếp xuống **thẻ số 4 (**`HIGH • 69/100`** — Thiếu mô tả ngoại lệ)**: khung bằng chứng AST tự động đổi sang khoanh sáng **dòng 3** (`raise ValueError(...)`) với `Node Proof: ast.Raise(exc='ValueError', lineno=3)`.

**Bước 3 — Kiểm tra bằng chứng cho hàm bị xóa hẳn (Thẻ số 5 của Kịch bản 1):**

- Kéo xuống **thẻ số 5 (**`MEDIUM • 59/100`** — **`legacy_reconcile_invoice`**)**.

- **Kết quả :** Thẻ mang nhãn màu đỏ `Chỉ neo ở Tài liệu`, khung bên phải báo *Không tìm thấy nút AST tương ứng* và liệt kê rõ ký hiệu hợp lệ duy nhất đang có trong tệp là `process_payment`.

**Bước 4 — Kiểm tra bằng chứng gợi ý hàm đổi tên ở Kịch bản 2 (**`2. Referential Drift`**):**

- Bấm sang nút **2. Referential Drift** ở hàng kịch bản phía trên, sau đó xem **thẻ số 1 (**`verify_access_token`**)**.

- **Kết quả :** Thẻ hiển thị nhãn màu vàng `Gợi ý hàm đổi tên AST`, khung bên phải tự động kéo đoạn code của hàm mới `validate_access_token` vào làm bằng chứng kèm ghi chú: *↳ Ứng viên đổi tên gần nhất trong AST: *`validate_access_token`.

**Bước 5 — Kiểm tra gói ngữ cảnh chống ảo giác (**`AI Grounding Payload`**):**

- Trên bất kỳ thẻ lỗi nào, bấm vào dòng chữ `Xem gói ngữ cảnh chống ảo giác cho AI Auto-Repair (AI Grounding Payload)` (hoặc bấm nút `Sao chép AI Grounding Payload` ở góc phải khung 5.3).

- **Kết quả đúng:** Khung mở rộng hiển thị đầy đủ 5 phần chuẩn hóa (`DRIFT_SUMMARY`, `DOC_ANCHOR`, `AST_ANCHOR`, `VERIFIED_AST_FACTS`, và `REPAIR_CONSTRAINT` cấm AI tự bịa thêm tham số/hàm ngoài danh sách đã kiểm chứng).
