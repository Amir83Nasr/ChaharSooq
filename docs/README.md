# Documentation — چهارسوق

Start with the [architecture overview](architecture/overview.md). Read the section that matches your task.

| Section                                                                            | Read it for                                                                 |
| ---------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| [architecture/overview.md](architecture/overview.md)                               | How the frontend, backend, and database fit together                        |
| [architecture/frontend.md](architecture/frontend.md)                               | Next.js app, `packages/ui`, formatting and RTL rules                        |
| [architecture/backend.md](architecture/backend.md)                                 | FastAPI layers, security, integrations, OpenAPI                             |
| [architecture/api.md](architecture/api.md)                                         | Endpoint reference and error envelope                                       |
| [architecture/database.md](architecture/database.md)                               | Schema and data rules                                                       |
| [architecture/authentication.md](architecture/authentication.md)                   | Admin login, sessions, and rate limiting                                    |
| [architecture/testing.md](architecture/testing.md)                                 | Test layers and commands                                                    |
| [architecture/deployment.md](architecture/deployment.md)                           | Development, Staging, Production, release flow, Docker                      |
| [operations/infrastructure-readiness.md](operations/infrastructure-readiness.md)   | Pre-deployment readiness audit, blockers, readiness matrix                  |
| [operations/it-requirements.md](operations/it-requirements.md)                     | Checklist of the values and decisions requested from IT                     |
| [operations/production-runbook.md](operations/production-runbook.md)               | Preflight, first start, service lifecycle, release, incidents, monitoring   |
| [operations/troubleshooting.md](operations/troubleshooting.md)                     | Production failure matrix, evidence collection, allowed/dangerous actions   |
| [operations/backup-and-recovery.md](operations/backup-and-recovery.md)             | PostgreSQL dumps, encryption, off-host retention, restore drills, PITR gap  |
| [operations/tls-certificate-lifecycle.md](operations/tls-certificate-lifecycle.md) | TLS install, rotation, rollback, backup/restore, expiry checks, first start |
| [api/README.md](api/README.md)                                                     | Swagger usage, API conventions, OpenAPI snapshot                            |
| [parsina-api.pdf](parsina-api.pdf)                                                 | Vendor document for the Parsina accounting API                              |
| [adr/](adr/)                                                                       | Architecture decision records (`001` to `014`)                              |

New significant decisions get the next ADR number. Do not renumber existing ADRs.
