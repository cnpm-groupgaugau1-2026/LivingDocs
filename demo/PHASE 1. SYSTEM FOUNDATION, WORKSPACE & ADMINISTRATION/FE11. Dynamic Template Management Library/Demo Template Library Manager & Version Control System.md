# Demo Template Library Manager & Version Control System

<http://localhost:3000/templates>

## 1. Tra cứu & Lọc danh mục chuẩn (Catalog Filtering)

1. Quan sát danh sách mặc định gồm 5 mẫu chuẩn hệ thống đã khởi tạo trong PostgreSQL (`Enterprise REST API Reference`, `Standard Repository README`, `Backend Service Module Guide`, `Engineering Onboarding Guide`, `Architecture Decision Record (ADR)`) cùng template vừa tạo ở bước 3.1.


1. Bấm các nút lọc theo phân loại (`API Reference`, `ADR`, `README`...) trên thanh công cụ để kiểm tra bộ lọc tức thì.



1. Nhập từ khóa `docs/api` vào ô tìm kiếm và tích chọn `Chỉ hiển thị các Template đang áp đặt (Enforced Policy)` để lọc riêng các mẫu đang bắt buộc áp dụng trong CI/CD.

## 2. Nhân bản (Clone) & Bật/Tắt chính sách áp đặt (Enforce Policy)

1. Trên thẻ `Enterprise REST API Reference`, bấm nút `Clone`:
    - Backend gọi `POST /api/v1/templates/{id}/clone` và tạo bản sao độc lập tên `Enterprise REST API Reference (Clone)` ở phiên bản `v1.0` với trạng thái mặc định là `Optional / Draft`.


1. Trên thẻ bản sao vừa tạo, bấm nút `Bật Enforce` ở góc trên bên phải:

- 
    - Backend gọi `PATCH /api/v1/templates/{id}/enforce`, nhãn trạng thái lập tức chuyển sang `Enforced` (chấm xanh) kèm thông báo áp dụng trên đường dẫn `docs/api/**/*.md`.

## 3. Tạo mốc phiên bản mới (Versioning)

1. Bấm `Chỉnh sửa (Builder)` ngay trên thẻ `Enterprise REST API Reference (Clone)`.

1. Thêm một dòng mô tả hoặc chèn thêm biến `{{functions.list}}` vào khung soạn thảo, sửa ghi chú phiên bản thành `Bổ sung danh sách hàm public vào API Spec`, rồi bấm `Lưu Template & Tạo Phiên Bản`.

1. Quay lại tab `3.2 Template Library & Version Control`: nhãn phiên bản trên thẻ tự động tăng từ `v1.0` lên `v1.1` và nút lịch sử cập nhật thành `Lịch sử (2 bản)`

## 4. Xem lịch sử thay đổi & Khôi phục phiên bản (Version History & Rollback)

1. Bấm vào dòng `Lịch sử (2 bản)` ở góc dưới bên phải của thẻ template vừa sửa để mở hộp thoại **Version Control History**.

1. Kiểm tra danh sách snapshot lưu trong bảng `doc_template_versions` (`v1.1` và `v1.0`) hiển thị đầy đủ tác giả, thời gian cập nhật, ghi chú thay đổi và nội dung Markdown gốc của từng bản.


1. Bấm nút `Rollback về v1.0`:

- 
    - Hệ thống gọi `POST /api/v1/templates/{id}/rollback/{version_id}`, khôi phục toàn bộ nội dung và cấu hình ánh xạ của `v1.0`, đồng thời ghi nhận một bản lưu kiểm toán mới là `v1.2` (`Rollback về nội dung của v1.0`).


1. Nhấn `F5` tải lại trang để xác nhận toàn bộ trạng thái `Enforced`, bản sao và lịch sử phiên bản được lưu bền vững trong PostgreSQL.
