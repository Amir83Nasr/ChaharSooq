# Rollback — ChaharSooq Production (Blue-Green)

Status: **procedure and design only**. No rollback or deployment has been executed against
`market-linux`. No volume, database, image, or Production network setting has been removed or changed
by this document.

Related: [release-management.md](release-management.md) ·
[production-runbook.md](production-runbook.md) ·
[cicd-blue-green-test-report.md](cicd-blue-green-test-report.md) ·
[ADR 017](../adr/017-blue-green-deployment.md) ·
[ADR 014](../adr/014-production-backup-and-recovery.md) ·
[backup-and-recovery.md](backup-and-recovery.md)

## 1. What rollback means in this stack

- **Code/slot rollback:** return traffic to the previously active Blue-Green slot (or redeploy the
  previous release digests). This is fast when the previous slot is still healthy and the database
  schema remains compatible.
- **Code rollback is not data rollback.** A previous image can serve only a schema it understands.
  If a migration is destructive, non-additive, or data-transforming, rollback may require restoring a
  verified backup (and accepting a data-loss window back to the backup point).
- **No destructive cleanup:** never run `docker compose down -v`, `docker volume prune`,
  `docker system prune`, or remove database volumes/images as part of rollback unless explicitly
  approved in a separate recovery procedure.

## 2. Automated rollback behavior (`deploy/scripts/deploy.sh`)

The automated deploy script implements fail-closed, traffic-gated behavior:

| Failure point                                                                                                            | Automatic behavior                                                                                                                                          | Active traffic                                                                                             |
| ------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Before traffic switch (pull, revision mismatch, provision, migrate, slot start, inactive-slot health/smoke verification) | Deployment aborts; no upstream rewrite/reload to the new slot                                                                                               | **Unchanged** (previously active slot keeps serving)                                                       |
| During/after traffic switch (post-switch external verification fails)                                                    | Script attempts to rewrite `deploy/caddy/active-upstream.caddy` back to the previously active slot and reload Caddy; verifies external probes when possible | Returned to previous slot **if** restore/reload/probe succeeds; otherwise **manual intervention required** |
| State write failure after successful switch                                                                              | Deployment remains successful; script logs warning that state file was not updated                                                                          | New slot remains active                                                                                    |

Design guarantees (code-level): digest-only deploy, revision-label verification, no `set -x`, no secret
reads/prints, no volume/database/image removal, previous slot kept running for rollback, state recorded
in `/etc/charsooq/state/deploy-state.env` when writable.

## 3. Manual rollback — previous slot still healthy (preferred)

Use when the inactive/previous slot is still running, healthy, and schema-compatible.

1. **Confirm state (read-only):** inspect `/etc/charsooq/state/deploy-state.env` and
   `deploy/caddy/active-upstream.caddy` to identify active/inactive slots and image refs.
2. **Verify previous slot health (read-only):** check container health and internal probes for the
   previous slot (`api-<slot>` `/ready`, `/health`; `web-<slot>` `/login`, `/api/v1/health`).
3. **Switch traffic back (state-changing, brief risk):** rewrite `deploy/caddy/active-upstream.caddy`
   to point to the previous slot atomically and reload Caddy gracefully
   (`docker kill --signal=USR1 <caddy-container>`). Do not restart Caddy unless reload is unavailable.
4. **Verify (read-only):** confirm external HTTPS probes (`/api/v1/health`, `/login`) and user-facing
   behavior through the approved site.
5. **Persist state (state-changing):** update `deploy-state.env` to reflect the restored active slot
   and record the rollback event/time/operator outside Git.
6. **Preserve evidence:** keep deploy logs, workflow run URL, release/tag/SHA/digests, and migration
   revision. Do not remove the failed slot/images until the incident is understood.

## 4. Manual rollback — redeploy previous release digests

Use when the previous slot is not runnable but the schema is backward-compatible with the previous
release.

1. Obtain the previous release's **API/Web digests** from the previous GitHub Release body (authoritative
   record) and confirm they match the intended commit.
2. Set `CHARSOOQ_API_IMAGE` and `CHARSOOQ_WEB_IMAGE` to `repository@sha256:<digest>` values.
3. Pull, start, and verify the inactive slot through the approved deploy procedure
   (`deploy/scripts/deploy.sh` with the previous release identity, or the controlled manual equivalent).
4. Switch traffic only after health/smoke verification; keep the current/failing slot for diagnosis.
5. Verify external health/login and record the deployed digests/revision.

## 5. Rollback after migration failure or incompatible schema change

1. **Stop blind retries.** Do not run `alembic downgrade` as a reflex.
2. **Preserve evidence:** migration logs, `alembic_version`, release SHA/digests, timestamps, and (if
   readable) a backup of the current database state. Do not delete the database volume.
3. **Assess compatibility:** determine whether the previous application code can run on the current
   schema.
   - **Additive/expand-compatible:** prefer code rollback to previous slot/release.
   - **Non-compatible/destructive/data loss risk:** follow [backup-and-recovery.md](backup-and-recovery.md)
     to restore the verified pre-change backup into a scratch database first, validate, then perform the
     approved restore/replacement during a maintenance window.
4. **Return service safely:** restore the compatible image pair and verify health/login/API flows.
5. **Record data-loss window** (backup point vs incident time) if a restore was required.

## 6. Host restart recovery and rollback considerations

- `db`, `caddy`, and slot services are `restart: unless-stopped`; `pgdata`, `caddy_data`, and
  `caddy_config` are persistent volumes.
- Caddy's active upstream is persisted in `deploy/caddy/active-upstream.caddy` (bind-mounted). The
  deploy script also persists slot/image/release state in `/etc/charsooq/state/deploy-state.env`.
- After an unplanned restart, verify which slot is actually serving and which slot containers are
  healthy before attempting a rollback. If only one slot is running, recover the intended active slot
  first; do not remove the other slot's images/state.

## 7. Rollback verification checklist

- [ ] Active upstream file and/or state identify the serving slot
- [ ] Restored slot `api` is healthy and `/ready` + `/health` succeed
- [ ] Restored slot `web` `/login` and same-origin `/api/v1/health` succeed
- [ ] External `https://<CHARSOOQ_SITE_HOST>/api/v1/health` and `/login` succeed (with approved CA trust)
- [ ] Login/session behavior is correct for the current `SESSION_COOKIE_SECURE` mode
- [ ] Release SHA/digests and migration revision are recorded
- [ ] No volume, database, or image was removed during rollback
