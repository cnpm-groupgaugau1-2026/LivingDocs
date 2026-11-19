# Demo RBAC User & Permission Management Panel

**\*Kiểm tra dữ liệu thực từ PostgreSQL & Thẻ thống kê KPI**

<http://localhost:3000/admin>
![Demo Frontend](/docs/images/f13-1.png)
![Demo Frontend](/docs/images/f13-2.png)

**\*Đối chiếu Ma trận phân quyền RBAC (5 Actor)**
![Demo Frontend](/docs/images/f13-3.png)

**\*Mời thành viên mới & Kiểm thử chặn trùng Email**

-Tạo lời mời hợp lệ:
![Demo Frontend](/docs/images/f13-4.png)

-Kiểm thử trùng lặp (Negative Test):
![Demo Frontend](/docs/images/f13-5.png)
![Demo Frontend](/docs/images/f13-6.png)

**\*Tìm kiếm & Lọc đa điều kiện (Search & Filter)**

Tìm kiếm theo từ khóa
![Demo Frontend](/docs/images/f13-7.png)

Lọc theo vai trò (5 Actor):
![Demo Frontend](/docs/images/f13-8.png)

Lọc theo trạng thái:
![Demo Frontend](/docs/images/f13-9.png)

**\*Thay đổi vai trò trực tiếp & Kiểm chứng lưu bền vững**
![Demo Frontend](/docs/images/f13-10.png)
![Demo Frontend](/docs/images/f13-11.png)

**\*Đình chỉ / Kích hoạt & Chốt chặn tự bảo vệ (Guardrails)**

đình chỉ :
![Demo Frontend](/docs/images/f13-12.png)

kích hoạt lại 
![Demo Frontend](/docs/images/f13-13.png)

**\*Kiểm thử chốt chặn tự khóa / tự hạ quyền Admin (Admin Lockout Prevention):**
![Demo Frontend](/docs/images/f13-14.png)

**Kết quả:** Backend từ chối yêu cầu (`400 Bad Request`) và hiển thị cảnh báo đỏ (*"Không thể tự hạ quyền Administrator của chính mình"* / *"Không thể tự khóa tài khoản đang đăng nhập"*), đảm bảo hệ thống không bao giờ rơi vào trạng thái mất hết quản trị viên.
