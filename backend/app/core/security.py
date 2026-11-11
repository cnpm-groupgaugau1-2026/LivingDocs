from datetime import datetime, timedelta
from typing import Optional, List
import bcrypt
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.config import settings

# Cấu hình OAuth2 Scheme để Swagger UI nhận diện nút Authorize
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Kiểm tra mật khẩu thô với chuỗi băm."""
    pwd_bytes = plain_password.encode('utf-8')[:72]
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(pwd_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    """Tạo chuỗi băm bcrypt từ mật khẩu (giới hạn tối đa 72 bytes)."""
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire_minutes = getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=expire_minutes))
    to_encode.update({"exp": expire})
    algorithm = getattr(settings, "ALGORITHM", "HS256")
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=algorithm)


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Giải mã Token từ Header Request và trích xuất thông tin User & Role."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token không hợp lệ hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        algorithm = getattr(settings, "ALGORITHM", "HS256")
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[algorithm]
        )
        username: str = payload.get("sub")
        role: str = payload.get("role")
        
        if username is None or role is None:
            raise credentials_exception
            
        return {"username": username, "role": role}
    except JWTError:
        raise credentials_exception


class RoleChecker:
    """Dependency class kiểm tra xem Role của User có nằm trong danh sách cho phép hay không."""
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Quyền hạn không đủ. Yêu cầu vai trò thuộc: {self.allowed_roles}"
            )
        return current_user