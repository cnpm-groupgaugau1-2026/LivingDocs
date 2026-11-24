# Multi\-language AST Code Entity Parser Engine

**Multi-language AST Code Entity Parser Engine** (`backend/app/services/ast_parser_service.py`) đóng vai trò là tầng nền tảng bóc tách cấu trúc mã nguồn cho toàn bộ hệ thống LivingDocs:

- **Nguyên lý cốt lõi:** Sử dụng bộ phân tích cú pháp **Tree-sitter** để biên dịch mã nguồn tĩnh thành **Cây cú pháp trừu tượng (AST)** thay vì dùng biểu thức chính quy (Regex) hay thực thi mã. Cách tiếp cận này đảm bảo độ chính xác tuyệt đối về ngữ pháp, không bị nhầm lẫn bởi chuỗi ký tự hoặc comment giả, và an toàn tuyệt đối vì không chạy code.
- **Hỗ trợ đa ngôn ngữ trên một đầu ra thống nhất:** Dù đầu vào là **Python** (`.py`), **JavaScript** (`.js`, `.jsx`) hay **TypeScript** (`.ts`, `.tsx`), engine đều chuẩn hóa kết quả về cùng một cấu trúc dữ liệu `ASTParseResponse`.

Truy cập `http://localhost:3000`, bấm nút `✨ Sinh tài liệu AI (AST)` trên thanh công cụ trình soạn thảo và chọn tab `Dán / Tải tệp Code` (hoặc mở Swagger UI tại `http://localhost:8000/docs` với endpoint `POST /api/v1/doc-generation/parse`) để thực hiện kịch bản kiểm thử 4 bước dưới đây.

Bước 1: Phân tích cú pháp Python & Bóc tách quan hệ Class – Method

Trên cột cấu hình bên trái của cửa sổ phân tích, nhập thông tin cho một service Python mẫu để kiểm tra khả năng nhận diện ngôn ngữ và cấu trúc phân cấp lớp – phương thức:


- **Tổng thực thể AST (**`3`**):** Bộ phân tích Tree-sitter đã quét toàn bộ tệp và nhận diện được đúng 3 khối cấu trúc chính gồm 1 lớp (`PaymentGateway`) và 2 phương thức (`charge`, `refund`).
- **Đã có Docstring (**`2`**):** Trong 3 thực thể trên, có 2 thực thể đã được viết mô tả bằng chuỗi `"""..."""` là lớp `PaymentGateway` và phương thức `charge`.
- **Độ phủ tài liệu (**`66.67%`**):** Hệ thống lấy số thực thể đã có tài liệu chia cho tổng số thực thể (2/3 \*100%) để đo lường mức độ hoàn thiện tài liệu hiện tại của tệp mã nguồn.
- **Ưu tiên cao (**`0`**):** Cảnh báo mức `HIGH` chỉ kích hoạt khi một hàm vừa **thiếu tài liệu** vừa có **logic phức tạp** (nhiều vòng lặp và điều kiện lồng nhau). Trong đoạn mã này không có hàm nào rơi vào ngưỡng rủi ro cao nên chỉ số bằng `0`.
- Lớp `PaymentGateway` và phương thức `charge` không xuất hiện trong danh sách lỗi vì cả hai đều đã có docstring đầy đủ, riêng `charge` đã khai báo trọn vẹn kiểu dữ liệu đầu vào (`str`, `float`) lẫn kiểu trả về (`-> dict`). Toàn bộ thiếu sót đều tập trung ở phương thức `refund`:

  image\_3f9d00.png

  
    - **Thông tin định vị trên tiêu đề thẻ (**`PaymentGateway.refund`** | **`Dòng 12–15`** | **`Complexity: 2`**):**
        - `PaymentGateway.refund`: Cây AST nhận diện chính xác quan hệ cha – con, biết `refund` là phương thức nằm trong lớp `PaymentGateway` chứ không phải hàm đứng độc lập.
        - `Dòng 12–15`: Tọa độ dòng bắt đầu và kết thúc chính xác của hàm `refund` trong khung mã nguồn bên trái.
        - `Complexity: 2`: Điểm độ phức tạp rẽ nhánh (Cyclomatic Complexity). Mọi hàm đều có điểm gốc là `1`; hàm `refund` có thêm 1 nhánh điều kiện `if not transaction_id:` nên cộng thêm `1` thành `2`.
    - **Cảnh báo **`MEDIUM`** (Thiếu Docstring):** Hàm `refund` chưa có dòng mô tả `"""..."""` bên trong để giải thích mục đích hoàn tiền và ý nghĩa tham số `transaction_id`. Vì độ phức tạp của hàm ở mức thấp (`2`), hệ thống xếp mức ưu tiên bổ sung ở ngưỡng trung bình (`MEDIUM`).
    - **Cảnh báo **`LOW`** (Thiếu kiểu dữ liệu trả về):** Ở dòng 12, tham số đầu vào đã có kiểu (`transaction_id: str`), nhưng phần khai báo hàm chưa chỉ rõ kiểu dữ liệu trả về (ví dụ `-> bool`). Hệ thống nhắc bổ sung phần này ở mức `LOW` để bước sinh tài liệu AI phía sau xác định chính xác hàm trả về giá trị logic `True`/`False`.

      
- Nếu chúng ta thử thêm dòng `"""Hoàn tiền giao dịch."""` và sửa dòng 12 thành `def refund(self, transaction_id: str) -> bool:` rồi bấm lại **Phân tích AST & Độ phủ**, chỉ số **Độ phủ tài liệu** sẽ tăng lên **100%** và danh sách **Thực thể thiếu tài liệu** sẽ trống hoàn toàn.


Bước 2: Chuyển đổi đa ngôn ngữ sang TypeScript & Bóc tách JSDoc / Arrow Function

Thay đổi sang mã nguồn TypeScript để kiểm chứng cơ chế tự động chuyển bộ ngữ pháp sang `tree-sitter-typescript` và chuẩn hóa đầu ra thống nhất:

Kết quả trên màn hình cho thấy **AST Parser Engine** đã tự động chuyển sang bộ ngữ pháp **TypeScript** (dựa vào đuôi `.ts`), đọc thành công chuẩn bình luận **JSDoc** và bóc tách chính xác cú pháp **Arrow Function** hiện đại.

### \*Ý nghĩa 4 thẻ chỉ số tổng quan

Các chỉ số thống kê ở góc trên bên phải phản ánh quá trình phân tích cấu trúc tệp `src/auth/TokenService.ts`:

- **Tổng thực thể AST (**`3`**):** Engine nhận diện đủ 3 cấu trúc gồm lớp `TokenService`, phương thức `verify` và hàm mũi tên `extractBearer` — chứng minh bộ phân tích hiểu được hàm gán biến (`export const ... =>`) chứ không chỉ cú pháp `function` truyền thống.
- **Đã có Docstring (**`2`**) & Độ phủ (**`66.67%`**):** Thay vì tìm chuỗi `"""..."""` bên trong thân hàm như Python, engine tự động quét các khối bình luận JSDoc (`/** ... */`) nằm *liền kề phía trên* khai báo, ghi nhận đúng 2 mô tả của `TokenService` và `verify` 
- **Ưu tiên cao (**`0`**):** Không có hàm nào rơi vào ngưỡng vừa thiếu tài liệu vừa có logic quá phức tạp.

### \*Chi tiết thẻ cảnh báo `extractBearer`

Toàn bộ phần thiếu sót được khoanh vùng chính xác vào hàm mũi tên `extractBearer` ở cuối tệp:

- **Nhận diện đúng tên hàm & tọa độ (**`extractBearer`** | **`Dòng 14–17`**):** Dù được khai báo dưới dạng hằng số `export const`, cây AST vẫn tách riêng nó thành một thực thể hàm độc lập và định vị chính xác từ dòng 14 đến dòng 17.
- **Đo độ phức tạp (**`Complexity: 2`**):** Điểm cơ sở là `1` cộng thêm `1` câu lệnh rẽ nhánh `if` ở dòng 15, cho thấy logic hàm tương đối đơn giản nên chỉ bị gắn nhãn ưu tiên `MEDIUM`.
- **Không xuất hiện cảnh báo **`LOW`** như bên Python:** Khác với hàm `refund` lúc trước bị nhắc thiếu kiểu trả về, hàm `extractBearer` đã khai báo đầy đủ kiểu tham số (`authHeader?: string`) và kiểu trả về (`: string | null`), nên hệ thống chỉ yêu cầu bổ sung khối JSDoc mô tả mục đích hàm và tham số `authHeader`.

Nếu chúng ta thêm  khối `/** Trích xuất chuỗi token từ header Authorization. */` ngay phía trên dòng 14 và bấm **Phân tích AST & Độ phủ**, độ phủ của tệp TypeScript này sẽ đạt **100%**.

Bước 3: Kiểm thử JavaScript & Đo lường độ phức tạp nhánh (Cyclomatic Complexity)

Thử nghiệm với tệp JavaScript thuần (`.js`) chứa nhiều cấu trúc rẽ nhánh lồng nhau để kiểm tra bộ tính điểm độ phức tạp logic:

Kết quả trên màn hình cho thấy **AST Parser Engine** đã tự động chuyển sang bộ ngữ pháp **JavaScript** (dựa vào đuôi `.js`)

### Tại sao "Độ phủ tài liệu" đạt 100% nhưng vẫn có 1 cảnh báo `LOW`?

Hệ thống tách bạch 2 tiêu chí đánh giá chất lượng tài liệu khác nhau trên cùng một hàm `dispatchSyncJob`:

- **Chỉ số Độ phủ tài liệu (**`100%`**):** Chỉ số này đo tỷ lệ số thực thể đã có phần mô tả tổng quan (`Docstring` / `JSDoc`). Do chúng ta đã viết khối bình luận `/** Điều phối hàng đợi đồng bộ dữ liệu từ GitHub Webhook. */` ngay phía trên hàm nên tỷ lệ đạt `1/1 = 100%`.
- **Cảnh báo mức **`LOW`** (Thiếu kiểu dữ liệu):** Vì đây là tệp **JavaScript thuần (**`.js`**)**, tham số `repoName` và giá trị trả về của hàm không có khai báo kiểu dữ liệu (`type annotation`), trong khi hai tham số còn lại (`maxRetries = 3`, `isUrgent = false`) có giá trị mặc định để hệ thống tự nhận biết. Do đó, bộ phân tích vẫn gắn một gợi ý nhẹ ở mức `LOW` để lưu ý rằng nếu bổ sung kiểu dữ liệu (hoặc viết bằng TypeScript `.ts`), bước sinh tài liệu AI phía sau sẽ mô tả chính xác kiểu đầu vào/đầu ra hơn

Điểm độ phức tạp Cyclomatic (`5`) phản ánh số lượng đường rẽ nhánh logic bên trong thân hàm `dispatchSyncJob` (dòng 4–14):

- **Điểm cơ sở (**`+1`**):** Mọi hàm đều bắt đầu với điểm mặc định là `1`.
- **Nhánh kiểm tra điều kiện đầu vào (**`+1`**):** Câu lệnh `if (!repoName)` ở dòng 5.
- **Vòng lặp xử lý thử lại (**`+1`**):** Vòng lặp `for (let attempt = 0; ...)` ở dòng 8.
- **Điều kiện lồng trong vòng lặp (**`+1`**):** Câu lệnh `if (attempt === 2 && !isUrgent)` ở dòng 9.
- **Toán tử rẽ nhánh ba ngôi (**`+1`**):** Biểu thức `isUrgent ? true : false` ở dòng 13.

Bước 4: Kiểm thử nạp trực tiếp tệp mã nguồn từ GitHub Workspace

Để kiểm thử luồng nạp trực tiếp mã nguồn từ **GitHub Workspace** (tự động quét cây thư mục repository qua GitHub API, lọc đúng các tệp ngôn ngữ hỗ trợ AST và tải nội dung về bộ phân tích).

-Chọn hoặc bổ sung tệp mã nguồn vào Repository GitHub

-Nạp tệp từ GitHub Workspace vào khung phân tích AST

-Chạy phân tích và đối chiếu kết quả

Hệ thống đã quét thành công cây thư mục từ repository `tienndq546498-beep/tmttmm` và hiển thị tệp `services/order_service.py [python]` trong danh sách thả xuống, nhưng nội dung phân tích hiện tại vẫn đang chạy trên tệp mẫu mặc định (`app/services/payment_processor.py`) do chưa bấm nút `Nạp`.


### \*Giải thích kết quả đang hiển thị trên màn hình

Do khung mã nguồn bên dưới vẫn giữ nội dung của tệp mẫu `app/services/payment_processor.py`, báo cáo ở cột bên phải đang phản ánh cấu trúc của lớp `PaymentProcessor`:

- **Tổng thực thể AST (**`2`**) & Độ phủ (**`50%`**):** Bộ phân tích tách được 2 thực thể gồm lớp `PaymentProcessor` (đã có docstring) và phương thức `process_order` (chưa có docstring), đạt tỷ lệ bao phủ 50%.
- **Cảnh báo **`MEDIUM`** (**`PaymentProcessor.process_order`** | **`Dòng 4–9`**):** Phương thức `process_order` đã khai báo đầy đủ kiểu dữ liệu đầu vào (`str`, `float`) và kiểu trả về (`-> bool`) nên không phát sinh cảnh báo `LOW`, chỉ thiếu phần docstring mô tả mục đích hàm cùng 3 tham số `order_id`, `amount`, `currency`.
- **Độ phức tạp (**`Complexity: 3`**):** Tính từ điểm cơ sở `1` cộng thêm `1` nhánh kiểm tra `if amount <= 0` và `1` nhánh điều kiện `if currency == "VND" and amount < 1000`.

### \* Thao tác tiếp theo để nạp mã nguồn thật từ GitHub

-Bấm trực tiếp vào nút `Nạp` nằm ngay bên phải ô chọn `services/order_service.py [python]`.

-Quan sát dòng chữ xanh `Tệp:` phía trên khung nhập liệu đổi từ `app/services/payment_processor.py` sang `services/order_service.py` và nội dung bên trong cập nhật thành lớp `OrderService`.

-Bấm lại nút `Phân tích AST & Độ phủ` ở góc dưới bên trái để xem kết quả bóc tách 3 thực thể (`OrderService`, `create_order`, `cancel_order`) từ tệp vừa tải về qua GitHub API.


### Kết quả đối chiếu từ tệp GitHub thực tế

- **Đồng bộ GitHub Workspace:** Đường dẫn `Tệp: services/order_service.py` và toàn bộ nội dung lớp `OrderService` hiển thị khớp hoàn toàn với mã nguồn trên repository.
- **Bóc tách AST & Độ phủ (**`66.67%`**):** Bộ phân tích nhận diện chính xác **3 thực thể** (`OrderService`, `create_order`, `cancel_order`), ghi nhận 2 thực thể đã có docstring.
- **Khoanh vùng lỗ hổng tại **`OrderService.cancel_order`** (**`Dòng 10–13`** | **`Complexity: 2`**):** Phương thức `create_order` đạt chuẩn nên không phát sinh cảnh báo; toàn bộ thiếu sót được bắt chính xác tại `cancel_order` gồm thiếu docstring (`MEDIUM`) và thiếu kiểu dữ liệu trả về (`LOW`).
