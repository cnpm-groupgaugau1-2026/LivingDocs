# Multi\-Category Drift Classifier \(Referential, Signature, Semantic\)

<http://localhost:3000/drift-demo>

**Multi-Category Drift Classifier** là công cụ tự động đối chiếu **tài liệu hướng dẫn (Markdown)** với **mã nguồn thực tế (Code)** để phát hiện những chỗ code đã thay đổi nhưng tài liệu chưa được cập nhật theo.

Thay vì báo lỗi chung chung, tính năng này phân loại các điểm lệch thành **3 nhóm dễ hiểu**:

1. **Referential Drift (Sai tham chiếu — Màu đỏ):** Tài liệu nhắc tới một tệp hoặc một hàm **không còn tồn tại** trong code (do đã bị xóa hoặc đổi tên).
2. **Signature Drift (Sai chữ ký hàm — Màu vàng):** Tên hàm vẫn đúng, nhưng **đầu vào hoặc đầu ra bị lệch** (ví dụ: code thêm tham số mới, đổi kiểu dữ liệu từ `int` sang `str`, đổi giá trị mặc định, hoặc đổi kiểu trả về).
3. **Semantic Drift (Sai hành vi — Màu xanh):** Tên hàm và tham số khớp nhau 100%, nhưng **cách hàm chạy bên trong lại mâu thuẫn với lời mô tả** (ví dụ: tài liệu ghi hàm *chỉ đọc dữ liệu*, nhưng bên trong code lại gọi lệnh *xóa hoặc lưu database*, hoặc tự ý ném ra lỗi mà tài liệu không nhắc tới).

Bước 1 :Kiểm tra phát hiện cả 3 loại lỗi cùng lúc

**Bước 1 — Kiểm tra kịch bản tổng hợp cả 3 loại lỗi:**

- **Thao tác:** Mở `http://localhost:3000/drift-demo` và bấm nút **1. Tổng hợp cả 3 loại Drift**.
- **Tác dụng:** Kiểm tra xem hệ thống có bắt được cùng lúc nhiều loại sai lệch trên một tệp hay không.
- **Kết quả :** Thanh biểu đồ hiện đủ 3 màu, 4 ô thống kê báo **6 – 1 – 3 – 2** (tổng 6 lỗi gồm 1 Referential, 3 Signature, 2 Semantic) và bên dưới liệt kê đủ 6 thẻ.

**Bước 2 — Kiểm tra tính năng bấm thẻ để soi dòng lỗi:**

- **Thao tác:** Ở danh sách bên dưới, bấm chọn **thẻ số 1** (`legacy_reconcile_invoice`), sau đó bấm sang **thẻ số 2** (`process_payment`).
- **Tác Dụng:** Kiểm tra khả năng chỉ đúng vị trí dòng bị lệch cho người dùng dễ sửa.
- **Kết quả :** Khi bấm thẻ 1, dòng 6–7 bên tài liệu sáng đỏ và khung code hiện thanh báo không tìm thấy hàm. Khi bấm thẻ 2, thanh báo đỏ biến mất, dòng 3–4 bên tài liệu và dòng 1–5 bên code cùng sáng lên

**Bước 3 — Kiểm tra bộ lọc nhanh theo nhóm lỗi:**

- **Thao tác:** Bấm lần lượt vào 3 ô thống kê màu: **1. Referential Drift** -\> **2. Signature Drift** -\> **3. Semantic Drift**, rồi bấm lại **Tất cả sai lệch**.
- **Ý nghĩa:** Kiểm tra tính năng lọc riêng từng nhóm lỗi khi dự án có quá nhiều cảnh báo.


- **Kết quả :** Danh sách bên dưới tự thu gọn còn 1 thẻ đỏ -\> 3 thẻ vàng -\> 2 thẻ xanh, và hiện lại đủ 6 thẻ khi bấm **Tất cả sai lệch**

Bước 4 — Kiểm tra chuyên sâu từng nhóm lỗi riêng lẻ:

- **Thao tác:** Bấm lần lượt 3 nút kịch bản **2. Referential Drift**, **3. Signature Drift**, và **4. Semantic Drift** trên thanh công cụ.
- **Ý nghĩa:** Kiểm tra từng bộ quy tắc độc lập: nút 2 kiểm tra gợi ý tên hàm bị đổi (`validate_access_token`); nút 3 kiểm tra bắt lệch tham số và kiểu trả về; nút 4 kiểm tra bắt lỗi hành vi ẩn dù chữ ký hàm giống hệt nhau.

- **Kết quả :** Thanh biểu đồ đổi sang một màu duy nhất tương ứng với từng kịch bản và hiển thị đúng số lượng lỗi của nhóm đó (**2** lỗi ở nút 2, **3** lỗi ở nút 3, **3** lỗi ở nút 4).

**Bước 5 — Kiểm tra trường hợp tài liệu đã chuẩn 100%:**

- **Thao tác:** Bấm nút **5. Tài liệu khớp 100%**.
- **Ý nghĩa:** Đảm bảo công cụ không báo lỗi giả khi lập trình viên đã viết tài liệu chính xác.


- **Kết quả :** Tất cả chỉ số về **0**, thanh biểu đồ chuyển sang màu xanh lá toàn phần và hiện khung thông báo tài liệu đã đồng bộ hoàn toàn.

**Bước 6 — Kiểm tra tự sửa nội dung trực tiếp:**

- **Thao tác:** Đang ở Kịch bản 5, bấm nút **Sửa trực tiếp** ở góc trên bên phải, sửa chữ `False` thành `True` trong khung Markdown bên trái rồi bấm nút xanh **Chạy Phân Loại**.

- **Ý nghĩa:** Kiểm tra hệ thống chạy phân tích thời gian thực với dữ liệu bạn tự gõ.


- **Kết quả đúng:** Màn hình tự quay về chế độ soi dòng và báo ngay **1 lỗi Signature Drift** tại đúng dòng bạn vừa đổi giá trị mặc định.
