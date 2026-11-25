# Visual Asset \- Code Consistency Verification Pipeline

<http://localhost:3000/multimodal-demo>

**Visual Asset - Code Consistency Verification Pipeline (FE05.3)** khép kín luồng xử lý đa phương thức của FE05 bằng cách lấy trực tiếp đồ thị kiến trúc và danh sách `ArchitecturalClaims` từ **FE05.2** để đối chiếu tự động với mã nguồn thật trong repository qua cây cú pháp trừu tượng (**Python AST**) và bộ quét định tuyến (**API Route Scanner**).

### Cơ chế kiểm chứng 3 tầng của FE05.3

- **Lập chỉ mục mã nguồn tĩnh (AST & Route Indexer):** Tự động quét toàn bộ thư mục dự án (`D:\CNPM\LivingDocs` hoặc đường dẫn tùy chỉnh), trích xuất tọa độ chính xác (`file_path:line_number`) của từng `class`, `def` / `async def`, decorator `@router.<method>(...)` kèm `APIRouter(prefix=...)` và tập lời gọi hàm nội bộ (`ast.Call`) trong từng tệp.
- **Đối chiếu đa chiều theo 3 nhóm khẳng định:**
    - `api_contract`: So khớp `METHOD + PATH` với các route trong backend; phát hiện **API Drift** nếu endpoint trên sơ đồ bị lệch phiên bản hoặc sai đường dẫn so với router thật.
    - `code_mapping`: Xác minh sự tồn tại của lớp (`ClassDef`), hàm (`FunctionDef`) và đường dẫn tệp triển khai; phát hiện **Symbol/File Drift** nếu hàm bị đổi tên hoặc nằm sai tệp.
    - `service_dependency` / `data_persistence`: Kiểm tra cả hai thành phần nguồn–đích lẫn chiều gọi hàm thực tế trong AST để phát hiện **Dependency Drift** (mũi tên vẽ ngược chiều gọi hoặc dịch vụ đích không tồn tại).
- **Chấm điểm nhất quán & đề xuất khắc phục (Consistency Scoring & Remediation):** Phân loại từng khẳng định thành `CONSISTENT`, `DRIFTED` hoặc `UNVERIFIED`, tính chỉ số `consistency_score` (`0%` – `100%`) và sinh hướng dẫn đồng bộ cụ thể giữa tài liệu trực quan và mã nguồn.

- **Bước 1 — Kiểm tra Endpoint Backend trên Swagger UI (**`http://localhost:8000/docs`**):**
    - Mở nhóm `multimodal` -\> chọn `POST /api/v1/multimodal/verify-consistency` -\> bấm **Try it out**.
    - Tải lên một tệp ảnh sơ đồ hoặc PDF bất kỳ (để trống `repo_path` để tự động quét `D:\CNPM\LivingDocs`) và bấm **Execute**.
- 
    - **Kết quả :** API trả về mã `200 OK` với JSON `VisualCodeConsistencyResponse` chứa `scanned_repo_root`, `scanned_files_count`, `indexed_symbols_count`, `consistency_score`, `overall_status` và mảng `verification_results` kèm `evidences` (`file_path`, `line_number`, `snippet`).
- **Bước 2 — Kiểm thử đối chiếu mã nguồn thật (**`4. Kiến trúc LivingDocs Multimodal (Live Code)`**):**
    - Trên trang `http://localhost:3000/multimodal-demo`, quan sát kết quả mặc định của mẫu số 4 (`livingdocs_multimodal_pipeline.png`).
    - **Kết quả :**
    - 
        - Hàng KPI hiển thị phạm vi quét toàn bộ dự án (`scanned_files_count` và hàng trăm `classes / functions / routes` đã lập chỉ mục), kèm điểm nhất quán tổng thể (**Consistency Score**).
        - Các khẳng định về hàm và API thật của dự án như `POST /api/v1/multimodal/ocr`, `VisionContextExtractor` (`extract_context()`), `TechnicalAssetOcrEngine` (`extract_from_bytes()`), `VisualAssetConsistencyVerifier` (`verify_consistency()`) và luồng gọi `VisionContextExtractor` -\> `TechnicalAssetOcrEngine` đều hiển thị nhãn xanh `CONSISTENT` kèm khung đen **Code Evidence** trỏ đúng dòng code thật (`app/api/multimodal.py`, `app/services/vision_context_extractor_service.py`, `app/services/ocr_engine_service.py`, `app/services/visual_consistency_service.py`).
    - 
        - Riêng cạnh `VisionContextExtractor` -\> `VisualAssetConsistencyVerifier` bị gắn nhãn đỏ `DRIFTED` vì trong AST thực tế `VisualAssetConsistencyVerifier` mới là lớp gọi `VisionContextExtractor` (ngược chiều mũi tên trên sơ đồ mẫu) — chứng minh bộ phân tích AST kiểm tra được cả hướng phụ thuộc thực tế.
- **Bước 3 — Kiểm thử phát hiện Drift & thành phần chưa triển khai (Mẫu số 1, 2, 3):**
    - Bấm lần lượt vào `1. Sơ đồ Kiến trúc Microservices`, `2. Lưu đồ Xác thực Token` và `3. Sơ đồ Đồng bộ Repository`.
    - Sử dụng thanh lọc trạng thái `ALL`** | **`CONSISTENT`** | **`DRIFTED`** | **`UNVERIFIED` ở góc phải khung **Repository Root**.
    - **Kết quả :**
    - 
        - Các thành phần nghiệp vụ giả định chưa có trong repo hiện tại (`BillingService`, `TransactionDB`, `SessionCache`, `POST /api/v1/billing/charge`) được phân loại rõ ràng thành `UNVERIFIED` hoặc `DRIFTED` (nếu trùng từ khóa gần giống với hàm hiện có trong repo), kèm hộp **Đề xuất xử lý** hướng dẫn bổ sung code hoặc cập nhật lại sơ đồ.
- **Bước 4 — Kiểm thử đối chiếu Tài liệu Đặc tả PDF Đa trang:**
    - Bấm nút `Tải lên Ảnh / PDF thật` ở góc trên bên phải và chọn tệp `LivingDocs Architecture & API Specification.pdf` (tài liệu đặc tả 3 trang).
    - **Kết quả :**
    - 
        - Hệ thống chạy nối tiếp **FE05.1 (tách 3 trang PDF)** -\> **FE05.2 (hợp nhất đồ thị đa trang & 12 claims)** -\> **FE05.3 (đối chiếu cả 12 claims với AST mã nguồn)**.
        - Những claims trùng khớp với các service/endpoint thật trong `backend/app/` hiện `CONSISTENT`, các claims mô tả module mở rộng chưa triển khai hiện `UNVERIFIED` kèm bằng chứng đối chiếu chi tiết.
- **Bước 5 — Kiểm tra tính toàn vẹn xuyên suốt 3 phân hệ (**`FE05.1 OCR`** -\>**`FE05.2 Vision Graph`** -\> **`FE05.3 Drift Check`**):**
    - Trên cùng một tài liệu đang mở, bấm chuyển qua lại giữa 3 nút `FE05.1 OCR`, `FE05.2 Vision Graph` và `FE05.3 Drift Check` ở góc trên bên phải.
    - **Kết quả đúng:** Dữ liệu đồng bộ tức thì không cần gọi lại API: **FE05.1** hiển thị ảnh gốc, token post-OCR và văn bản chuẩn hóa; **FE05.2** hiển thị đồ thị SVG tương tác (có tên hàm/endpoint ngay trên từng hộp) và Node Inspector; **FE05.3** hiển thị báo cáo kiểm chứng sai lệch với mã nguồn thật.
