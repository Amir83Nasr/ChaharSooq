"""Shared error helpers — Persian messages, fixed envelope."""

from fastapi import HTTPException, status

LOGIN_REQUIRED = "نیاز به ورود است"


def unauthorized(detail: str = LOGIN_REQUIRED) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
