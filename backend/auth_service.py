import time
import httpx
from fastapi import HTTPException, status
from config import settings

class OAuth42:
    def __init__(self):
        self.client_id = settings.FT_CLIENT_ID
        self.client_secret = settings.FT_CLIENT_SECRET
        self.redirect_uri = settings.FT_REDIRECT_URI
        self.base_url = "https://api.intra.42.fr"
        self._app_token: str | None = None
        self._app_token_expiry: float = 0.0

    async def get_app_token(self) -> str | None:
        """Client-credentials token for server-to-server 42 API calls."""
        now = time.time()
        if self._app_token and now < self._app_token_expiry - 60:
            return self._app_token
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/oauth/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "scope": "public",
                    },
                )
            if response.status_code != 200:
                print(f"⚠️  42 client_credentials failed: {response.status_code} {response.text}")
                return None
            data = response.json()
            self._app_token = data.get("access_token")
            self._app_token_expiry = now + int(data.get("expires_in", 7200))
            return self._app_token
        except Exception as e:
            print(f"⚠️  42 app token error: {e}")
            return None

    async def get_user_coalitions(self, user_42_ref) -> list:
        """Fetch coalitions for a 42 user (numeric id or login). Returns [] on failure."""
        token = await self.get_app_token()
        if not token or not user_42_ref:
            return []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/v2/users/{user_42_ref}/coalitions",
                    headers={"Authorization": f"Bearer {token}"},
                )
            if response.status_code != 200:
                print(f"⚠️  42 coalitions fetch failed for {user_42_ref}: {response.status_code}")
                return []
            return response.json() or []
        except Exception as e:
            print(f"⚠️  42 coalitions error for {user_42_ref}: {e}")
            return []

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
