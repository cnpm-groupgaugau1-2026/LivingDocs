# Severity Scoring Engine \(Low, Medium, High, Critical\)

<http://localhost:3000/drift-demo>

**Severity Scoring Engine (Sub-feature 5.2)** là bộ chấm điểm mức độ nguy hiểm cho từng sai lệch mà bộ phân loại 5.1 vừa tìm ra, giúp lập trình viên biết **lỗi nào nghiêm trọng nhất để ưu tiên sửa trước** thay vì phải đọc dàn trải từ trên xuống dưới.

Hệ thống tính điểm từng lỗi trên thang **0 – 100** dựa trên 4 tiêu chí thực tế:

- **Mức độ làm hỏng code (**`8 – 45đ`**):** Lỗi âm thầm sửa/xóa dữ liệu (`45đ`) hoặc đổi tham số bắt buộc (`42đ`) bị phạt nặng nhất; lỗi chỉ thêm tham số tùy chọn (`8đ`) bị phạt nhẹ nhất.
- **Độ nhạy cảm nghiệp vụ (**`+20đ`**):** Cộng thêm điểm nếu lỗi nằm ở hàm/tệp liên quan đến thanh toán (`payment`, `billing`), bảo mật (`auth`, `token`, `security`) hoặc xóa dữ liệu (`delete`, `cleanup`).
- **Phạm vi ảnh hưởng công khai (**`+10đ`**):** Cộng thêm điểm nếu đó là hàm công khai cho bên ngoài gọi (không bắt đầu bằng dấu `_`).
- **Độ tin cậy của hệ thống (**`0 – 15đ`**):** Độ chắc chắn càng cao thì điểm cộng càng lớn.

Từ tổng điểm này, mỗi lỗi được gắn nhãn 1 trong 4 cấp độ và **tự động sắp xếp từ cao xuống thấp**:

- **CRITICAL (**`80 – 100đ`** — Đỏ đậm):** Cực kỳ nguy hiểm, có thể gây mất dữ liệu hoặc sập luồng thanh toán/bảo mật.
- **HIGH (**`60 – 79đ`** — Cam):** Rủi ro cao, dễ làm người dùng gọi sai hàm hoặc gặp lỗi bất ngờ.
- **MEDIUM (**`35 – 59đ`** — Vàng):** Rủi ro trung bình, cần cập nhật tài liệu sớm.
- **LOW (**`0 – 34đ`** — Xanh dương):** Rủi ro thấp, ít ảnh hưởng đến hệ thống đang chạy.

## Các bước kiểm thử trực tiếp trên giao diện

**Bước 1 — Kiểm tra tự động xếp hạng ưu tiên ở Kịch bản 1 (**`1. Tổng hợp cả 3 loại Drift`**):**

- **Quan sát khung bên phải (**`5.2 Điểm rủi ro tài liệu`**):** Hệ thống chấm điểm rủi ro chung của cả tệp là `86 / 100 điểm`** (**`CRITICAL`**)**, chia thành **1 Critical – 3 High – 2 Medium – 0 Low**.


- **Quan sát thứ tự danh sách bên dưới:** Lỗi mâu thuẫn `read-only` nhưng lại gọi `db.save_transaction` tự động nhảy lên **vị trí số 1** với huy hiệu `CRITICAL • 89/100`, đẩy lỗi thiếu hàm cũ (`MEDIUM • 59/100`) xuống vị trí số 5.


- **Kiểm tra giải thích điểm số:** Nhìn vào khung **"Công thức chấm điểm"** ngay trong thẻ số 1, bạn sẽ thấy rõ từng khoản cộng (`+45đ` side-effect + `+20đ` luồng thanh toán + `+10đ` hàm công khai + `+14đ` độ tin cậy = `89đ`).

**Bước 2 — Kiểm tra bộ lọc theo 4 cấp độ rủi ro:**

- Ở khung **5.2 Điểm rủi ro tài liệu**, bấm lần lượt vào 4 ô: **CRITICAL** -\>**HIGH** -\>**MEDIUM** -\> **LOW**.



- **Kết quả :** Danh sách bên dưới thu gọn đúng số thẻ tương ứng (`1` thẻ Critical -\>`3` thẻ High -\> `2` thẻ Medium -\> `0` thẻ Low). Bấm dòng chữ **Xóa lọc mức độ** để hiện lại đủ 6 thẻ.

**Bước 3 — Kiểm tra Kịch bản 3 (**`3. Signature Drift`**) để thấy mức **`MEDIUM`** và **`LOW`**:**

- Bấm nút **3. Signature Drift** ở hàng kịch bản phía trên.

- **Kết quả :** Điểm rủi ro chung giảm xuống còn `52 / 100 điểm`** (**`MEDIUM`**)** vì `search_documents` chỉ là hàm tìm kiếm thông thường, không bị cộng `+20đ` nhạy cảm. Danh sách bên dưới hiện 3 mức nhẹ hơn: `MEDIUM • 56/100`, `MEDIUM • 42/100`, và `LOW • 33/100` (thêm tham số tùy chọn `include_archived` ít gây lỗi nhất nên xếp cuối cùng).

**Bước 4 — Kiểm tra Kịch bản 2 (**`2. Referential Drift`**) và Kịch bản 4 (**`4. Semantic Drift`**):**

- Bấm **2. Referential Drift**: điểm rủi ro chung là `78 / 100 điểm`** (**`HIGH`**)**, gồm lỗi đổi tên hàm xác thực `verify_access_token` (`CRITICAL • 80/100`) xếp trên lỗi sai đường dẫn tệp (`HIGH • 66/100`).


- Bấm **4. Semantic Drift**: điểm rủi ro chung nhảy lên `86 / 100 điểm`** (**`CRITICAL`**)**, đứng đầu là lỗi gọi lệnh xóa tài khoản `db.delete_inactive_accounts` trái mô tả `read-only` (`CRITICAL • 89/100`).

**Bước 5 — Kiểm tra trạng thái an toàn ở Kịch bản 5 (**`5. Tài liệu khớp 100%`**):**


- Bấm **5. Tài liệu khớp 100%**: điểm rủi ro chung về `0 / 100 điểm`, nhãn đổi sang màu xanh dương `IN SYNC`** (An toàn tuyệt đối)**.
