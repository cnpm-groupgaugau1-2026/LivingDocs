import httpx
from fastapi import HTTPException, status
from app.core.config import settings

GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_API = "https://api.github.com/user"
GITHUB_EMAILS_API = "https://api.github.com/user/emails"

async def exchange_code_for_token(code: str) -> str:
    """Đổi authorization code lấy GitHub access token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_REDIRECT_URI,
            },
        )
        data = response.json()
        if "access_token" not in data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"GitHub OAuth error: {data.get('error_description', 'Invalid code')}"
            )
        return data["access_token"]

async def get_github_user_profile(github_token: str) -> dict:
    """Lấy thông tin profile người dùng từ GitHub API."""
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
        }
        profile_res = await client.get(GITHUB_USER_API, headers=headers)
        if profile_res.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Khởi tạo thông tin GitHub thất bại"
            )
        profile = profile_res.json()

        # Lấy email chính nếu profile không để công khai email
        if not profile.get("email"):
            emails_res = await client.get(GITHUB_EMAILS_API, headers=headers)
            if emails_res.status_code == 200:
                emails = emails_res.json()
                primary_email = next((e["email"] for e in emails if e.get("primary")), None)
                profile["email"] = primary_email

        return profile
