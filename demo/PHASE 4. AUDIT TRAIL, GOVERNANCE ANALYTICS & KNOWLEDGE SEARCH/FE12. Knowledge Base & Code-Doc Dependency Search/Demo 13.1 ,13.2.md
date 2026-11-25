# demo 13\.1,13\.2

<http://localhost:3000/knowledge-search>

**Knowledge Base & Code-Doc Dependency Search (FE12)** hỗ trợ tìm kiếm trên kho tài liệu và thực thể mã nguồn của **LivingDocs**, trải dài trên 2 phân hệ: **Vector Search & Hybrid RAG Retrieval Engine (13.1)** và **Interactive Bidirectional Navigation UI (Document ↔ Code Entity) (13.2)**. Mục tiêu là giúp người dùng tìm nhanh tài liệu hoặc mã nguồn liên quan theo từ khóa lẫn ngữ nghĩa, đồng thời nhảy qua lại hai chiều giữa tài liệu và file mã nguồn tương ứng.

- **13.1 Vector Search & Hybrid RAG Retrieval Engine:** Tính điểm khớp từ khóa (`keyword_score`) kết hợp tương đồng ngữ nghĩa vector (`semantic_score`) theo các chế độ `hybrid`, `semantic`, `keyword`, lọc theo `collection`, xếp hạng kết quả và trích xuất đoạn `rag_context` từ các mục liên quan nhất.
- **13.2 Interactive Bidirectional Navigation UI:** Hiển thị danh sách liên kết hai chiều (`bidirectional_links`) giữa tài liệu (`document`) và mã nguồn (`code_entity`), cho phép chọn một mục và bấm **Chuyển tới →** để chuyển trực tiếp giữa tài liệu và thực thể mã nguồn liên kết.

### bản demo kiểm thử FE12

- **Bước 1 — Kiểm tra Endpoint & Tìm Kiếm Hybrid Khởi Tạo (13.1):** Mở `http://localhost:8000/docs` (nhóm `fe12-knowledge-search`) gọi `GET /api/v1/knowledge-search/search?q=drift&mode=hybrid` hoặc mở `http://localhost:3000/knowledge-search`.
- 
    - *Kết quả mong đợi:* Trả về `200 OK` với danh sách kết quả kèm `score`, `keyword_score`, `semantic_score`, `rag_context`, và trang `/knowledge-search` hiển thị danh sách kết quả mặc định.
- **Bước 2 — Đổi Chế Độ Tìm Kiếm & Lọc Collection (13.1):** Trên trang `/knowledge-search`, nhập từ khóa (ví dụ `rollback` hoặc `policy`), đổi chế độ từ `Hybrid` sang `Semantic Vector` hoặc `Keyword`, và chọn một `Collection` (ví dụ `ci-cd`, `audit`, `governance`).
- 
    - *Kết quả mong đợi:* Kết quả tìm kiếm cập nhật đúng theo từ khóa, chế độ và collection đã chọn; khung **13.1 RAG Retrieved Context** đồng bộ nội dung trích dẫn top kết quả.
- **Bước 3 — Điều Hướng Hai Chiều Giữa Tài Liệu & Mã Nguồn (13.2):** Chọn một mục tài liệu `[DOC]` (ví dụ `FE06 CI/CD Pipeline & PR Merge Policy Runbook`) ở cột trái, xem danh sách liên kết hai chiều ở khung **13.2 Bidirectional Navigation**, sau đó bấm **Chuyển tới →** vào một thực thể mã nguồn `[CODE]` liên kết (ví dụ `ci_policy_service.py`).
- 
    - *Kết quả mong đợi:* Khung điều hướng chuyển sang chi tiết `[CODE] ci_policy_service.py` và hiển thị liên kết ngược trở lại `[DOC]` tương ứng để bấm quay lại hai chiều.
