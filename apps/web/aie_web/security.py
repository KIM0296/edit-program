"""CSRF tokens (double-submit cookie) and request scheme handling.

Every state-changing form carries ``csrf_token``; the POST handler compares it
in constant time with the ``aie_csrf`` cookie (HttpOnly, SameSite=Strict). A
present ``Origin`` header must also name the request's own host. Cookies are
marked ``Secure`` when the request is HTTPS — taken from ``X-Forwarded-Proto``
only when ``trust_proxy`` is on (behind a tunnel / reverse proxy).
"""

import hmac
import re
import secrets
from urllib.parse import urlsplit

from starlette.requests import Request

from .pipeline import PipelineError
from .store import Settings

CSRF_COOKIE = "aie_csrf"
TRIAL_COOKIE = "aie_trial"
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,64}$")


class CsrfRefused(PipelineError):
    """Missing or invalid CSRF token / foreign Origin (HTTP 403)."""


def new_token() -> str:
    return secrets.token_urlsafe(32)


def cookie_token(request: Request) -> str | None:
    value = request.cookies.get(CSRF_COOKIE)
    return value if value is not None and _TOKEN_RE.match(value) else None


def is_https(request: Request, settings: Settings) -> bool:
    if settings.secure_cookies or request.url.scheme == "https":
        return True
    if settings.trust_proxy:
        forwarded = request.headers.get("x-forwarded-proto", "")
        return forwarded.split(",")[0].strip().lower() == "https"
    return False


def check_csrf(request: Request, form_token: str) -> None:
    expected = cookie_token(request)
    if expected is None or not form_token or not hmac.compare_digest(expected, form_token):
        raise CsrfRefused(
            "보안 확인(CSRF 토큰)에 실패했습니다. 페이지를 새로 고친 뒤 다시 시도하세요.",
            ("CSRF_INVALID",),
        )
    origin = request.headers.get("origin")
    if origin is not None and origin != "null":
        host = request.headers.get("host", "")
        if urlsplit(origin).netloc.lower() != host.lower():
            raise CsrfRefused("다른 사이트에서 보낸 요청은 받지 않습니다.", ("ORIGIN_MISMATCH",))
    elif origin == "null":
        raise CsrfRefused("다른 사이트에서 보낸 요청은 받지 않습니다.", ("ORIGIN_MISMATCH",))
