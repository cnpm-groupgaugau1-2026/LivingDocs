@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    # Tìm user theo email HOẶC username
    user = db.query(User).filter(
        (User.email == form_data.username) | (User.username == form_data.username)
    ).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email/Username hoặc mật khẩu không chính xác!"
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role.value if hasattr(user.role, 'value') else user.role}
    )
    return {"access_token": access_token, "token_type": "bearer"}
    from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User, Role  # Nhập model User của bạn
from app.core.config import settings
from app.core.security import create_access_token
from app.services.github_service import exchange_code_for_token, get_github_user_profile

router = APIRouter()

@router.get("/auth/github/login")
def github_login():
    """Chuyển hướng user đến trang xác thực OAuth của GitHub."""
    github_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={settings.GITHUB_RsEDIRECT_URI}"
        f"&scope=user:email%20repo"
    )
    return RedirectResponse(url=github_url)


@router.get("/auth/github/callback")
async def github_callback(code: str, db: Session = Depends(get_db)):
    """Xử lý Authorization Code từ GitHub và cấp JWT Session."""
    # 1. Đổi code lấy Token
    github_token = await exchange_code_for_token(code)
    
    # 2. Lấy thông tin User từ GitHub
    gh_profile = await get_github_user_profile(github_token)
    email = gh_profile.get("email")
    username = gh_profile.get("login")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Tài khoản GitHub không cung cấp Email khả dụng."
        )

    # 3. Liên kết hoặc tạo mới User trong DB
    user = db.query(User).filter((User.email == email) | (User.username == username)).first()
    
    if not user:
        user = User(
            email=email,
            username=username,
            full_name=gh_profile.get("name") or username,
            hashed_password="",  # User SSO không có password local
            role=Role.DEVELOPER,  # Mặc định gán vai trò DEVELOPER
            github_token=github_token
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Cập nhật token GitHub mới nhất
        user.github_token = github_token
        db.commit()

    # 4. Tạo JWT token nội bộ cho hệ thống
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role.value if hasattr(user.role, 'value') else user.role}
    )

    # 5. Redirect về Frontend kèm Token
    redirect_url = f"{settings.FRONTEND_URL}/auth/success?token={access_token}"
    return RedirectResponse(url=redirect_url)