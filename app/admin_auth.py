
import base64
import binascii
import hmac
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class AdminAuthMiddleware(BaseHTTPMiddleware):
    PUBLIC_PATHS = {
        "/health",
        "/webhooks/elevenlabs",
    }

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        username = os.getenv("TORRES_ADMIN_USERNAME", "")
        password = os.getenv("TORRES_ADMIN_PASSWORD", "")

        if not username or not password:
            return JSONResponse(
                {"detail": "Admin authentication is not configured"},
                status_code=503,
            )

        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")

        if scheme.lower() != "basic" or not token:
            return self.unauthorized()

        try:
            decoded = base64.b64decode(token, validate=True).decode("utf-8")
            supplied_username, separator, supplied_password = decoded.partition(":")
        except (ValueError, UnicodeDecodeError, binascii.Error):
            return self.unauthorized()

        valid_username = hmac.compare_digest(
            supplied_username.encode(), username.encode()
        )
        valid_password = hmac.compare_digest(
            supplied_password.encode(), password.encode()
        )

        if not separator or not valid_username or not valid_password:
            return self.unauthorized()

        return await call_next(request)

    @staticmethod
    def unauthorized():
        return Response(
            content='{"detail":"Authentication required"}',
            status_code=401,
            media_type="application/json",
            headers={"WWW-Authenticate": 'Basic realm="TORRES AI Admin"'},
        )
