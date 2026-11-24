# Vision\-LLM Context Extractor \(Diagrams, Flowcharts, PDFs\)

<http://localhost:3000/multimodal-demo>

**Vision-LLM Context Extractor (FE05.2)** là tầng suy luận ngữ nghĩa và tái dựng đồ thị kiến trúc từ tài liệu trực quan (sơ đồ microservices, lưu đồ flowchart, pipeline và tài liệu PDF đặc tả nhiều trang), chuyển đổi các thực thể rời rạc từ OCR (FE05.1) thành **đồ thị có hướng (**`Nodes`** & **`Directed Edges`**)** và các **khẳng định kiến trúc (**`Architectural Claims`**)** có thể kiểm chứng trực tiếp với mã nguồn ở bước **FE05.3**.

Hệ thống xử lý qua **3 tầng tự động**:

- **Hợp nhất ngữ cảnh đa phương thức (Multimodal Context Fusion):** Nhận đồng thời tệp hình ảnh/PDF gốc và tập thực thể kỹ thuật đã chuẩn hóa từ `TechnicalAssetOcrEngine` (FE05.1), tự động gắn kết các hàm (`functions`), đường dẫn tệp (`file_paths`) và API endpoint vào đúng dịch vụ (`Node`) chủ quản theo vùng lân cận và tên miền nghiệp vụ.
- **Đa tầng suy luận đồ thị (Hybrid Vision-LLM & Structural Graph Engine):** Ưu tiên gọi trực tiếp **Gemini 2.5 Flash Vision-LLM** (`gemini_vision_llm`) nếu `backend/.env` có cấu hình `GEMINI_API_KEY` để suy luận không gian hình hộp và hướng mũi tên -\> tự động chuyển sang bộ tái dựng đồ thị cấu trúc cục bộ (`structural_graph_reconstructor`) khi chạy offline để đảm bảo kết quả luôn nhất quán và không phụ thuộc hạn mức API.
- **Tổng hợp luồng thực thi & khẳng định kiểm chứng (Execution Flow & Claim Synthesizer):** Tái dựng trình tự gọi hàm theo từng bước (`Execution Flows`) và sinh danh sách các ràng buộc kỹ thuật chuẩn hóa (`CLM-01`, `CLM-02`,...) kèm `verifiable_target` sẵn sàng đưa vào bộ phát hiện sai lệch mã nguồn (**FE05.3**).

**Bước 1 — Kiểm tra API Context Extractor trên Backend:**

- Mở nhanh tab mới tới `http://localhost:8000/docs`, tìm nhóm `multimodal` và mở rộng endpoint `POST /api/v1/multimodal/extract-context`.


**Kết quả :** Endpoint hiển thị đầy đủ 2 tham số đầu vào `file` (bắt buộc) và `context_hint` (tùy chọn), cùng lược đồ phản hồi `VisionContextExtractionResponse` gồm các trường `nodes`, `edges`, `execution_flows` và `architectural_claims`.

**Bước 2 — Kiểm tra sơ đồ kiến trúc mặc định (**`1. Sơ đồ Kiến trúc Microservices`**):**

- Quay lại `http://localhost:3000/multimodal-demo`, quan sát 4 thẻ KPI phía trên, khung **Đồ thị kiến trúc tái dựng (Directed Graph)** và bảng **Node Inspector** bên phải.
- **Kết quả:**
- 
    - Thẻ **Loại tài liệu suy luận** hiển thị `architecture_diagram` (`1 trang • 8 OCR tokens`), đạt **4 Nodes**, **3 Directed Edges** và **7 Architectural Claims**.
    - Khung đồ thị SVG vẽ lại chính xác **4 hộp thành phần** (`ApiGateway`, `BillingService`, `AuthService`, `TransactionDB`) cùng **3 mũi tên chỉ hướng** (`HTTP/JSON`, `verify_jwt`, `SQL Write`) mà OCR thuần túy ở FE05.1 không đọc được.
- 
    - Khi bấm chuột vào từng hộp trên sơ đồ (`ApiGateway`, `BillingService`, `AuthService`, `TransactionDB`), khung **Node Inspector** bên phải hiển thị đúng endpoint đã chuẩn hóa (`POST /api/v1/billing/charge`) và các hàm tương ứng (`process_payment()`, `validate_access_token()`, `save_transaction()`).

**Bước 3 — Kiểm tra nhận diện lưu đồ (**`2. Lưu đồ Xác thực Token`**) và sơ đồ pipeline (**`3. Sơ đồ Đồng bộ Repository`**):**

- Bấm lần lượt vào nút `2. Lưu đồ Xác thực Token` và `3. Sơ đồ Đồng bộ Repository` trên thanh công cụ.
- **Kết quả :**
- 
    - Ở mẫu số 2, hệ thống tự chuyển loại tài liệu sang `flowchart`, dựng đủ 4 node (`ClientRequest`, `AuthMiddleware`, `SessionCache`, `ProtectedAPI`) cùng các hàm `verify_jwt_signature()`, `check_revoked_jti()`, `dispatch_controller()` và 3 luồng điều hướng (`Authorization`, `Redis Lookup`, `Valid Token`).
- 
    - Ở mẫu số 3, hệ thống chuyển sang `pipeline_diagram`, tái dựng đầy đủ chuỗi luồng từ `GitHubWebhook` (`POST /api/v1/github/webhook`) -\> `RepoService` (`sync_repository()`) -\> tách 2 nhánh tới `ASTParser` (`parse_python_symbols()`) và `DriftEngine` (`classify_doc_drift()`).

- **Bước 4 — Kiểm tra Luồng thực thi tuần tự và Khẳng định kiến trúc đầu ra cho FE05.3:**
    - Kéo xuống 2 khung bên dưới cùng: **Luồng thực thi tuần tự (Execution Flows)** và **Khẳng định kiến trúc (Sẵn sàng cho FE05.3 Drift Check)**.
    - **Kết quả :**
    - 
        - Cột bên trái liệt kê rõ trình tự từng bước từ `1` đến `3` (ai gọi ai, kích hoạt hàm nào, qua giao thức gì).
        - Cột bên phải sinh danh sách các khẳng định chuẩn hóa (`CLM-01`, `CLM-02`,...) phân loại rõ theo `service_dependency`, `data_persistence`, `api_contract` và `code_mapping` để tầng FE05.3 đối chiếu tự động với AST của mã nguồn.
- **Bước 5 — Kiểm thử hợp nhất ngữ cảnh từ tệp PDF nhiều trang:**
    - Bấm nút xanh `Tải lên Ảnh / PDF thật` ở góc trên bên phải và chọn tệp `LivingDocs Architecture & API Specification.pdf` (tài liệu đặc tả 3 trang).
    - **Kết quả đúng:**
    - 
        - Hệ thống tự động hợp nhất toàn bộ **55 OCR tokens** qua **3 trang** (`pdf_document`), dựng thành một đồ thị kiến trúc thống nhất kèm chỉ số trang nguồn (`p.1`, `p.2`, `p.3`) trên từng Node.
        - Khi bấm vào các Node trong **Node Inspector**, mục **Đường dẫn mã nguồn (File Paths)** tự động ánh xạ đúng tệp triển khai (`app/services/billing_service.py`, `app/services/auth_service.py`, `app/services/repo_service.py`) và sinh trọn bộ **12 Architectural Claims** có gắn `verifiable_target` cụ thể.
