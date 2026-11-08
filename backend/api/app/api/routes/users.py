"""User management handlers — management (owner/admin) account routes."""

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
    CannotDeleteOwnerError,
    CannotDeleteSelfError,
    ForbiddenRoleError,
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
        "The owner sees every account; an admin sees only viewer accounts. "
        "Write endpoints use the same visibility and permission rules."
    ),
)
def list_users(
    actor: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> list[UserOut]:
    return [UserOut.model_validate(account) for account in UserService(session).list(actor=actor)]


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description=(
        "Creates a login account. The owner may create `admin` or `viewer` "
        "accounts; an admin may create viewers only. Duplicate usernames "
        "return `409`."
    ),
    responses={403: FORBIDDEN, 409: CONFLICT, 422: VALIDATION_ERROR},
)
def create_user(
    payload: UserCreateIn,
    actor: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> UserOut:
    try:
        account = UserService(session).create(payload, actor=actor)
    except ForbiddenRoleError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="فقط مالک می‌تواند مدیر جدید بسازد",
        ) from None
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
        "Deletes the account and every active session it owns. The owner may "
        "delete admins and viewers; an admin may delete viewers only. No one "
        "can delete their own account and the env-managed owner cannot be "
        "removed. The last admin cannot be deleted."
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
    actor: Admin = Depends(require_admin),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> Response:
    try:
        UserService(session).delete(user_id, actor=actor)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="کاربر پیدا نشد"
        ) from None
    except CannotDeleteSelfError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="حساب کاربری خودتان را نمی‌توانید حذف کنید",
        ) from None
    except CannotDeleteOwnerError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="حساب مالک با متغیرهای محیطی مدیریت می‌شود و حذف نمی‌شود",
        ) from None
    except LastAdminError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="حداقل یک مدیر باید در سیستم باقی بماند",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
