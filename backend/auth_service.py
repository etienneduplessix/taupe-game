import httpx
from fastapi import HTTPException, status
from config import settings

class OAuth42:
    def __init__(self):
        self.client_id = settings.FT_CLIENT_ID
        self.client_secret = settings.FT_CLIENT_SECRET
        self.redirect_uri = settings.FT_REDIRECT_URI
        self.base_url = "https://api.intra.42.fr"

    async def get_authorization_url(self) -> str:
        # We use a standard OAuth2 authorization URL
        # Using a dummy state for now, in production we should use a random string
        return f"{self.base_url}/oauth/authorize?response_type=code&client_id={self.client_id}&redirect_uri={self.redirect_uri}&scope=public"

    async def get_access_token(self, code: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "code": code,
                },
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Failed to obtain access token: {response.text}"
                )
            return response.json().get("access_token")

    async def get_user_info(self, token: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v2/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Failed to fetch user info: {response.text}"
                )
            return response.json()

oauth_42 = OAuth42()
