# IT requirements checklist — چهارسوق Production

Status: **question list, not a record of answers**. This file is the request sent to the
organization's IT team. It contains no approved values, no real IP addresses, no DNS names, and no
certificate data — those are what the answers are for.

Related: [Infrastructure readiness audit](infrastructure-readiness.md) ·
[Production runbook](production-runbook.md) ·
[Release management](release-management.md) ·
[Deployment](../architecture/deployment.md) ·
[ADR 012](../adr/012-internal-reverse-proxy-and-tls.md) ·
[ADR 013](../adr/013-tls-certificate-lifecycle.md) ·
[ADR 014](../adr/014-production-backup-and-recovery.md) ·
[ADR 015](../adr/015-container-image-release-and-publishing.md)

## 1. How to answer

Please answer the questions below, or write "not available" / "not applicable" where that is the
case. An unanswered question blocks a specific stage; a wrong answer is worse than no answer,
because the deployment stack is designed to fail closed rather than guess.

**Needed by** marks the stage that the answer unblocks:

| Code | Stage                             | Meaning in practice                                |
| ---- | --------------------------------- | -------------------------------------------------- |
| A    | Before server preparation         | The host cannot be prepared without it             |
| B    | Before the first deployment       | The stack cannot be started without it             |
| C    | Before users are given access     | The panel runs but must not be opened to users yet |
| D    | For future maintenance operations | Needed to operate the panel over time              |

If an answer is not available for stage A, B, or C, the corresponding step is deferred — it is not
approximated with a placeholder value.

## 2. Server specifications

| #   | Question                                                                                                                                                       | Answer | Needed by |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | --------- |
| 1.1 | Which Linux distribution and release will the server run? (Please give the exact release, e.g. Ubuntu 24.04 LTS.)                                              |        | A         |
| 1.2 | What is the CPU architecture of the server? (`x86_64` or `arm64`.)                                                                                             |        | A         |
| 1.3 | How many CPU cores and how much RAM does the server have? Please give the current values and the maximum values you are willing to allocate.                   |        | A         |
| 1.4 | How much free disk space is available on the filesystem that holds `/var/lib/docker`? Please give the total size and the current free space.                   |        | A         |
| 1.5 | Is a separate disk, filesystem, or storage pool available for the database volume and for backup archives, or must both live on the same filesystem as Docker? |        | A         |
| 1.6 | Is time synchronisation (NTP) enabled on the server, and against which time source?                                                                            |        | A         |
| 1.7 | What is the intended operating and patching schedule for the server?                                                                                           |        | D         |
| 1.8 | Will the server be moved, renamed, or re-IP'd at any point? A fixed IP is required for the certificate.                                                        |        | A         |

## 3. IP address and DNS

| #   | Question                                                                                                                                                                              | Answer | Needed by |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | --------- |
| 2.1 | What is the fixed internal IP address that the application server should use? This is the address clients will connect to.                                                            |        | B         |
| 2.2 | Is that address configured on a dedicated interface, or shared with other services on the host?                                                                                       |        | B         |
| 2.3 | Does the organization run an internal DNS service that can create records for application servers?                                                                                    |        | A         |
| 2.4 | What internal DNS name should the panel use? (A name such as `charsooq.<your-domain>` is preferred over a bare IP, because a DNS name keeps the certificate valid if the IP changes.) |        | B         |
| 2.5 | Is there a DNS forwarder (Windows DNS, a resolver appliance, a hosts-file management process) that must be updated to make that name resolvable?                                      |        | A         |
| 2.6 | Which VLAN or network segment should reach the panel, and are there segments that must explicitly be denied?                                                                          |        | C         |

## 4. Network and firewall

| #   | Question                                                                                                                                             | Answer | Needed by |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | --------- |
| 3.1 | Are TCP ports 80 and 443 free on the host, or are they already used by another service?                                                              |        | B         |
| 3.2 | Is inbound TCP 443 permitted from the client segment to the server's IP?                                                                             |        | C         |
| 3.3 | Is inbound TCP 80 permitted from the client segment? (It is used only to redirect users to HTTPS.)                                                   |        | C         |
| 3.4 | Should any other inbound port be opened for this application? (The application itself needs none: only the reverse proxy publishes a port.)          |        | C         |
| 3.5 | Does the organization use IPv6 on this network, and should the panel be reachable over IPv6?                                                         |        | A         |
| 3.6 | Are there proxy, NAT, or filtering rules between the client segment and the server that affect long-lived HTTPS connections?                         |        | C         |
| 3.7 | What are the IP ranges of the organization's LAN, VPN, and any other routed networks? These are needed to choose Docker subnets that cannot collide. |        | B         |
| 3.8 | Are there existing Docker hosts on the same network, and what address pools do they use?                                                             |        | B         |

## 5. Docker and registry

| #    | Question                                                                                                                                                                                                     | Answer | Needed by |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------ | --------- |
| 4.1  | Is Docker Engine already installed on the server? If yes, which version?                                                                                                                                     |        | A         |
| 4.2  | Is Docker Compose v2 (the `docker compose` subcommand) available? If yes, which version?                                                                                                                     |        | A         |
| 4.3  | Does the Docker daemon start automatically after a host reboot, and is that configured?                                                                                                                      |        | A         |
| 4.4  | Which named account may run deployments, and can it be added to the `docker` group? (Note: membership in that group is equivalent to root on the host.)                                                      |        | B         |
| 4.5  | Does the server have outbound internet access, or does it require an HTTP/HTTPS proxy or an image mirror?                                                                                                    |        | B         |
| 4.6  | Is there a container registry the organization uses (for example GitHub Container Registry, GitLab Registry, Harbor, or a Nexus instance)? Please give the hostname and how a service account authenticates. |        | B         |
| 4.7  | If a registry exists, what image retention and access-control rules apply?                                                                                                                                   |        | D         |
| 4.8  | Where may the deployment checkout live on the host, and which account should own it? (A path such as `/opt/charsooq` is expected.)                                                                           |        | A         |
| 4.9  | Is there a policy for scanning images for vulnerabilities before they run?                                                                                                                                   |        | D         |
| 4.10 | May the Production images be stored in GitHub Container Registry, that is, outside the organization's own infrastructure? If not, which private registry must be used?                                       |        | B         |
| 4.11 | Can the Production host pull from the registry (DNS resolution, TLS trust, and any proxy)? If it cannot, the images must be transferred by another route, and the release procedure changes.                 |        | B         |
| 4.12 | Must the published images be mirrored into an internal registry or an air-gapped artifact store before they may run in Production?                                                                           |        | B         |

## 6. TLS and certificate authority

| #    | Question                                                                                                                                                       | Answer | Needed by |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | --------- |
| 5.1  | Does the organization operate an internal certificate authority (CA) that can issue server certificates?                                                       |        | B         |
| 5.2  | Can that CA issue a certificate whose subject alternative name (SAN) is the DNS name from question 2.4?                                                        |        | B         |
| 5.3  | If no internal CA exists, can that CA issue a certificate with an IP SAN instead, matching question 2.1?                                                       |        | B         |
| 5.4  | If a public CA is to be used instead, is that permitted for an internal-only service, and what is the issuance process?                                        |        | B         |
| 5.5  | What is the process to request a certificate: which team or system receives the request, and what information does it need (CSR, subject, SAN list, validity)? |        | B         |
| 5.6  | How long is a certificate valid, and how much notice is given before expiry?                                                                                   |        | D         |
| 5.7  | Who renews the certificate, and who is the backup owner?                                                                                                       |        | D         |
| 5.8  | Where should the private key be stored before it is installed on the server, and who may read it there?                                                        |        | B         |
| 5.9  | Is the organization's root CA already installed in the trusted certificate store on organization computers?                                                    |        | C         |
| 5.10 | If it is not: can the root certificate be distributed through Active Directory Group Policy or an equivalent client-management tool? Please name the tool.     |        | C         |
| 5.11 | If Group Policy is available, who owns that policy and what is the lead time for a new policy to reach all computers?                                          |        | C         |
| 5.12 | Is a machine certificate or a non-browser client (for example an internal integration) also expected to connect?                                               |        | D         |
| 5.13 | Is HTTP/3 (QUIC over UDP 443) expected to be permitted through the firewall, or should it stay disabled?                                                       |        | D         |

## 7. Backup and storage

| #    | Question                                                                                                                                                         | Answer | Needed by |
| ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | --------- |
| 6.1  | Is there an approved backup destination that is not on this server? Please give the host, share, or object-storage bucket.                                       |        | C         |
| 6.2  | How are backup archives transferred to that destination (for example a scheduled `rsync`, `scp`, a backup agent, or a mounted share)? What credentials are used? |        | C         |
| 6.3  | Which backup encryption tool is approved for use on this network (for example `age` or GnuPG)?                                                                   |        | C         |
| 6.4  | Who holds the encryption key or identity, where is it stored, and how would it be recovered if the key owner is unavailable?                                     |        | C         |
| 6.5  | How long should backups be kept, and is there a legal-hold requirement that prevents deletion?                                                                   |        | D         |
| 6.6  | What recovery point objective (RPO) and recovery time objective (RTO) does the organization require?                                                             |        | C         |
| 6.7  | Is continuous database recovery (point-in-time recovery via transaction-log archiving) required, or is a nightly logical dump sufficient?                        |        | C         |
| 6.8  | Who is accountable for confirming that a backup succeeded, and to whom is a failure reported?                                                                    |        | C         |
| 6.9  | Is there an existing backup or storage platform that already covers this server's Docker volumes, or would this be a new responsibility?                         |        | C         |
| 6.10 | Where should the six application secret files be stored so they can be recovered if the server is rebuilt?                                                       |        | C         |

## 8. Monitoring and alerting

| #   | Question                                                                                                                            | Answer | Needed by |
| --- | ----------------------------------------------------------------------------------------------------------------------------------- | ------ | --------- |
| 7.1 | Is there an existing monitoring agent or collector installed on organization servers that this service should join?                 |        | D         |
| 7.2 | Which alert channel is used for operational paging (for example a messaging channel, an email list, or a ticketing queue)?          |        | D         |
| 7.3 | Who is on call for this service, and what is the escalation path?                                                                   |        | D         |
| 7.4 | Should an external probe check the panel's public endpoint from outside the server's own network? If so, from which source network? |        | D         |
| 7.5 | Is there a policy for how long container logs and system logs are retained centrally?                                               |        | D         |
| 7.6 | Is there a disk-usage threshold that should raise an alert before the database stops?                                               |        | D         |
| 7.7 | Should certificate expiry be tracked by the organization's certificate inventory, and if so, how is it enrolled?                    |        | D         |

## 9. Access and operational responsibilities

| #    | Question                                                                                                                                                     | Answer | Needed by |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------ | --------- |
| 8.1  | Who may SSH to the server, and with which named accounts? (Root login and shared accounts are not to be used.)                                               |        | A         |
| 8.2  | How is SSH access granted and revoked, and is it audited?                                                                                                    |        | D         |
| 8.3  | Who owns the application release — that is, who approves a new version and who performs the deployment?                                                      |        | D         |
| 8.11 | Who may create a GitHub Release for this repository, and who may approve its promotion to Production? The publishing workflow runs on a published release.   |        | B         |
| 8.4  | What maintenance window applies to deployments and to any change that interrupts the service?                                                                |        | D         |
| 8.5  | Who is the custodian of the application secret files (the database credentials, the session secret, and the owner password), and how often are they rotated? |        | C         |
| 8.6  | Who approves a schema change that cannot be undone by reverting the application version, and what is the required backup before it?                          |        | D         |
| 8.7  | Are there restrictions on which outbound hosts the server may contact? The application calls an external accounting API from the server side.                |        | A         |
| 8.8  | Is there a proxy or egress filter that the server's outbound traffic must pass through?                                                                      |        | A         |
| 8.9  | Who is the contact for an incident on this server, and how is an incident declared?                                                                          |        | D         |
| 8.10 | Is there an existing change-approval or maintenance-tracking system (for example an ITSM) that releases and certificate renewals must be recorded in?        |        | D         |

## 10. Answer summary

Fill this table and return it with the answers above. It is the fastest way to see whether a first
deployment can be scheduled.

| Stage                                 | All answers received? | Blocking items still open |
| ------------------------------------- | --------------------- | ------------------------- |
| A — before server preparation         | ☐ yes ☐ no            |                           |
| B — before the first deployment       | ☐ yes ☐ no            |                           |
| C — before users are given access     | ☐ yes ☐ no            |                           |
| D — for future maintenance operations | ☐ yes ☐ no            |                           |

If any row is "no", the deployment is deferred rather than started with placeholder values.
