# Demo Webhook Handler & Real\-time Ingestion Pipeline

**\*Kích hoạt Real-time Ingestion Pipeline từ giao diện**

Vì môi trường phát triển đang chạy trên localhost nên GitHub chưa thể gọi trực tiếp vào máy cục bộ nếu không qua tunnel. Nút `⚡ Test Webhook` gọi API `POST /api/v1/github/webhook/simulate` để lấy commit mới nhất từ repository trên GitHub và đẩy qua đúng hàm xử lý `_run_webhook_ingestion_pipeline`. Hệ thống tự động lọc các file `.md`, cập nhật nội dung mới vào PostgreSQL và ghi nhận nhật ký trạng thái

**\*Giả lập gói tin GitHub Webhook thật (**`ping`** & **`push`**) qua Swagger UI**


Đây chính là endpoint `POST /api/v1/github/webhook` nhận trực tiếp sự kiện từ GitHub. Khi có commit mới được push lên nhánh `main`, Backend kiểm tra chữ ký bảo mật `X-Hub-Signature-256` bằng thuật toán `HMAC-SHA256`, duyệt qua mảng `commits` để lọc riêng các file `.md` được thêm, sửa hoặc xóa, sau đó tự động gọi GitHub Contents API cập nhật vào PostgreSQL. Ở phía Frontend, giao diện tự động cập nhật nhật ký `LIVE` mà người dùng không cần tải lại trang.

**\*Đối chiếu nhật ký trong bảng **`webhook_event_logs`** (PostgreSQL)**

Mọi sự kiện webhook đi qua hệ thống đều được lưu vết kiểm toán (audit log) trong bảng `webhook_event_logs` của PostgreSQL gồm loại sự kiện, mã commit 7 ký tự, danh sách file bị tác động và trạng thái xử lý (`ingested`, `ignored` hoặc `connected`), giúp Tech Lead và Admin dễ dàng giám sát luồng đồng bộ tự động.
