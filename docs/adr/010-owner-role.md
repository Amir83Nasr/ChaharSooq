# ADR 010 — Env-managed owner (super admin)

Date: 2026-11-08 · Status: accepted

## Context

ADR 009 introduced `admin` and `viewer`, but the top-level credential still
lived in the seed script (`admin` / `secret123`) and the Makefile. That made
the main credential a code default instead of configuration, and every admin
could create or delete other admins. The shop needs:

- one highest-privilege account configured from the environment;
- a middle role that can manage shop data and viewer accounts, but cannot
  see the owner or other admins;
- a migration that keeps existing installs logged in.

## Decision

- Add `owner` to `admins.role`. It is the only role that may create or delete
  admins and it sees every account.
- `admin` keeps shop writes and may create/delete `viewer` accounts only.
  `GET /api/v1/users` returns viewers only for an admin, so higher-privilege
  usernames never leak. `viewer` stays read-only.
- The owner comes from `OWNER_USERNAME` / `OWNER_PASSWORD` (legacy
  `ADMIN_USER` / `ADMIN_PASSWORD` accepted as aliases). On boot, after
  migrations, `app/services/owner.py` creates the account if missing,
  re-hashes the password when it changes, revokes its sessions, and demotes
  any other `owner` row to `admin` (single-owner invariant).
- Production fails fast when `OWNER_PASSWORD` is missing or shorter than 8
  characters. Development may run without it; the panel then has no owner
  until the env value is set.
- Migration `0018_owner_role` promotes the oldest existing `admin` to
  `owner`; all other accounts stay `admin`.

## Alternatives

- Keep the top account as an ordinary `admin` seeded once: rejected — the
  hard-coded default and panel-based admin creation made the highest level
  replaceable and impossible to configure per environment.
- Two roles only (`owner`, `viewer`): rejected — the shop needs a middle
  operator that manages data and viewers without seeing admins.
- Update the owner username row in place when `OWNER_USERNAME` changes:
  rejected — username is the login identity; a new env username creates the
  new owner and demotes the old one, which is predictable and reversible.

## Consequences

- Changing `OWNER_PASSWORD` is the supported password-reset path for the
  owner; it takes effect on the next API boot and invalidates old sessions.
- Every endpoint must use `require_user` (read), `require_admin`
  (owner/admin write), or `require_owner` (owner-only).
- The panel no longer needs to store or bootstrap the top credential; the
  env is the source of truth.
