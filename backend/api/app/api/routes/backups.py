"""Owner-only backup settings, archive operations, and direct restore.

Queued work is executed by the background worker, so every mutating endpoint
returns immediately (``202``) except an upload, which is verified in-request.
"""

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_db_readonly, require_owner
from app.api.openapi import (
    CONFLICT,
    FORBIDDEN,
    NOT_FOUND,
    UNAUTHORIZED,
    VALIDATION_ERROR,
)
from app.models import Admin
from app.schemas import (
    BackupOut,
    BackupSettingsOut,
    BackupSettingsUpdateIn,
)
from app.services import (
    BackupRequestError,
    BackupService,
    BackupUnavailableError,
    InvalidArchiveError,
    UploadTooLargeError,
)

router = APIRouter(tags=["Backups"], responses={401: UNAUTHORIZED, 403: FORBIDDEN})

_REJECTION_MESSAGES = {
    "not_found": "پشتیبان یافت نشد",
    "not_verified": "فقط پشتیبان تأیید‌شده قابل بازیابی است",
    "pending_exists": "کار دیگری در صف اجرا است",
    "file_missing": "فایل پشتیبان در سرور موجود نیست",
    "backup_pending": "تا پایان پشتیبان‌گیری جاری، بازیابی امکان‌پذیر نیست",
    "backup_running": "این پشتیبان در حال اجرا است و حذف آن ممکن نیست",
    "restore_running": "بازیابی دیگری در حال اجرا است",
}
_UNAVAILABLE_MESSAGES = {
    "tools_unavailable": "ابزارهای PostgreSQL روی این سرور نصب نیستند",
    "storage_unavailable": "پوشهٔ ذخیرهٔ پشتیبان در دسترس یا قابل نوشتن نیست",
}


def _rejection(error: BackupRequestError) -> HTTPException:
    code = status.HTTP_404_NOT_FOUND if error.reason == "not_found" else status.HTTP_409_CONFLICT
    return HTTPException(
        status_code=code,
        detail=_REJECTION_MESSAGES.get(error.reason, "درخواست مجاز نیست"),
    )


def _unavailable(error: BackupUnavailableError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=_UNAVAILABLE_MESSAGES.get(error.reason, "پشتیبان‌گیری در دسترس نیست"),
    )


def _backup_out(record: object) -> BackupOut:
    return BackupOut.model_validate(record)


# ── settings ─────────────────────────────────────────────────


@router.get(
    "/settings/backup",
    response_model=BackupSettingsOut,
    summary="Read backup settings",
    description=(
        "Owner-only backup schedule settings and local tool availability. "
        "Retention and verification are fixed policy."
    ),
)
def get_backup_settings(
    _owner: Admin = Depends(require_owner),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> BackupSettingsOut:
    return BackupSettingsOut.model_validate(BackupService(session).settings_view())


@router.put(
    "/settings/backup",
    response_model=BackupSettingsOut,
    summary="Update backup settings",
    description="Enables or pauses automatic backups and changes their interval.",
    responses={422: VALIDATION_ERROR},
)
def update_backup_settings(
    payload: BackupSettingsUpdateIn,
    _owner: Admin = Depends(require_owner),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> BackupSettingsOut:
    settings = BackupService(session).update_settings(
        enabled=payload.enabled, interval_minutes=payload.interval_minutes
    )
    return BackupSettingsOut.model_validate(settings)


# ── archives ─────────────────────────────────────────────────


@router.get(
    "/backups",
    response_model=list[BackupOut],
    summary="List backup archives",
    description=(
        "Owner-only metadata for recent archives, including file availability. "
        "Never includes credentials or filesystem paths."
    ),
)
def list_backups(
    _owner: Admin = Depends(require_owner),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> list[BackupOut]:
    return [BackupOut.model_validate(row) for row in BackupService(session).list_backups()]


@router.post(
    "/backups",
    response_model=BackupOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue a manual backup",
    description=(
        "Queues a full logical dump of the database. The background worker runs "
        "it within seconds; poll `GET /backups` for the result."
    ),
    responses={409: CONFLICT},
)
def queue_backup(
    _owner: Admin = Depends(require_owner),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> BackupOut:
    try:
        record = BackupService(session).queue_manual()
    except BackupRequestError as error:
        raise _rejection(error) from None
    except BackupUnavailableError as error:
        raise _unavailable(error) from None
    return _backup_out(BackupService.backup_view(record))


@router.post(
    "/backups/upload",
    response_model=BackupOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a backup archive",
    description=(
        "Accepts a verified pg_dump custom-format archive, stores it locally, and "
        "makes it available for a data restore. The file never touches the database."
    ),
    responses={
        409: CONFLICT,
        413: {"description": "Upload exceeds the configured cap."},
        422: VALIDATION_ERROR,
    },
)
def upload_backup(
    file: UploadFile = File(..., description="`pg_dump --format=custom` archive"),  # noqa: B008
    _owner: Admin = Depends(require_owner),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> BackupOut:
    try:
        record = BackupService(session).save_upload(file.file)
    except UploadTooLargeError:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="حجم فایل از سقف مجاز بیشتر است",
        ) from None
    except InvalidArchiveError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="فایل، آرشیو معتبر pg_dump نیست",
        ) from None
    except BackupUnavailableError as error:
        raise _unavailable(error) from None
    finally:
        file.file.close()
    return _backup_out(BackupService.backup_view(record))


@router.get(
    "/backups/{backup_id}/download",
    summary="Download a backup archive",
    description="Owner-only download of the stored dump. Expired archives return 404.",
    response_class=FileResponse,
    responses={404: NOT_FOUND, 422: VALIDATION_ERROR},
)
def download_backup(
    backup_id: int,
    _owner: Admin = Depends(require_owner),  # noqa: B008
    session: Session = Depends(get_db_readonly),  # noqa: B008
) -> FileResponse:
    service = BackupService(session)
    path = service.download_path(backup_id)
    name = service.archive_name(backup_id)
    if path is None or name is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پشتیبان یافت نشد")
    return FileResponse(path, media_type="application/octet-stream", filename=name)


@router.delete(
    "/backups/{backup_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a backup archive",
    description=(
        "Owner-only permanent removal of one stored archive and its metadata. "
        "Archives with an active restore or still running are kept."
    ),
    responses={404: NOT_FOUND, 409: CONFLICT, 422: VALIDATION_ERROR},
)
def delete_backup(
    backup_id: int,
    _owner: Admin = Depends(require_owner),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> Response:
    try:
        BackupService(session).delete_backup(backup_id)
    except BackupRequestError as error:
        raise _rejection(error) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── direct restore ───────────────────────────────────────────


@router.post(
    "/backups/{backup_id}/restore",
    response_model=BackupOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Restore an archive",
    description=(
        "Owner-only, direct trigger of a transactional data restore from one verified, "
        "locally stored archive. The owner confirms in the client before calling this "
        "endpoint. Shop data is replaced; accounts, sessions, and backup history are "
        "preserved. A verified pre-restore archive is created first and the load is "
        "rolled back on failure. Poll `GET /backups` for `restore_status`."
    ),
    responses={404: NOT_FOUND, 409: CONFLICT, 422: VALIDATION_ERROR},
)
def restore_backup(
    backup_id: int,
    _owner: Admin = Depends(require_owner),  # noqa: B008
    session: Session = Depends(get_db),  # noqa: B008
) -> BackupOut:
    try:
        record = BackupService(session).start_restore(backup_id)
    except BackupRequestError as error:
        raise _rejection(error) from None
    return _backup_out(BackupService.backup_view(record))
