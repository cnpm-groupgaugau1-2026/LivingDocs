# Demo Authentication & RBAC

## 1. Mô hình Phân quyền 5 Actor (RBAC Matrix)

Hệ thống phân chia 5 cấp độ truy cập từ thấp đến cao:

|  |  |  |
| --- | --- | --- |
| **Vai trò (Role)** | **Mô tả Actor** | **Quyền hạn tiêu biểu trên API** |
| `Developer` | Người dùng cơ bản / Writer | Tạo & sửa dự thảo tài liệu (`POST /api/v1/documents/draft`) |
| `STAFF` | Nhân viên kiểm duyệt | Review nội dung tài liệu (`POST /api/v1/workflow/review`) |
| `MANAGER` | Quản lý dự án | Phê duyệt xuất bản tài liệu (`POST /api/v1/workflow/approve`) |
| `TECH_LEAD` | Trưởng nhóm kỹ thuật | Xem dashboard quản trị hệ thống (`GET /api/v1/governance/dashboard`) |
| `ADMIN` | Quản trị viên toàn hệ thống | Quản lý người dùng & cấp quyền (`GET /api/v1/admin/users`) |

![Demo Frontend](../docs/images/anh-14.png)
**2 .Kịch bản Demo Checkpoints trên Swagger UI**

1. Đăng ký & Đăng nhập lấy Bearer Token

-Gọi API `POST /api/v1/auth/register` để tạo tài khoản mới với vai trò mong muốn
![Demo Frontend](../docs/images/anh-15.png)

Gọi API `POST /api/v1/auth/login` với thông tin tài khoản vừa đăng ký.
![Demo Frontend](../docs/images/anh-16.png)

Sao chép chuỗi `access_token` trong kết quả phản hồi JSON

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4ZDQwYzFlNC1iNjZjLTRhMjUtOGZlYy1hNmU4ZDEyMmMxMDkiLCJyb2xlIjoiQURNSU5JU1RSQVRPUiIsImV4cCI6MTc5NDUwODI0M30.7XKuVxkl8j63_LKOznFLSSt-IU5of1g4T3mSxjeuFMI
```

1. Ủy quyền (Authorize) trên Swagger UI
   ![Demo Frontend](../docs/images/anh-17.png)

1. Kiểm tra Ma trận Quyền hạn (200 OK vs 403 Forbidden)
2. ![Demo Frontend](../docs/images/anh-18.png)

3\. Kiểm tra trường hợp Chặn truy cập trái quyền (`403 Forbidden`)
![Demo Frontend](../docs/images/anh-19.png)
![Demo Frontend](../docs/images/anh-20.png)
