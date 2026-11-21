# ADR 027 — Backup schedule defaults in days

Date: 2026-11-21 · Status: accepted · Supersedes the schedule defaults in
[ADR 023](023-in-app-backup-and-data-restore.md)

## Context

ADR 023 enabled automatic backups by default every 720 minutes (12 hours), and
the owner panel exposed that interval in hours. Owners asked for the interval to
be expressed in whole days, with a weekly default and no automatic schedule
until the owner turns it on. The accepted interval range (60–10080 minutes) and
the worker's due-check are unchanged; only the presentation and the stored
defaults move.

## Decision

- The owner panel edits the schedule in whole days (1–7), converting to minutes
  at the API boundary. The API contract keeps `interval_minutes` in minutes.
- When no setting is stored, automatic backups are **disabled** and the interval
  is **10080 minutes (7 days)**. Manual backup, upload, download and restore are
  unaffected and remain available to the owner.
- Existing stored settings are not migrated; an interval saved earlier remains
  in force until the owner changes it.

## Consequences

- A fresh installation makes no scheduled archive until the owner enables the
  schedule; the UI shows the disabled state and the weekly default explicitly.
- The UI rounds a pre-existing sub-day interval up to one day for display; saving
  from the panel then writes that whole-day value.
- The range still caps the schedule at seven days; a longer cadence needs a
  separate decision.
