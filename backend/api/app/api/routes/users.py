"""User management handlers — admin-only account create/list/delete."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_db_readonly, require_admin
from app.api.openapi import (
    CONFLICT,
    FORBIDDEN,
    NOT_FOUND,
    UNAUTHORIZED,
    VALIDATION_ERROR,
)
from app.models import Admin
from app.schemas import UserCreateIn, UserOut
from app.services import (
    CannotDeleteSelfError,
    LastAdminError,
    UsernameTakenError,
    UserNotFoundError,
    UserService,
)

router = APIRouter(tags=["Users"], responses={401: UNAUTHORIZED, 403: FORBIDDEN})


@router.get(
    "/users",
    response_model=list[UserOut],
    summary="List users",
    description=(
        "Every login account with its role. Admin-only; write endpoints that "
        "use this list require the same role."
    ),
)
def list_users(
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> list[UserOut]:
    return [UserOut.model_validate(account) for account in UserService(session).list()]


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description=(
        "Creates a login account. `role=admin` grants full management; "
        "`role=viewer` can only read. Duplicate usernames return `409`."
    ),
    responses={409: CONFLICT, 422: VALIDATION_ERROR},
)
def create_user(
    payload: UserCreateIn,
    _admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> UserOut:
    try:
        account = UserService(session).create(payload)
    except UsernameTakenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="این نام کاربری قبلاً ثبت شده است",
        ) from None
    return UserOut.model_validate(account)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    description=(
        "Deletes the account and every active session it owns. An admin cannot "
        "delete their own account, and the last admin cannot be removed."
    ),
    responses={
        204: {"description": "Account deleted."},
        404: NOT_FOUND,
        409: CONFLICT,
        422: VALIDATION_ERROR,
    },
)
def delete_user(
    user_id: int,
    admin: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> Response:
    try:
        UserService(session).delete(user_id, actor_id=admin.id)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="کاربر پیدا نشد"
        ) from None
    except CannotDeleteSelfError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="حساب کاربری خودتان را نمی‌توانید حذف کنید",
        ) from None
    except LastAdminError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="حداقل یک مدیر باید در سیستم باقی بماند",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
