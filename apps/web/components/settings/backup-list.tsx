"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Download, Play, RotateCcw, Trash2, Upload } from "lucide-react"

import { Badge } from "@workspace/ui/primitives/badge"
import { BusyLabel } from "@workspace/ui/primitives/busy-label"
import { Button } from "@workspace/ui/primitives/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/primitives/table"
import { formatPersianDateTime } from "@workspace/ui/lib/date"
import { formatPersianNumber, toPersianDigits } from "@workspace/ui/lib/number"

import {
  api,
  BACKUP_POLL_MS,
  type BackupRecord,
  type BackupStatus,
  type BackupVerification,
  type RestoreStatus,
} from "@/lib/api"
import { downloadFile } from "@/lib/download"
import { backupErrorLabel, BACKUP_KIND_LABELS } from "./backup-labels"
import { BackupDeleteDialog } from "@/components/settings/backup-delete-dialog"
import { BackupRestoreDialog } from "@/components/settings/backup-restore-dialog"

const STATUS: Record<
  BackupStatus,
  { label: string; variant: "warning" | "success" | "destructive" | "outline" }
> = {
  queued: { label: "در صف", variant: "outline" },
  running: { label: "در حال اجرا", variant: "warning" },
  completed: { label: "کامل", variant: "success" },
  failed: { label: "ناموفق", variant: "destructive" },
}

const VERIFICATION: Record<
  BackupVerification,
  { label: string; variant: "outline" | "success" | "destructive" }
> = {
  pending: { label: "در انتظار", variant: "outline" },
  verified: { label: "تأیید شد", variant: "success" },
  failed: { label: "تأیید ناموفق", variant: "destructive" },
}

const RESTORE: Record<
  RestoreStatus,
  { label: string; variant: "warning" | "success" | "destructive" | "outline" }
> = {
  queued: { label: "بازیابی در صف", variant: "outline" },
  running: { label: "در حال بازیابی", variant: "warning" },
  completed: { label: "بازیابی شد", variant: "success" },
  failed: { label: "بازیابی ناموفق", variant: "destructive" },
}

function sizeLabel(size: number | null): string {
  if (size === null) return "—"
  if (size < 1_048_576) {
    return `${formatPersianNumber(Math.max(1, Math.round(size / 1024)))} کیلوبایت`
  }
  return `${formatPersianNumber(Math.round(size / 1_048_576))} مگابایت`
}

function restoreInFlight(backup: BackupRecord): boolean {
  return (
    backup.restore_status === "queued" || backup.restore_status === "running"
  )
}

function isWorkInFlight(backups: BackupRecord[]): boolean {
  return backups.some(
    (backup) =>
      backup.status === "queued" ||
      backup.status === "running" ||
      restoreInFlight(backup)
  )
}

type BackupView = {
  status: (typeof STATUS)[BackupStatus]
  verification: (typeof VERIFICATION)[BackupVerification]
  restore: (typeof RESTORE)[RestoreStatus] | null
  errorLabel: string | null
  restoreErrorLabel: string | null
  kindLabel: string
  size: string
  downloadable: boolean
  restoreBlocked: boolean
  deleteBlocked: boolean
}

function backupView(
  backup: BackupRecord,
  backupPending: boolean,
  restorePending: boolean
): BackupView {
  return {
    status: STATUS[backup.status],
    verification: VERIFICATION[backup.verification],
    restore: backup.restore_status ? RESTORE[backup.restore_status] : null,
    errorLabel: backupErrorLabel(backup.error_code),
    restoreErrorLabel: backupErrorLabel(backup.restore_error_code),
    kindLabel: BACKUP_KIND_LABELS[backup.kind] ?? backup.kind,
    size: sizeLabel(backup.size_bytes),
    downloadable: backup.downloadable,
    restoreBlocked:
      backup.status !== "completed" ||
      backup.verification !== "verified" ||
      !backup.downloadable ||
      backupPending ||
      restorePending,
    deleteBlocked:
      backup.status === "queued" ||
      backup.status === "running" ||
      restoreInFlight(backup) ||
      backupPending ||
      restorePending,
  }
}

type BackupActionsProps = {
  view: BackupView
  downloading: boolean
  restoring: boolean
  deleting: boolean
  onDownload: () => void
  onRestore: () => void
  onDelete: () => void
}

/** The same three actions in the desktop row and the mobile card. */
function BackupActions({
  view,
  downloading,
  restoring,
  deleting,
  onDownload,
  onRestore,
  onDelete,
}: BackupActionsProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        className="h-11 gap-2 md:h-9"
        disabled={!view.downloadable || downloading}
        aria-busy={downloading}
        onClick={onDownload}
      >
        دانلود
        <Download className="size-4" />
      </Button>
      <Button
        variant="outline"
        size="sm"
        className="h-11 gap-2 md:h-9"
        disabled={view.restoreBlocked || restoring}
        aria-busy={restoring}
        onClick={onRestore}
      >
        بازیابی
        <RotateCcw className="size-4" />
      </Button>
      <Button
        variant="destructive"
        size="sm"
        className="h-11 gap-2 md:h-9"
        disabled={view.deleteBlocked || deleting}
        aria-busy={deleting}
        onClick={onDelete}
      >
        حذف
        <Trash2 className="size-4" />
      </Button>
    </div>
  )
}

function BackupErrors({ view }: { view: BackupView }) {
  return (
    <>
      {view.errorLabel ? (
        <p
          className="mt-1 max-w-40 truncate text-xs text-destructive"
          title={toPersianDigits(view.errorLabel)}
        >
          {toPersianDigits(view.errorLabel)}
        </p>
      ) : null}
      {view.restore ? (
        <Badge variant={view.restore.variant} className="mt-1">
          {view.restore.label}
        </Badge>
      ) : null}
      {view.restoreErrorLabel ? (
        <p
          className="mt-1 max-w-40 truncate text-xs text-destructive"
          title={toPersianDigits(view.restoreErrorLabel)}
        >
          {toPersianDigits(view.restoreErrorLabel)}
        </p>
      ) : null}
    </>
  )
}

/** Archive list and direct owner actions: backup, upload, download, restore, delete. */
export function BackupList() {
  const [backups, setBackups] = useState<BackupRecord[]>([])
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState<"backup" | "upload" | null>(null)
  const [downloading, setDownloading] = useState<number | null>(null)
  const [deleting, setDeleting] = useState<number | null>(null)
  const [restoring, setRestoring] = useState<number | null>(null)
  const [restoreTarget, setRestoreTarget] = useState<BackupRecord | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<BackupRecord | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const fetchBackups = useCallback(async () => {
    setBackups(await api.backups())
  }, [])

  useEffect(() => {
    let cancelled = false
    api
      .backups()
      .then((rows) => {
        if (!cancelled) {
          setBackups(rows)
          setLoaded(true)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "خطایی رخ داد.")
          setLoaded(true)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Worker progress is asynchronous, so poll only while something is running.
  const inFlight = isWorkInFlight(backups)
  useEffect(() => {
    if (!inFlight) return
    const timer = window.setInterval(() => {
      void fetchBackups().catch(() => {
        // A transient poll failure must not replace the visible list.
      })
    }, BACKUP_POLL_MS)
    return () => window.clearInterval(timer)
  }, [inFlight, fetchBackups])

  const backupPending = backups.some(
    (backup) => backup.status === "queued" || backup.status === "running"
  )
  const restorePending = backups.some(restoreInFlight)

  function fail(err: unknown) {
    setError(err instanceof Error ? err.message : "خطایی رخ داد.")
  }

  function openRestore(backup: BackupRecord) {
    setError(null)
    setNotice(null)
    setRestoreTarget(backup)
  }

  function openDelete(backup: BackupRecord) {
    setError(null)
    setNotice(null)
    setDeleteTarget(backup)
  }

  async function startBackup() {
    setBusy("backup")
    setError(null)
    setNotice(null)
    try {
      await api.queueBackup()
      await fetchBackups()
      setNotice("نسخه پشتیبان در صف قرار گرفت.")
    } catch (err: unknown) {
      fail(err)
    } finally {
      setBusy(null)
    }
  }

  async function upload(file: File) {
    setBusy("upload")
    setError(null)
    setNotice(null)
    try {
      await api.uploadBackup(file)
      await fetchBackups()
      setNotice("فایل تأیید شد و آماده بازیابی است.")
    } catch (err: unknown) {
      fail(err)
    } finally {
      setBusy(null)
    }
  }

  async function download(backup: BackupRecord) {
    setDownloading(backup.id)
    setError(null)
    try {
      await downloadFile(
        api.backupDownloadUrl(backup.id),
        `charsooq-backup-${backup.id}.dump`
      )
    } catch (err: unknown) {
      fail(err)
    } finally {
      setDownloading(null)
    }
  }

  async function remove(target: BackupRecord) {
    setDeleting(target.id)
    setError(null)
    setNotice(null)
    try {
      await api.deleteBackup(target.id)
      setDeleteTarget(null)
      await fetchBackups()
      setNotice("نسخه پشتیبان حذف شد.")
    } catch (err: unknown) {
      fail(err)
    } finally {
      setDeleting(null)
    }
  }

  async function restore(target: BackupRecord) {
    setRestoring(target.id)
    setError(null)
    setNotice(null)
    try {
      await api.restoreBackup(target.id)
      setRestoreTarget(null)
      await fetchBackups()
      setNotice("بازیابی آغاز شد.")
    } catch (err: unknown) {
      fail(err)
    } finally {
      setRestoring(null)
    }
  }

  if (!loaded) {
    return (
      <div
        className="h-24 animate-pulse rounded-2xl bg-muted"
        aria-label="در حال بارگذاری"
      />
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          className="h-11 gap-2 md:h-9"
          onClick={() => void startBackup()}
          disabled={busy !== null || backupPending || restorePending}
          aria-busy={busy === "backup"}
        >
          <BusyLabel
            busy={busy === "backup"}
            idle="ساخت نسخه"
            busyLabel="در حال ثبت…"
            spinner
          />
          {busy === "backup" ? null : <Play className="size-4" />}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="h-11 gap-2 md:h-9"
          onClick={() => fileInput.current?.click()}
          disabled={busy !== null || backupPending || restorePending}
          aria-busy={busy === "upload"}
        >
          <BusyLabel
            busy={busy === "upload"}
            idle="بارگذاری نسخه"
            busyLabel="در حال بارگذاری…"
            spinner
          />
          {busy === "upload" ? null : <Upload className="size-4" />}
        </Button>
        <input
          ref={fileInput}
          type="file"
          accept=".dump,.backup,.tar,application/octet-stream"
          className="sr-only"
          aria-label="انتخاب فایل پشتیبان"
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = ""
            if (file) void upload(file)
          }}
        />
      </div>

      {backups.length === 0 ? (
        <p className="text-sm text-muted-foreground">نسخه‌ای ثبت نشده است.</p>
      ) : (
        <>
          <div className="hidden md:block">
            <Table className="min-w-[56rem]">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-72">اقدامات</TableHead>
                  <TableHead className="w-52">زمان ساخت</TableHead>
                  <TableHead className="w-24">نوع</TableHead>
                  <TableHead className="w-28">حجم</TableHead>
                  <TableHead className="w-36">وضعیت</TableHead>
                  <TableHead className="w-32">تأیید</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {backups.map((backup) => {
                  const view = backupView(backup, backupPending, restorePending)
                  return (
                    <TableRow key={backup.id}>
                      <TableCell>
                        <BackupActions
                          view={view}
                          downloading={downloading === backup.id}
                          restoring={restoring === backup.id}
                          deleting={deleting === backup.id}
                          onDownload={() => void download(backup)}
                          onRestore={() => openRestore(backup)}
                          onDelete={() => openDelete(backup)}
                        />
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        {formatPersianDateTime(backup.created_at)}
                      </TableCell>
                      <TableCell>{view.kindLabel}</TableCell>
                      <TableCell className="whitespace-nowrap">
                        {view.size}
                      </TableCell>
                      <TableCell>
                        <Badge variant={view.status.variant}>
                          {view.status.label}
                        </Badge>
                        <BackupErrors view={view} />
                      </TableCell>
                      <TableCell>
                        <Badge variant={view.verification.variant}>
                          {view.verification.label}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>

          <ul className="flex flex-col gap-2.5 md:hidden">
            {backups.map((backup) => {
              const view = backupView(backup, backupPending, restorePending)
              return (
                <li
                  key={backup.id}
                  className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-3 sm:p-4"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <span className="text-[11px] text-muted-foreground">
                        زمان ساخت
                      </span>
                      <span className="text-sm font-semibold whitespace-nowrap">
                        {formatPersianDateTime(backup.created_at)}
                      </span>
                    </div>
                    <Badge variant={view.status.variant}>
                      {view.status.label}
                    </Badge>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-muted-foreground">
                    <span>{view.kindLabel}</span>
                    <span>{view.size}</span>
                    <Badge variant={view.verification.variant}>
                      {view.verification.label}
                    </Badge>
                  </div>
                  <BackupErrors view={view} />
                  <BackupActions
                    view={view}
                    downloading={downloading === backup.id}
                    restoring={restoring === backup.id}
                    deleting={deleting === backup.id}
                    onDownload={() => void download(backup)}
                    onRestore={() => openRestore(backup)}
                    onDelete={() => openDelete(backup)}
                  />
                </li>
              )
            })}
          </ul>
        </>
      )}

      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {toPersianDigits(error)}
        </p>
      ) : null}
      {notice ? (
        <p role="status" className="text-sm text-success">
          {toPersianDigits(notice)}
        </p>
      ) : null}

      <BackupRestoreDialog
        backup={restoreTarget}
        open={restoreTarget !== null}
        onOpenChange={(open) => {
          if (!open) setRestoreTarget(null)
        }}
        onConfirm={() => {
          if (restoreTarget !== null) void restore(restoreTarget)
        }}
        pending={restoring !== null}
        error={error}
      />
      <BackupDeleteDialog
        backup={deleteTarget}
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
        onConfirm={() => {
          if (deleteTarget !== null) void remove(deleteTarget)
        }}
        pending={deleting !== null}
        error={error}
      />
    </div>
  )
}
