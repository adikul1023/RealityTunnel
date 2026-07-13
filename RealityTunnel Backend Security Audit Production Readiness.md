## User

RealityTunnel Backend Security Audit (Production Readiness)

You are acting as a Principal Security Engineer performing a professional production security review.

Your goal is NOT to compliment the code.

Your goal is to break it.

Assume this backend is about to be deployed publicly to process real payments and authenticate paying VPN customers.

Your task is to think like:

Senior Backend Engineer
Red Team Engineer
Penetration Tester
Application Security Architect
Payment Security Engineer
Cloud Security Engineer

Do not assume any design decision is correct simply because it exists.

Challenge every assumption.

Audit Philosophy

I do NOT want style feedback.

I do NOT want code formatting suggestions.

I do NOT want naming suggestions.

I do NOT want "this could be cleaner."

I ONLY care about production correctness, security, resilience and architecture.

If something is technically correct but dangerous in production, explain why.

If something is merely uncommon but safe, do not flag it.

Project Overview

RealityTunnel is a commercial VPN backend.

Main technologies:

Python 3.12
FastAPI
PostgreSQL
SQLAlchemy Async
Alembic
httpx
Docker
Marzban
JWT (Ed25519)
Razorpay integration
asyncio

Architecture:

Customer

↓

Authentication

↓

Billing

↓

Subscription

↓

Provisioning

↓

Credentials

↓

Marzban

No router talks directly to Marzban.

No payment provider talks directly to Marzban.

Only ProvisioningService owns provisioning.

Only SubscriptionService owns entitlement.

Only PaymentService owns payments.

Business logic is isolated from routers.

Authentication

Review:

login flow
refresh flow
logout
logout-all
token rotation
replay protection
refresh token revocation
device binding
master token validation
JWT validation
issuer
audience
expiration
Ed25519 implementation
race conditions
refresh replay
refresh storms
concurrent logout/login

Look specifically for:

Privilege escalation

Authentication bypass

Replay

Session fixation

Token confusion

JWT confusion

Algorithm confusion

Timing attacks

Account enumeration

Race conditions

Authorization

Verify:

Customer JWT

cannot ever access

Admin APIs

Admin JWT

cannot ever access

Customer APIs

Check:

Dependency injection

FastAPI dependencies

Authorization boundaries

Object ownership validation

Horizontal privilege escalation

Vertical privilege escalation

Payments

Review:

PaymentService

WebhookService

Razorpay provider

Look for:

Webhook replay

Signature verification

Order tampering

Duplicate capture

Refund abuse

Race conditions

Double activation

Double renewal

Concurrent webhook delivery

Idempotency

Transaction boundaries

Subscriptions

Review:

Subscription lifecycle

Trial

Active

Grace

Expired

Cancelled

Look for:

Invalid transitions

Race conditions

Expired subscriptions remaining active

Concurrent renewals

TOCTOU

Incorrect locking

Provisioning

Review:

ProvisioningService

Retry queues

Synchronization

Credential generation

Marzban integration

Look for:

Duplicate users

Orphaned users

Partial failures

Rollback correctness

Infinite retries

Credential leakage

State divergence

Credentials

Review:

Generation

Revocation

Restoration

Rotation

VLESS URI generation

Sing-box config generation

Look for:

Secret leakage

Caching

Incorrect regeneration

Stale credentials

Improper revocation

Database

Review:

SQLAlchemy

Repositories

Transactions

Isolation

SELECT FOR UPDATE

Indexes

Foreign keys

Cascade behavior

Look for:

Deadlocks

Lost updates

Race conditions

Missing locks

Missing transactions

N+1

Phantom reads

Broken rollback

Async correctness

Review every async service.

Look for:

Missing await

Background task leaks

Cancelled tasks

Shared mutable state

Thread safety

Asyncio misuse

Connection leaks

Background jobs

Review:

Schedulers

Retry processing

Lifecycle automation

Health monitoring

Look for:

Duplicate execution

Scheduler overlap

Crash recovery

Infinite loops

Race conditions

Memory leaks

Security

Review:

Secrets

Logging

Configuration

TLS

CSRF

Headers

Rate limiting

Secret rotation

Audit logging

Recovery

Backup

Look for:

Information disclosure

Secret exposure

Unsafe defaults

Production misconfiguration

Missing validation

Trust boundary violations

Docker

Review:

Dockerfile

docker-compose

Production compose

Look for:

Container escape risks

Running as root

Writable filesystem

Secrets

Permissions

Capabilities

Network isolation

CI/CD

Review:

GitHub Actions

Release pipeline

Security scanning

SBOM generation

Look for:

Supply chain risks

Credential leakage

Unsafe workflow permissions

Dependency attacks

Logging

Verify that:

Passwords

JWTs

Refresh tokens

Master tokens

Database URLs

API keys

Webhook payloads

VLESS URIs

REALITY keys

never appear in logs.

Performance

Review:

Caching

Connection pooling

Metrics

Load testing

Profiling

Look for:

Unbounded memory growth

Hot locks

Expensive queries

Blocking operations

Scalability bottlenecks

Recovery

Review:

Backups

Restore

Integrity

Disaster recovery

Look for:

Restore inconsistencies

Corruption

Missing validation

Silent failures

Threat Model

Produce a realistic threat model covering:

External attacker

Malicious customer

Compromised customer device

Compromised VPS

Compromised Marzban

Compromised payment gateway

Leaked database

Leaked signing key

Admin insider

Supply chain compromise

Required Output

Produce a report with exactly these sections.

Executive Summary

Overall production readiness score

0–10

Critical Findings

Only vulnerabilities that should block production.

Include:

Severity

Likelihood

Impact

Attack scenario

Exact fix

High Findings
Medium Findings
Low Findings
Architecture Review

Critique the architecture itself.

Concurrency Review

Race conditions

Transaction correctness

Locking correctness

Authentication Review
Authorization Review
Payment Review
Provisioning Review
Docker Review
CI/CD Review
Production Readiness

Would you deploy this system today?

Answer:

YES

YES WITH FIXES

NO

Explain why.

Prioritized Fix List

Order every issue from highest risk to lowest.

Important

Do NOT assume the implementation is correct.

Attempt to prove it wrong.

If you cannot find a vulnerability, explicitly explain why the implementation is safe.

Never invent issues.

Every finding must reference the exact file, class, function, or code path responsible.

If you are uncertain, clearly label it as "Needs verification" instead of presenting speculation as fact.

## Assistant

<thinking>
I need to get a comprehensive understanding of this codebase before diving into the audit, so I'm going to start by mapping out the project structure and then systematically work through each component. Given how extensive this is, I might want to parallelize some of the analysis, but first I need to understand what I'm working with.
</thinking>

I'll conduct a thorough security audit of this codebase. Given the scope, let me start by understanding the project structure before diving into each subsystem.

**Tool Call: List the `OverREALITY` directory's contents**
Status: Completed

# Folders:
OverREALITY\.agents
OverREALITY\.github
OverREALITY\.idea
OverREALITY\.vscode
OverREALITY\Assets
OverREALITY\RealityTunnel-Lab
OverREALITY\android
OverREALITY\billing-server
OverREALITY\bin
OverREALITY\obj
OverREALITY\setup
OverREALITY\sing-box-for-android
OverREALITY\sing-box-src

# Files:
OverREALITY\.gitignore
OverREALITY\App.xaml
OverREALITY\App.xaml.cs
OverREALITY\AppSettings.cs
OverREALITY\LICENSE
OverREALITY\MainWindow.xaml
OverREALITY\MainWindow.xaml.cs
OverREALITY\OverREALITY-debug.apk
OverREALITY\OverREALITY-v1.0.0.zip
OverREALITY\OverREALITY-v1.0.1.apk
OverREALITY\OverREALITY.sln
OverREALITY\Package.appxmanifest
OverREALITY\README.md
OverREALITY\RealityTunnel Architecture v5 and Future Plan.md
OverREALITY\RealityTunnel.csproj
OverREALITY\RealityTunnel_Architecture_v5.md
OverREALITY\TrayIcon.cs
OverREALITY\XrayController.cs
OverREALITY\app.ico
OverREALITY\app.manifest
OverREALITY\build_setup.ps1
OverREALITY\config.template.json
OverREALITY\setup.exe
OverREALITY\singbox_runtime.log


## Assistant

The backend is likely in `billing-server`. Let me explore it.

**Tool Call: List the `OverREALITY/billing-server` directory's contents**
Status: Completed

# Folders:
OverREALITY\billing-server\.github
OverREALITY\billing-server\alembic
OverREALITY\billing-server\app
OverREALITY\billing-server\backups
OverREALITY\billing-server\deployment
OverREALITY\billing-server\dev_keys
OverREALITY\billing-server\docs
OverREALITY\billing-server\scripts
OverREALITY\billing-server\tests

# Files:
OverREALITY\billing-server\.gitignore
OverREALITY\billing-server\Dockerfile
OverREALITY\billing-server\README.md
OverREALITY\billing-server\alembic.ini
OverREALITY\billing-server\docker-compose.prod.yml
OverREALITY\billing-server\docker-compose.yml
OverREALITY\billing-server\pytest.ini
OverREALITY\billing-server\requirements.txt


**Tool Call: List the `OverREALITY/billing-server/app` directory's contents**
Status: Completed

# Folders:
OverREALITY\billing-server\app\__pycache__
OverREALITY\billing-server\app\core
OverREALITY\billing-server\app\models
OverREALITY\billing-server\app\observability
OverREALITY\billing-server\app\performance
OverREALITY\billing-server\app\rate_limit
OverREALITY\billing-server\app\recovery
OverREALITY\billing-server\app\repositories
OverREALITY\billing-server\app\routers
OverREALITY\billing-server\app\security
OverREALITY\billing-server\app\security_hardening
OverREALITY\billing-server\app\services

# Files:
OverREALITY\billing-server\app\__init__.py
OverREALITY\billing-server\app\config.py
OverREALITY\billing-server\app\database.py
OverREALITY\billing-server\app\dependencies.py
OverREALITY\billing-server\app\exceptions.py
OverREALITY\billing-server\app\logging_config.py
OverREALITY\billing-server\app\main.py
OverREALITY\billing-server\app\scheduler.py


**Tool Call: List the `OverREALITY/billing-server/dev_keys` directory's contents**
Status: Completed

OverREALITY/billing-server/dev_keys is empty.


**Tool Call: List the `OverREALITY/billing-server/deployment` directory's contents**
Status: Completed

# Folders:
OverREALITY\billing-server\deployment\production
OverREALITY\billing-server\deployment\rollback
OverREALITY\billing-server\deployment\staging
OverREALITY\billing-server\deployment\upgrade


**Tool Call: List the `OverREALITY/billing-server/.github` directory's contents**
Status: Completed

# Folders:
OverREALITY\billing-server\.github\workflows


## Assistant

<thinking>
I need to get a comprehensive view of the codebase structure, so I'm going to scan through all the Python files in the subdirectories to understand the full scope of what I'm working with.
</thinking>

**Tool Call: 50 matches**
Status: Completed

file://D:\My projects\VPN\OverREALITY\billing-server\app\__init__.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\config.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\core\__init__.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\core\feature_flags.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\core\fingerprint.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\core\profiles.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\core\redaction.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\core\secret_registry.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\core\startup_validator.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\database.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\dependencies.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\exceptions.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\logging_config.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\main.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\models\__init__.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\models\account.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\models\admin_user.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\models\base.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\models\connection_signal.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\models\device.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\models\payment.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\models\provisioning.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\models\provisioning_retry.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\models\refresh_token.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\models\subscription.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\models\subscription_plan.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\models\system_health.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\observability\__init__.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\observability\context.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\observability\logging.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\observability\metrics.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\observability\middleware.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\observability\tracing.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\performance\__init__.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\performance\benchmarks.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\performance\cache.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\performance\exceptions.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\performance\load_testing.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\performance\optimizer.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\performance\pooling.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\performance\profiler.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\rate_limit\__init__.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\rate_limit\backend.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\rate_limit\exceptions.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\rate_limit\limiter.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\rate_limit\middleware.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\rate_limit\models.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\rate_limit\storage.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\recovery\__init__.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\recovery\backup.py

**Tool Call: 5 matches**
Status: Completed

file://D:\My projects\VPN\OverREALITY\billing-server\.github\workflows

file://D:\My projects\VPN\OverREALITY\billing-server\.github\workflows\ci.yml

file://D:\My projects\VPN\OverREALITY\billing-server\.github\workflows\docker.yml

file://D:\My projects\VPN\OverREALITY\billing-server\.github\workflows\release.yml

file://D:\My projects\VPN\OverREALITY\billing-server\.github\workflows\security.yml

**Tool Call: 50 matches**
Status: Completed

file://D:\My projects\VPN\OverREALITY\billing-server\tests\__init__.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\conftest.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\core\__init__.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\core\test_backup.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\core\test_configuration_hardening.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\core\test_integrity.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\core\test_observability.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\core\test_rate_limit.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\core\test_restore.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\performance\__init__.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\performance\test_cache.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\performance\test_load.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\performance\test_optimizer.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\performance\test_pooling.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\performance\test_profiler.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\__init__.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_admin_accounts.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_admin_auth.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_admin_billing_api.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_admin_recovery.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_auth.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_billing_api.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_connection_signals_integration.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_credentials_integration.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_devices.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_rate_limit.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_subscription_limits.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_webhooks_integration.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\security\__init__.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\security\test_audit.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\security\test_crypto.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\security\test_csrf.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\security\test_headers.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\security\test_jwt_service.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\security\test_rotation.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\security\test_tls.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\security\test_tokens.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\services\__init__.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\services\test_admin_auth.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\services\test_authentication.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\services\test_connection_signal.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\services\test_credential_service.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\services\test_device_service.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\services\test_event_chaining.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\services\test_lifecycle_job_service.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\services\test_payment_service.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\services\test_provisioning_service.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\services\test_refresh_tokens.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\services\test_scheduler.py

file://D:\My projects\VPN\OverREALITY\billing-server\tests\services\test_subscription_plan.py

## Assistant

This is a large, well-organized codebase. Given the scope, I'll delegate parallel deep-dive audits across disjoint subsystems to sub-agents, then synthesize into the final report. Let me first see the remaining file list and the services/routers/security directories.

**Tool Call: 50 matches**
Status: Completed

file://D:\My projects\VPN\OverREALITY\billing-server\app\recovery\checksums.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\recovery\exceptions.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\recovery\integrity.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\recovery\restore.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\recovery\retention.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\repositories\__init__.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\repositories\account_repository.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\repositories\admin_user_repository.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\repositories\base.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\repositories\connection_signal_repository.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\repositories\device_repository.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\repositories\payment_repository.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\repositories\provisioning_repository.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\repositories\provisioning_retry_repository.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\repositories\refresh_token_repository.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\repositories\subscription_repository.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\repositories\system_health_repository.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\__init__.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_auth.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_dtos.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_models.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_recovery.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\auth.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\auth_models.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\billing.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\credential_models.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\credentials.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\device_models.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\devices.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\health.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\metrics.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\webhooks.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\scheduler.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\security\__init__.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\security\admin_jwt.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\security\admin_password.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\security\constants.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\security\crypto.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\security\jwt_models.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\security\jwt_service.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\security\tokens.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\security_hardening\__init__.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\security_hardening\audit.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\security_hardening\csrf.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\security_hardening\exceptions.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\security_hardening\headers.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\security_hardening\rotation.py

file://D:\My projects\VPN\OverREALITY\billing-server\app\security_hardening\tls.py

**Tool Call: List the `OverREALITY/billing-server/app/services` directory's contents**
Status: Completed

# Folders:
OverREALITY\billing-server\app\services\__pycache__
OverREALITY\billing-server\app\services\payment
OverREALITY\billing-server\app\services\provisioning

# Files:
OverREALITY\billing-server\app\services\__init__.py
OverREALITY\billing-server\app\services\admin_account.py
OverREALITY\billing-server\app\services\admin_auth.py
OverREALITY\billing-server\app\services\admin_billing_dtos.py
OverREALITY\billing-server\app\services\admin_billing_service.py
OverREALITY\billing-server\app\services\authentication.py
OverREALITY\billing-server\app\services\billing_dtos.py
OverREALITY\billing-server\app\services\billing_service.py
OverREALITY\billing-server\app\services\connection_signal.py
OverREALITY\billing-server\app\services\credential_service.py
OverREALITY\billing-server\app\services\device.py
OverREALITY\billing-server\app\services\exceptions.py
OverREALITY\billing-server\app\services\lifecycle_job_service.py
OverREALITY\billing-server\app\services\refresh_tokens.py
OverREALITY\billing-server\app\services\subscription_plan.py
OverREALITY\billing-server\app\services\subscription_service.py


**Tool Call: List the `OverREALITY/billing-server/app/routers` directory's contents**
Status: Completed

# Folders:
OverREALITY\billing-server\app\routers\__pycache__

# Files:
OverREALITY\billing-server\app\routers\__init__.py
OverREALITY\billing-server\app\routers\admin.py
OverREALITY\billing-server\app\routers\admin_auth.py
OverREALITY\billing-server\app\routers\admin_billing.py
OverREALITY\billing-server\app\routers\admin_dtos.py
OverREALITY\billing-server\app\routers\admin_models.py
OverREALITY\billing-server\app\routers\admin_recovery.py
OverREALITY\billing-server\app\routers\auth.py
OverREALITY\billing-server\app\routers\auth_models.py
OverREALITY\billing-server\app\routers\billing.py
OverREALITY\billing-server\app\routers\credential_models.py
OverREALITY\billing-server\app\routers\credentials.py
OverREALITY\billing-server\app\routers\device_models.py
OverREALITY\billing-server\app\routers\devices.py
OverREALITY\billing-server\app\routers\health.py
OverREALITY\billing-server\app\routers\metrics.py
OverREALITY\billing-server\app\routers\webhooks.py


**Tool Call: List the `OverREALITY/billing-server/app/security` directory's contents**
Status: Completed

# Folders:
OverREALITY\billing-server\app\security\__pycache__

# Files:
OverREALITY\billing-server\app\security\__init__.py
OverREALITY\billing-server\app\security\admin_jwt.py
OverREALITY\billing-server\app\security\admin_password.py
OverREALITY\billing-server\app\security\constants.py
OverREALITY\billing-server\app\security\crypto.py
OverREALITY\billing-server\app\security\jwt_models.py
OverREALITY\billing-server\app\security\jwt_service.py
OverREALITY\billing-server\app\security\tokens.py


**Tool Call: List the `OverREALITY/billing-server/app/security_hardening` directory's contents**
Status: Completed

# Folders:
OverREALITY\billing-server\app\security_hardening\__pycache__

# Files:
OverREALITY\billing-server\app\security_hardening\__init__.py
OverREALITY\billing-server\app\security_hardening\audit.py
OverREALITY\billing-server\app\security_hardening\csrf.py
OverREALITY\billing-server\app\security_hardening\exceptions.py
OverREALITY\billing-server\app\security_hardening\headers.py
OverREALITY\billing-server\app\security_hardening\rotation.py
OverREALITY\billing-server\app\security_hardening\tls.py
OverREALITY\billing-server\app\security_hardening\validators.py


**Tool Call: List the `OverREALITY/billing-server/app/repositories` directory's contents**
Status: Completed

# Folders:
OverREALITY\billing-server\app\repositories\__pycache__

# Files:
OverREALITY\billing-server\app\repositories\__init__.py
OverREALITY\billing-server\app\repositories\account_repository.py
OverREALITY\billing-server\app\repositories\admin_user_repository.py
OverREALITY\billing-server\app\repositories\base.py
OverREALITY\billing-server\app\repositories\connection_signal_repository.py
OverREALITY\billing-server\app\repositories\device_repository.py
OverREALITY\billing-server\app\repositories\payment_repository.py
OverREALITY\billing-server\app\repositories\provisioning_repository.py
OverREALITY\billing-server\app\repositories\provisioning_retry_repository.py
OverREALITY\billing-server\app\repositories\refresh_token_repository.py
OverREALITY\billing-server\app\repositories\subscription_repository.py
OverREALITY\billing-server\app\repositories\system_health_repository.py


## Assistant

<thinking>
I'm going to focus on the most critical components myself—authentication, authorization, and payments—since those carry the highest risk, then spin up parallel sub-agents to handle provisioning, credentials, database concurrency, Docker/CI, background jobs, and security hardening with read-only access to avoid conflicts.
</thinking>

I'll handle authentication, authorization, and payments myself (highest risk areas), while delegating provisioning/credentials, database/concurrency, and Docker/CI/CD to parallel sub-agents. Let me start reading the critical auth/payment files directly.

**Tool Call: Read file `billing-server\app\security\jwt_service.py`**
Status: Completed

```OverREALITY/billing-server/app/security/jwt_service.py
     1	"""
     2	jwt_service.py — JWT Engine for RealityTunnel Billing/Auth Access Tokens.
     3	
     4	SECURITY & ARCHITECTURAL DECISIONS:
     5	1. Why Ed25519 (EdDSA) instead of HS256:
     6	   Asymmetric Ed25519 cryptography cleanly separates identity issuance from token verification. The Billing/Auth server
     7	   retains the private signing key to issue signed access tokens. Future middleware, VPN servers, or client APIs only
     8	   need the public key to verify tokens without ever possessing the secret required to forge tokens. This avoids the
     9	   security hazards of shared-secret HMACs (HS256) across distributed systems. Furthermore, Ed25519 signatures are
    10	   exceptionally fast, produce compact 64-byte signatures, and are immune to RSA padding and key-confusion attacks.
    11	
    12	2. Why minimal claims:
    13	   Tokens include only `sub` (Account UUID), `account` (Account ID), `device` (Device GUID), and standard RFC 7519
    14	   registered claims (`iss`, `aud`, `iat`, `nbf`, `exp`, `jti`). We omit Master Tokens, hashes, emails, roles, and
    15	   subscription details to prevent data leaks if tokens are logged by client telemetry or captured in transit.
    16	
    17	3. Why 15-minute lifetime (`ACCESS_TOKEN_EXPIRE_MINUTES = 15`):
    18	   Access tokens are stateless bearer credentials. A brief 15-minute window minimizes the impact of token interception.
    19	   Long-term sessions are sustained via Refresh Token Rotation (Phase 1.3.4), avoiding database lookups on every API request.
    20	
    21	4. Why JWT includes a unique `jti` claim:
    22	   A cryptographically random 128-bit hex string identifies each token uniquely. This enables future capabilities such as
    23	   replay attack detection, audit logging, and rapid short-term blocklisting without altering token structure.
    24	
    25	5. Why verification validates Issuer (`iss`) and Audience (`aud`):
    26	   Validating `iss` ("RealityTunnel Billing/Auth") and `aud` ("RealityTunnel Client") prevents cross-service token
    27	   substitution attacks, ensuring tokens intended for one client or generated by another issuer cannot be misused here.
    28	
    29	KEY MANAGEMENT APPROACH:
    30	- Development mode: If Ed25519 PEM keys are absent from the configured key directory, they are automatically generated and
    31	  saved with restrictive file permissions (0600).
    32	- Production mode: Auto-generation is strictly prohibited. The service raises a RuntimeError if keys are not securely
    33	  pre-provisioned.
    34	"""
    35	from __future__ import annotations
    36	
    37	import logging
    38	import os
    39	import secrets
    40	import stat
    41	import uuid
    42	from datetime import datetime, timezone, timedelta
    43	from pathlib import Path
    44	from typing import Any
    45	
    46	import jwt
    47	from cryptography.hazmat.primitives import serialization
    48	from cryptography.hazmat.primitives.asymmetric import ed25519
    49	
    50	from app.security.jwt_models import (
    51	    AccessTokenClaims,
    52	    ACCESS_TOKEN_EXPIRE_MINUTES,
    53	    JWT_ALGORITHM,
    54	    JWT_AUDIENCE,
    55	    JWT_ISSUER,
    56	)
    57	from app.services.exceptions import (
    58	    InvalidAudienceError,
    59	    InvalidIssuerError,
    60	    InvalidSignatureError,
    61	    InvalidTokenError,
    62	    TokenExpiredError,
    63	    TokenNotYetValidError,
    64	)
    65	
    66	logger = logging.getLogger(__name__)
    67	
    68	
    69	class JWTService:
    70	    """
    71	    Dedicated engine for issuing and verifying Ed25519 signed Access JWTs.
    72	    Strictly independent of FastAPI routes, login endpoints, refresh tokens, and HTTP middleware.
    73	    """
    74	
    75	    def __init__(
    76	        self,
    77	        keys_dir: Path | str | None = None,
    78	        environment: str | None = None,
    79	    ) -> None:
    80	        if environment is None:
    81	            from app.config import settings
    82	            self.environment = settings.environment
    83	        else:
    84	            self.environment = environment
    85	
    86	        if keys_dir is None:
    87	            # Default to dev_keys directory in project root
    88	            self.keys_dir = Path(__file__).resolve().parent.parent.parent / "dev_keys"
    89	        else:
    90	            self.keys_dir = Path(keys_dir)
    91	
    92	        self.private_key: ed25519.Ed25519PrivateKey | None = None
    93	        self.public_key: ed25519.Ed25519PublicKey | None = None
    94	
    95	        self._load_or_generate_keys()
    96	
    97	    def _load_or_generate_keys(self) -> None:
    98	        """Load Ed25519 keys from disk or auto-generate them if in development mode."""
    99	        private_key_path = self.keys_dir / "ed25519_private.pem"
   100	        public_key_path = self.keys_dir / "ed25519_public.pem"
   101	
   102	        if private_key_path.exists() and public_key_path.exists():
   103	            private_bytes = private_key_path.read_bytes()
   104	            public_bytes = public_key_path.read_bytes()
   105	            self.private_key = serialization.load_pem_private_key(private_bytes, password=None)  # type: ignore
   106	            self.public_key = serialization.load_pem_public_key(public_bytes)  # type: ignore
   107	            return
   108	
   109	        if self.environment.lower() == "production":
   110	            raise RuntimeError(
   111	                "Production Ed25519 signing keys are absent from disk! "
   112	                "Automatic key generation is strictly prohibited in production environments."
   113	            )
   114	
   115	        # Development / test auto-generation
   116	        self.keys_dir.mkdir(parents=True, exist_ok=True)
   117	        new_private = ed25519.Ed25519PrivateKey.generate()
   118	        new_public = new_private.public_key()
   119	
   120	        private_pem = new_private.private_bytes(
   121	            encoding=serialization.Encoding.PEM,
   122	            format=serialization.PrivateFormat.PKCS8,
   123	            encryption_algorithm=serialization.NoEncryption(),
   124	        )
   125	        public_pem = new_public.public_bytes(
   126	            encoding=serialization.Encoding.PEM,
   127	            format=serialization.PublicFormat.SubjectPublicKeyInfo,
   128	        )
   129	
   130	        private_key_path.write_bytes(private_pem)
   131	        public_key_path.write_bytes(public_pem)
   132	
   133	        # Apply restrictive permissions on Unix systems
   134	        try:
   135	            os.chmod(private_key_path, stat.S_IRUSR | stat.S_IWUSR)
   136	            os.chmod(public_key_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
   137	        except Exception:
   138	            pass
   139	
   140	        self.private_key = new_private
   141	        self.public_key = new_public
   142	
   143	    def issue_access_token(
   144	        self,
   145	        account_uuid: str | uuid.UUID,
   146	        account_id: str,
   147	        device_guid: str,
   148	    ) -> str:
   149	        """
   150	        Issue a new 15-minute stateless Access JWT signed with Ed25519.
   151	
   152	        LOGGING INVARIANT: Never logs token strings or private keys.
   153	        """
   154	        if self.private_key is None:
   155	            raise RuntimeError("Private signing key is not initialized.")
   156	
   157	        now = datetime.now(timezone.utc)
   158	        iat = int(now.timestamp())
   159	        nbf = iat
   160	        exp = int((now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp())
   161	        jti = secrets.token_hex(16)
   162	
   163	        payload = {
   164	            "sub": str(account_uuid),
   165	            "account": str(account_id),
   166	            "device": str(device_guid),
   167	            "iss": JWT_ISSUER,
   168	            "aud": JWT_AUDIENCE,
   169	            "iat": iat,
   170	            "nbf": nbf,
   171	            "exp": exp,
   172	            "jti": jti,
   173	        }
   174	
   175	        token = jwt.encode(payload, self.private_key, algorithm=JWT_ALGORITHM)
   176	        logger.info("Access token issued")
   177	        return token
   178	
   179	    def verify_access_token(self, token: str) -> AccessTokenClaims:
   180	        """
   181	        Verify an Access JWT signature, expiration, issuer, audience, and required claims.
   182	        Returns typed AccessTokenClaims or raises dedicated JWT service exceptions.
   183	
   184	        LOGGING INVARIANT: Never logs token strings, public keys, or decoded claim contents.
   185	        """
   186	        if self.public_key is None:
   187	            raise RuntimeError("Public verification key is not initialized.")
   188	
   189	        try:
   190	            payload = jwt.decode(
   191	                token,
   192	                self.public_key,
   193	                algorithms=[JWT_ALGORITHM],
   194	                issuer=JWT_ISSUER,
   195	                audience=JWT_AUDIENCE,
   196	                leeway=0,  # Explicitly disallow clock skew for stateless access tokens
   197	                options={
   198	                    "require": ["sub", "account", "device", "iss", "aud", "iat", "nbf", "exp", "jti"],
   199	                    "verify_signature": True,
   200	                    "verify_exp": True,
   201	                    "verify_nbf": True,
   202	                    "verify_iat": True,
   203	                    "verify_iss": True,
   204	                    "verify_aud": True,
   205	                },
   206	            )
   207	        except jwt.ExpiredSignatureError as e:
   208	            logger.info("JWT validation failed: Token expired")
   209	            raise TokenExpiredError("Access token has expired") from e
   210	        except jwt.ImmatureSignatureError as e:
   211	            logger.info("JWT validation failed: Token not yet valid")
   212	            raise TokenNotYetValidError("Access token is not yet valid (nbf)") from e
   213	        except jwt.InvalidSignatureError as e:
   214	            logger.info("JWT validation failed: Invalid signature")
   215	            raise InvalidSignatureError("Access token signature verification failed") from e
   216	        except jwt.InvalidIssuerError as e:
   217	            logger.info("JWT validation failed: Invalid issuer")
   218	            raise InvalidIssuerError("Access token issuer verification failed") from e
   219	        except jwt.InvalidAudienceError as e:
   220	            logger.info("JWT validation failed: Invalid audience")
   221	            raise InvalidAudienceError("Access token audience verification failed") from e
   222	        except jwt.MissingRequiredClaimError as e:
   223	            logger.info("JWT validation failed: Missing required claim")
   224	            raise InvalidTokenError("Access token is missing a required claim") from e
   225	        except jwt.PyJWTError as e:
   226	            logger.info("JWT validation failed: Invalid token")
   227	            raise InvalidTokenError("Access token is invalid or malformed") from e
   228	        except Exception as e:
   229	            logger.info("JWT validation failed: Invalid token")
   230	            raise InvalidTokenError("Unexpected error validating access token") from e
   231	
   232	        try:
   233	            return AccessTokenClaims.from_dict(payload)
   234	        except ValueError as e:
   235	            logger.info("JWT validation failed: Missing required claim")
   236	            raise InvalidTokenError("Access token is missing a required claim") from e

```


**Tool Call: Read file `billing-server\app\security\tokens.py`**
Status: Completed

```OverREALITY/billing-server/app/security/tokens.py
     1	"""
     2	Token & Identifier Generation
     3	
     4	Pure functions for generating cryptographically secure Master Tokens, Device GUIDs,
     5	and unambiguous human-readable Account IDs using Python's `secrets` module.
     6	Strictly zero logging of generated tokens or identifiers.
     7	"""
     8	
     9	import secrets
    10	from app.security.constants import (
    11	    MASTER_TOKEN_BYTES,
    12	    REFRESH_TOKEN_BYTES,
    13	    DEVICE_GUID_BYTES,
    14	    ACCOUNT_ID_PREFIX,
    15	    ACCOUNT_ID_GROUPS,
    16	    ACCOUNT_ID_GROUP_SIZE,
    17	    ACCOUNT_ID_SEPARATOR,
    18	    ACCOUNT_ID_ALPHABET,
    19	)
    20	
    21	
    22	def generate_master_token() -> str:
    23	    """
    24	    Generate a cryptographically secure 256-bit Master Token formatted as a 64-character hexadecimal string.
    25	
    26	    CRYPTOGRAPHIC REASONING — WHY SECRETS INSTEAD OF RANDOM / UUID:
    27	    1. Python's standard `random` module uses the Mersenne Twister algorithm, which is completely
    28	       deterministic and non-cryptographic. Observing 624 outputs allows an attacker to predict
    29	       all future random values, compromising token security.
    30	    2. `secrets.token_hex()` uses the operating system's Cryptographically Secure Pseudorandom
    31	       Number Generator (CSPRNG, e.g., getrandom()/urandom on Linux, BCryptGenRandom on Windows).
    32	    3. Generating 32 bytes (256 bits) of entropy produces a URL-safe, 64-character hex string
    33	       with deterministic length, ideal for high-entropy machine-to-machine authentication.
    34	    """
    35	    return secrets.token_hex(MASTER_TOKEN_BYTES)
    36	
    37	
    38	def generate_refresh_token() -> str:
    39	    """
    40	    Generate a cryptographically secure 256-bit Refresh Token formatted as a 64-character hexadecimal string.
    41	
    42	    CRYPTOGRAPHIC REASONING:
    43	    Like Master Tokens, Refresh Tokens must possess 256 bits of true entropy generated via OS CSPRNG
    44	    (`secrets.token_hex`). This ensures long-lived sessions are immune to guessing or brute-force attacks
    45	    when stored as SHA-256 digests in the database.
    46	    """
    47	    return secrets.token_hex(REFRESH_TOKEN_BYTES)
    48	
    49	
    50	def generate_device_guid() -> str:
    51	    """
    52	    Generate a cryptographically secure 256-bit Device GUID formatted as a 64-character hexadecimal string.
    53	
    54	    CRYPTOGRAPHIC REASONING — WHY RANDOM GUIDS INSTEAD OF HARDWARE FINGERPRINTING:
    55	    1. Hardware fingerprinting (MAC addresses, CPU IDs, motherboard serials) is unreliable across
    56	       virtual machines, containerized environments, and hardware upgrades (e.g., swapping a network card).
    57	    2. Hardware IDs can be trivially spoofed or cloned by malicious actors, making them insecure as an
    58	       identity proof.
    59	    3. Harvesting physical hardware serial numbers introduces significant user privacy and tracking concerns.
    60	    4. By generating a random 256-bit CSPRNG GUID once at installation time and storing it securely on
    61	       the client device, we ensure high uniqueness, zero privacy invasion, and robust resilience against
    62	       environment changes.
    63	    """
    64	    return secrets.token_hex(DEVICE_GUID_BYTES)
    65	
    66	
    67	def generate_account_id() -> str:
    68	    """
    69	    Generate a formatted Account ID in the RealityTunnel format: RT-XXXX-XXXX-XXXX.
    70	
    71	    DESIGN REASONING — WHY ACCOUNT IDS ARE IDENTIFIERS AND NOT SECRETS:
    72	    1. Account IDs serve purely as public/semi-public human-readable references for billing support,
    73	       account lookup, and user identification. They are NEVER used alone to authenticate requests or
    74	       grant authorization (which requires possession of the Master Token or valid session tokens).
    75	    2. To make transcription and manual entry error-free for end users, the alphabet is restricted to 31
    76	       unambiguous uppercase characters (`ABCDEFGHJKMNPQRSTUVWXYZ23456789`), explicitly excluding visually
    77	       confusing characters: '0' (zero), 'O' (capital o), '1' (one), 'I' (capital i), and 'L' (capital l).
    78	    3. `secrets.choice()` is used to ensure uniform, unbiased distribution across the alphabet.
    79	    """
    80	    groups = []
    81	    for _ in range(ACCOUNT_ID_GROUPS):
    82	        group = "".join(secrets.choice(ACCOUNT_ID_ALPHABET) for _ in range(ACCOUNT_ID_GROUP_SIZE))
    83	        groups.append(group)
    84	    return f"{ACCOUNT_ID_PREFIX}{ACCOUNT_ID_SEPARATOR}{ACCOUNT_ID_SEPARATOR.join(groups)}"

```


**Tool Call: Read file `billing-server\app\security\jwt_models.py`**
Status: Completed

```OverREALITY/billing-server/app/security/jwt_models.py
     1	"""
     2	jwt_models.py — Typed Dataclasses and Constants for Access JWTs.
     3	
     4	SECURITY & ARCHITECTURAL DECISIONS:
     5	1. Minimal Claims:
     6	   The JWT contains only `sub` (Account UUID), `account` (Account ID), `device` (Device GUID), and standard RFC 7519
     7	   registered claims (`iss`, `aud`, `iat`, `nbf`, `exp`, `jti`). We explicitly omit Master Tokens, password hashes, emails,
     8	   subscription statuses, and Marzban usernames to minimize exposure if a token is intercepted or logged by client telemetry.
     9	
    10	2. 15-Minute Lifetime (`ACCESS_TOKEN_EXPIRE_MINUTES = 15`):
    11	   Access tokens are stateless bearer tokens. A short 15-minute lifetime limits the window of vulnerability if a token is stolen.
    12	   Revocation and rotation are handled via Refresh Tokens (Phase 1.3.4), keeping access verification fast and database-free.
    13	
    14	3. Unique Token Identifier (`jti`):
    15	   Every token includes a random 128-bit hex string (`jti`). This enables future support for replay detection, audit tracking,
    16	   and short-term blocklisting without altering the core token schema.
    17	
    18	4. Explicit Issuer and Audience (`iss`, `aud`):
    19	   Enforcing strict `iss` ("RealityTunnel Billing/Auth") and `aud` ("RealityTunnel Client") claims prevents cross-service
    20	   token substitution attacks (e.g., using a token issued for a third-party analytical tool against our API).
    21	"""
    22	from __future__ import annotations
    23	
    24	from dataclasses import dataclass, asdict
    25	from typing import Any
    26	
    27	from app.config import settings
    28	
    29	# Centralized JWT Constants
    30	ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    31	JWT_ISSUER: str = settings.jwt_issuer
    32	JWT_AUDIENCE: str = settings.jwt_audience
    33	JWT_ALGORITHM: str = "EdDSA"
    34	
    35	
    36	@dataclass(frozen=True)
    37	class AccessTokenClaims:
    38	    """
    39	    Typed representation of decoded Access Token claims.
    40	    Ensures upper layers interact with strong types instead of raw dictionaries.
    41	    """
    42	    sub: str        # Account UUID string
    43	    account: str    # RealityTunnel Account ID (RT-XXXX-XXXX-XXXX)
    44	    device: str     # Device GUID
    45	    iss: str        # Issuer
    46	    aud: str        # Audience
    47	    iat: int        # Issued At timestamp (UTC epoch seconds)
    48	    nbf: int        # Not Before timestamp (UTC epoch seconds)
    49	    exp: int        # Expiration timestamp (UTC epoch seconds)
    50	    jti: str        # JWT ID (unique hex identifier)
    51	
    52	    def to_dict(self) -> dict[str, Any]:
    53	        """Convert typed dataclass to raw dictionary for serialization."""
    54	        return asdict(self)
    55	
    56	    @classmethod
    57	    def from_dict(cls, data: dict[str, Any]) -> AccessTokenClaims:
    58	        """Create typed dataclass from decoded payload dictionary, verifying all required claims exist."""
    59	        required_keys = {"sub", "account", "device", "iss", "aud", "iat", "nbf", "exp", "jti"}
    60	        missing = required_keys - data.keys()
    61	        if missing:
    62	            raise ValueError(f"Missing required JWT claims: {sorted(list(missing))}")
    63	        
    64	        return cls(
    65	            sub=str(data["sub"]),
    66	            account=str(data["account"]),
    67	            device=str(data["device"]),
    68	            iss=str(data["iss"]),
    69	            aud=str(data["aud"]),
    70	            iat=int(data["iat"]),
    71	            nbf=int(data["nbf"]),
    72	            exp=int(data["exp"]),
    73	            jti=str(data["jti"]),
    74	        )

```


**Tool Call: Read file `billing-server\app\security\admin_jwt.py`**
Status: Completed

```OverREALITY/billing-server/app/security/admin_jwt.py
     1	"""
     2	admin_jwt.py — Independent JWT Engine for RealityTunnel Administrative Access Tokens.
     3	
     4	SECURITY & ARCHITECTURAL DECISIONS:
     5	1. Complete Domain Isolation:
     6	   The administrative JWT service operates with an entirely independent Ed25519 signing keypair stored in a separate
     7	   key directory (`dev_keys/admin/admin_ed25519_private.pem` and `admin_ed25519_public.pem`). It never reuses customer keys.
     8	2. Separate Issuer and Audience:
     9	   Admin tokens enforce `iss` ("RealityTunnel Admin") and `aud` ("RealityTunnel Admin Panel"). This guarantees that a customer
    10	   access token presented to an admin route (or vice versa) fails verification immediately at the signature/issuer layer.
    11	3. 15-Minute Lifetime (`ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES = 15`):
    12	   Limits exposure of bearer tokens while keeping admin API requests stateless.
    13	4. Minimal Admin Claims:
    14	   Contains `sub` (admin UUID string), `username`, `role` ("super_admin" or "admin"), and RFC 7519 registered claims.
    15	"""
    16	from __future__ import annotations
    17	
    18	import logging
    19	import os
    20	import secrets
    21	import stat
    22	import uuid
    23	from dataclasses import dataclass, asdict
    24	from datetime import datetime, timezone, timedelta
    25	from pathlib import Path
    26	from typing import Any
    27	
    28	import jwt
    29	from cryptography.hazmat.primitives import serialization
    30	from cryptography.hazmat.primitives.asymmetric import ed25519
    31	
    32	from app.config import settings
    33	from app.services.exceptions import (
    34	    InvalidAdminTokenError,
    35	    AdminTokenExpiredError,
    36	)
    37	
    38	logger = logging.getLogger(__name__)
    39	
    40	ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    41	ADMIN_JWT_ALGORITHM: str = "EdDSA"
    42	
    43	
    44	@dataclass(frozen=True)
    45	class AdminTokenClaims:
    46	    """
    47	    Typed representation of decoded Admin Access Token claims.
    48	    """
    49	    sub: str        # Admin UUID string
    50	    username: str   # Admin username
    51	    role: str       # Admin role ("super_admin" or "admin")
    52	    iss: str        # Issuer
    53	    aud: str        # Audience
    54	    iat: int        # Issued At timestamp
    55	    nbf: int        # Not Before timestamp
    56	    exp: int        # Expiration timestamp
    57	    jti: str        # Unique JWT ID
    58	
    59	    def to_dict(self) -> dict[str, Any]:
    60	        return asdict(self)
    61	
    62	    @classmethod
    63	    def from_dict(cls, data: dict[str, Any]) -> AdminTokenClaims:
    64	        required_keys = {"sub", "username", "role", "iss", "aud", "iat", "nbf", "exp", "jti"}
    65	        missing = required_keys - data.keys()
    66	        if missing:
    67	            raise ValueError(f"Missing required Admin JWT claims: {sorted(list(missing))}")
    68	        
    69	        return cls(
    70	            sub=str(data["sub"]),
    71	            username=str(data["username"]),
    72	            role=str(data["role"]),
    73	            iss=str(data["iss"]),
    74	            aud=str(data["aud"]),
    75	            iat=int(data["iat"]),
    76	            nbf=int(data["nbf"]),
    77	            exp=int(data["exp"]),
    78	            jti=str(data["jti"]),
    79	        )
    80	
    81	
    82	class AdminJWTService:
    83	    """
    84	    Dedicated engine for issuing and verifying Ed25519 signed Administrative JWTs.
    85	    Strictly isolated from customer JWTService and customer keys.
    86	    """
    87	
    88	    def __init__(
    89	        self,
    90	        keys_dir: Path | str | None = None,
    91	        environment: str | None = None,
    92	        issuer: str | None = None,
    93	        audience: str | None = None,
    94	    ) -> None:
    95	        if environment is None:
    96	            self.environment = settings.environment
    97	        else:
    98	            self.environment = environment
    99	
   100	        self.issuer = issuer if issuer is not None else settings.admin_jwt_issuer
   101	        self.audience = audience if audience is not None else settings.admin_jwt_audience
   102	
   103	        if keys_dir is None:
   104	            self.keys_dir = Path(__file__).resolve().parent.parent.parent / "dev_keys" / "admin"
   105	        else:
   106	            self.keys_dir = Path(keys_dir)
   107	
   108	        self.private_key: ed25519.Ed25519PrivateKey | None = None
   109	        self.public_key: ed25519.Ed25519PublicKey | None = None
   110	
   111	        self._load_or_generate_keys()
   112	
   113	    def _load_or_generate_keys(self) -> None:
   114	        """Load Ed25519 keys from disk or auto-generate them if in development mode."""
   115	        private_key_path = self.keys_dir / "admin_ed25519_private.pem"
   116	        public_key_path = self.keys_dir / "admin_ed25519_public.pem"
   117	
   118	        if private_key_path.exists() and public_key_path.exists():
   119	            private_bytes = private_key_path.read_bytes()
   120	            public_bytes = public_key_path.read_bytes()
   121	            self.private_key = serialization.load_pem_private_key(private_bytes, password=None)  # type: ignore
   122	            self.public_key = serialization.load_pem_public_key(public_bytes)  # type: ignore
   123	            return
   124	
   125	        if self.environment.lower() == "production":
   126	            raise RuntimeError(
   127	                "Production Admin Ed25519 signing keys are absent from disk! "
   128	                "Automatic key generation is strictly prohibited in production environments."
   129	            )
   130	
   131	        # Development / test auto-generation
   132	        self.keys_dir.mkdir(parents=True, exist_ok=True)
   133	        new_private = ed25519.Ed25519PrivateKey.generate()
   134	        new_public = new_private.public_key()
   135	
   136	        private_pem = new_private.private_bytes(
   137	            encoding=serialization.Encoding.PEM,
   138	            format=serialization.PrivateFormat.PKCS8,
   139	            encryption_algorithm=serialization.NoEncryption(),
   140	        )
   141	        public_pem = new_public.public_bytes(
   142	            encoding=serialization.Encoding.PEM,
   143	            format=serialization.PublicFormat.SubjectPublicKeyInfo,
   144	        )
   145	
   146	        private_key_path.write_bytes(private_pem)
   147	        public_key_path.write_bytes(public_pem)
   148	
   149	        try:
   150	            os.chmod(private_key_path, stat.S_IRUSR | stat.S_IWUSR)
   151	            os.chmod(public_key_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
   152	        except Exception:
   153	            pass
   154	
   155	        self.private_key = new_private
   156	        self.public_key = new_public
   157	
   158	    def issue_admin_token(
   159	        self,
   160	        admin_id: uuid.UUID | str,
   161	        username: str,
   162	        is_super_admin: bool,
   163	    ) -> str:
   164	        """
   165	        Issue a signed Ed25519 Administrative Access Token valid for 15 minutes.
   166	        """
   167	        if self.private_key is None:
   168	            raise RuntimeError("Admin private key is not initialized")
   169	
   170	        now_dt = datetime.now(timezone.utc)
   171	        iat = int(now_dt.timestamp())
   172	        exp = int((now_dt + timedelta(minutes=ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp())
   173	        jti = secrets.token_hex(16)
   174	
   175	        role = "super_admin" if is_super_admin else "admin"
   176	
   177	        claims = AdminTokenClaims(
   178	            sub=str(admin_id),
   179	            username=username,
   180	            role=role,
   181	            iss=self.issuer,
   182	            aud=self.audience,
   183	            iat=iat,
   184	            nbf=iat,
   185	            exp=exp,
   186	            jti=jti,
   187	        )
   188	
   189	        token = jwt.encode(
   190	            payload=claims.to_dict(),
   191	            key=self.private_key,  # type: ignore
   192	            algorithm=ADMIN_JWT_ALGORITHM,
   193	        )
   194	        return token
   195	
   196	    def verify_admin_token(self, token: str) -> AdminTokenClaims:
   197	        """
   198	        Verify an Ed25519 Administrative Access Token signature, expiration, issuer, and audience.
   199	        Returns typed AdminTokenClaims on success or raises domain security exceptions.
   200	        """
   201	        if self.public_key is None:
   202	            raise RuntimeError("Admin public key is not initialized")
   203	        if not isinstance(token, str) or not token.strip():
   204	            raise InvalidAdminTokenError("Token cannot be empty")
   205	
   206	        try:
   207	            payload = jwt.decode(
   208	                jwt=token,
   209	                key=self.public_key,  # type: ignore
   210	                algorithms=[ADMIN_JWT_ALGORITHM],
   211	                audience=self.audience,
   212	                issuer=self.issuer,
   213	                options={
   214	                    "require": ["sub", "username", "role", "iss", "aud", "iat", "nbf", "exp", "jti"],
   215	                    "verify_signature": True,
   216	                    "verify_exp": True,
   217	                    "verify_nbf": True,
   218	                    "verify_iat": True,
   219	                    "verify_aud": True,
   220	                    "verify_iss": True,
   221	                },
   222	            )
   223	            return AdminTokenClaims.from_dict(payload)
   224	        except jwt.ExpiredSignatureError as exc:
   225	            raise AdminTokenExpiredError("Administrative access token has expired") from exc
   226	        except jwt.InvalidTokenError as exc:
   227	            raise InvalidAdminTokenError("Administrative access token signature or claims are invalid") from exc
   228	        except ValueError as exc:
   229	            raise InvalidAdminTokenError(f"Malformed token payload: {exc}") from exc
   230	        except Exception as exc:
   231	            raise InvalidAdminTokenError("Unexpected error during token verification") from exc

```


## Assistant

<thinking>
The JWT implementation looks good with its strict algorithm allowlist and proper issuer/audience validation, so now I'm moving through the dependency injection layer to verify how the authentication middleware is wired up across the different services and admin routes.
</thinking>

**Tool Call: Read file `billing-server\app\dependencies.py`**
Status: Completed

```OverREALITY/billing-server/app/dependencies.py
     1	"""
     2	dependencies.py — Centralized dependency injection providers for OverREALITY API services.
     3	
     4	Encapsulates database session wiring and service instantiation so routers never touch
     5	repositories or SQLAlchemy sessions directly. Also provides JWT bearer token authentication
     6	and active account context for protected endpoints.
     7	"""
     8	from __future__ import annotations
     9	
    10	import logging
    11	import uuid
    12	from fastapi import Depends, HTTPException, Request, status
    13	from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    14	from sqlalchemy.ext.asyncio import AsyncSession
    15	
    16	from app.database import get_db
    17	from app.models.account import Account
    18	from app.repositories import (
    19	    AccountRepository,
    20	    DeviceRepository,
    21	    RefreshTokenRepository,
    22	    ConnectionSignalRepository,
    23	    AdminUserRepository,
    24	)
    25	from app.config import settings
    26	from app.security.jwt_service import JWTService
    27	from app.security.admin_password import AdminPasswordService
    28	from app.security.admin_jwt import AdminJWTService
    29	from app.services import (
    30	    AuthenticationService,
    31	    DeviceService,
    32	    RefreshTokenService,
    33	    ConnectionSignalService,
    34	    AdminAuthenticationService,
    35	    AdminAccountService,
    36	    MarzbanProvisioningProvider,
    37	    ProvisioningService,
    38	    CredentialService,
    39	    SubscriptionService,
    40	    PaymentService,
    41	    WebhookService,
    42	    SubscriptionPlanService,
    43	    BillingService,
    44	    RazorpayProvider,
    45	    AdminBillingService,
    46	)
    47	from app.models.admin_user import AdminUser
    48	
    49	
    50	
    51	logger = logging.getLogger(__name__)
    52	
    53	# Bearer authentication schemes for OpenAPI Swagger documentation
    54	customer_oauth2_scheme = HTTPBearer(
    55	    auto_error=False,
    56	    scheme_name="CustomerBearer",
    57	    description="Customer Ed25519 Access JWT",
    58	)
    59	oauth2_scheme = customer_oauth2_scheme  # backward compatibility alias
    60	
    61	admin_oauth2_scheme = HTTPBearer(
    62	    auto_error=False,
    63	    scheme_name="AdminBearer",
    64	    description="Administrative Ed25519 Access JWT",
    65	)
    66	
    67	# Singleton JWT service instance (stateless Ed25519 signer/verifier)
    68	# Instantiated once on first request; loads keys from disk once and never regenerates.
    69	_jwt_service: JWTService | None = None
    70	_admin_password_service: AdminPasswordService | None = None
    71	_admin_jwt_service: AdminJWTService | None = None
    72	
    73	
    74	def get_jwt_service() -> JWTService:
    75	    """Dependency provider yielding the stateless singleton JWTService."""
    76	    global _jwt_service
    77	    if _jwt_service is None:
    78	        _jwt_service = JWTService()
    79	    return _jwt_service
    80	
    81	
    82	def get_admin_password_service() -> AdminPasswordService:
    83	    """Dependency provider yielding the stateless singleton AdminPasswordService."""
    84	    global _admin_password_service
    85	    if _admin_password_service is None:
    86	        _admin_password_service = AdminPasswordService()
    87	    return _admin_password_service
    88	
    89	
    90	def get_admin_jwt_service() -> AdminJWTService:
    91	    """Dependency provider yielding the stateless singleton AdminJWTService."""
    92	    global _admin_jwt_service
    93	    if _admin_jwt_service is None:
    94	        _admin_jwt_service = AdminJWTService()
    95	    return _admin_jwt_service
    96	
    97	
    98	async def get_account_repo(session: AsyncSession = Depends(get_db)) -> AccountRepository:
    99	    """Dependency provider yielding AccountRepository tied to the request session."""
   100	    return AccountRepository(session)
   101	
   102	
   103	async def get_refresh_repo(session: AsyncSession = Depends(get_db)) -> RefreshTokenRepository:
   104	    """Dependency provider yielding RefreshTokenRepository tied to the request session."""
   105	    return RefreshTokenRepository(session)
   106	
   107	
   108	async def get_auth_service(
   109	    account_repo: AccountRepository = Depends(get_account_repo),
   110	) -> AuthenticationService:
   111	    """Dependency provider yielding AuthenticationService."""
   112	    return AuthenticationService(account_repo)
   113	
   114	
   115	async def get_refresh_service(
   116	    refresh_repo: RefreshTokenRepository = Depends(get_refresh_repo),
   117	) -> RefreshTokenService:
   118	    """Dependency provider yielding RefreshTokenService."""
   119	    return RefreshTokenService(refresh_repo)
   120	
   121	
   122	async def get_device_repo(session: AsyncSession = Depends(get_db)) -> DeviceRepository:
   123	    """Dependency provider yielding DeviceRepository tied to the request session."""
   124	    return DeviceRepository(session)
   125	
   126	
   127	async def get_device_service(
   128	    device_repo: DeviceRepository = Depends(get_device_repo),
   129	    account_repo: AccountRepository = Depends(get_account_repo),
   130	) -> DeviceService:
   131	    """Dependency provider yielding DeviceService."""
   132	    return DeviceService(device_repo, account_repo)
   133	
   134	
   135	async def get_signal_repo(
   136	    session: AsyncSession = Depends(get_db),
   137	) -> ConnectionSignalRepository:
   138	    """Dependency provider yielding ConnectionSignalRepository tied to request session."""
   139	    return ConnectionSignalRepository(session)
   140	
   141	
   142	async def get_signal_service(
   143	    signal_repo: ConnectionSignalRepository = Depends(get_signal_repo),
   144	) -> ConnectionSignalService:
   145	    """Dependency provider yielding ConnectionSignalService."""
   146	    return ConnectionSignalService(signal_repo)
   147	
   148	
   149	
   150	async def get_current_account(
   151	    request: Request,
   152	    _bearer: HTTPAuthorizationCredentials | None = Depends(oauth2_scheme),
   153	    auth_service: AuthenticationService = Depends(get_auth_service),
   154	    jwt_service: JWTService = Depends(get_jwt_service),
   155	) -> Account:
   156	    """
   157	    Dependency yielding the authenticated and validated Account model from an HTTP Authorization Bearer token.
   158	
   159	    Requires Authorization: Bearer <token>. Rejects missing header, malformed header, missing Bearer prefix,
   160	    empty token, invalid/expired JWT, or inactive backing accounts with clean HTTP 401 Unauthorized responses.
   161	    """
   162	    auth_header = request.headers.get("Authorization")
   163	    if not auth_header:
   164	        logger.info("Authentication failed")
   165	        raise HTTPException(
   166	            status_code=status.HTTP_401_UNAUTHORIZED,
   167	            detail="Authentication failed or token invalid",
   168	        )
   169	
   170	    parts = auth_header.split()
   171	    if len(parts) != 2 or parts[0] != "Bearer":
   172	        logger.info("Authentication failed")
   173	        raise HTTPException(
   174	            status_code=status.HTTP_401_UNAUTHORIZED,
   175	            detail="Authentication failed or token invalid",
   176	        )
   177	
   178	    token = parts[1].strip()
   179	    if not token:
   180	        logger.info("Authentication failed")
   181	        raise HTTPException(
   182	            status_code=status.HTTP_401_UNAUTHORIZED,
   183	            detail="Authentication failed or token invalid",
   184	        )
   185	
   186	    try:
   187	        claims = jwt_service.verify_access_token(token)
   188	    except Exception:
   189	        logger.info("Token invalid")
   190	        raise HTTPException(
   191	            status_code=status.HTTP_401_UNAUTHORIZED,
   192	            detail="Authentication failed or token invalid",
   193	        )
   194	
   195	    try:
   196	        account = await auth_service.get_active_account_by_uuid(uuid.UUID(claims.sub))
   197	    except Exception:
   198	        logger.info("Authentication failed")
   199	        raise HTTPException(
   200	            status_code=status.HTTP_401_UNAUTHORIZED,
   201	            detail="Authentication failed or token invalid",
   202	        )
   203	
   204	    logger.info("Authentication succeeded")
   205	    return account
   206	
   207	
   208	async def get_admin_repo(session: AsyncSession = Depends(get_db)) -> AdminUserRepository:
   209	    """Dependency provider yielding AdminUserRepository tied to the request session."""
   210	    return AdminUserRepository(session)
   211	
   212	
   213	async def get_admin_auth_service(
   214	    admin_repo: AdminUserRepository = Depends(get_admin_repo),
   215	    password_service: AdminPasswordService = Depends(get_admin_password_service),
   216	    jwt_service: AdminJWTService = Depends(get_admin_jwt_service),
   217	) -> AdminAuthenticationService:
   218	    """Dependency provider yielding AdminAuthenticationService."""
   219	    return AdminAuthenticationService(admin_repo, password_service, jwt_service)
   220	
   221	
   222	async def get_current_admin(
   223	    request: Request,
   224	    _bearer: HTTPAuthorizationCredentials | None = Depends(admin_oauth2_scheme),
   225	    admin_auth_service: AdminAuthenticationService = Depends(get_admin_auth_service),
   226	    admin_jwt_service: AdminJWTService = Depends(get_admin_jwt_service),
   227	) -> AdminUser:
   228	    """
   229	    Dependency yielding the authenticated and validated AdminUser model from an HTTP Authorization Bearer token.
   230	    Strictly isolated from customer account authentication.
   231	    """
   232	    auth_header = request.headers.get("Authorization")
   233	    if not auth_header:
   234	        logger.info("Admin authentication failed")
   235	        raise HTTPException(
   236	            status_code=status.HTTP_401_UNAUTHORIZED,
   237	            detail="Authentication failed or token invalid",
   238	        )
   239	
   240	    parts = auth_header.split()
   241	    if len(parts) != 2 or parts[0] != "Bearer":
   242	        logger.info("Admin authentication failed")
   243	        raise HTTPException(
   244	            status_code=status.HTTP_401_UNAUTHORIZED,
   245	            detail="Authentication failed or token invalid",
   246	        )
   247	
   248	    token = parts[1].strip()
   249	    if not token:
   250	        logger.info("Admin authentication failed")
   251	        raise HTTPException(
   252	            status_code=status.HTTP_401_UNAUTHORIZED,
   253	            detail="Authentication failed or token invalid",
   254	        )
   255	
   256	    try:
   257	        claims = admin_jwt_service.verify_admin_token(token)
   258	    except Exception:
   259	        logger.info("Admin token invalid")
   260	        raise HTTPException(
   261	            status_code=status.HTTP_401_UNAUTHORIZED,
   262	            detail="Authentication failed or token invalid",
   263	        )
   264	
   265	    try:
   266	        admin = await admin_auth_service.get_active_admin_by_id(uuid.UUID(claims.sub))
   267	    except Exception:
   268	        logger.info("Admin authentication failed")
   269	        raise HTTPException(
   270	            status_code=status.HTTP_401_UNAUTHORIZED,
   271	            detail="Authentication failed or token invalid",
   272	        )
   273	
   274	    logger.info("Admin authentication succeeded")
   275	    return admin
   276	
   277	
   278	async def get_current_admin_optional(
   279	    request: Request,
   280	    admin_auth_service: AdminAuthenticationService = Depends(get_admin_auth_service),
   281	    admin_jwt_service: AdminJWTService = Depends(get_admin_jwt_service),
   282	) -> AdminUser | None:
   283	    """Optionally returns AdminUser if a valid Admin Bearer token is provided, otherwise None."""
   284	    auth_header = request.headers.get("Authorization")
   285	    if not auth_header:
   286	        return None
   287	    parts = auth_header.split()
   288	    if len(parts) != 2 or parts[0] != "Bearer":
   289	        return None
   290	    try:
   291	        token = parts[1]
   292	        claims = admin_jwt_service.verify_admin_token(token)
   293	        return await admin_auth_service.get_active_admin_by_id(uuid.UUID(claims.sub))
   294	    except Exception:
   295	        return None
   296	
   297	
   298	async def get_admin_account_service(
   299	    account_repo: AccountRepository = Depends(get_account_repo),
   300	    refresh_repo: RefreshTokenRepository = Depends(get_refresh_repo),
   301	) -> AdminAccountService:
   302	    """Dependency provider yielding AdminAccountService for administrative account management."""
   303	    return AdminAccountService(account_repo, refresh_repo)
   304	
   305	
   306	async def require_super_admin(
   307	    admin: AdminUser = Depends(get_current_admin),
   308	) -> AdminUser:
   309	    """
   310	    FastAPI dependency that enforces super-admin privilege.
   311	    Raises HTTP 403 Forbidden if the authenticated admin is not a super-admin.
   312	    Read-only operations use get_current_admin(); write operations use require_super_admin().
   313	    """
   314	    if not admin.is_super_admin:
   315	        logger.info("Admin access denied: super-admin privilege required")
   316	        raise HTTPException(
   317	            status_code=status.HTTP_403_FORBIDDEN,
   318	            detail="Super-admin privilege required for this operation",
   319	        )
   320	    return admin
   321	
   322	
   323	_marzban_provider: MarzbanProvisioningProvider | None = None
   324	
   325	
   326	def get_marzban_provider() -> MarzbanProvisioningProvider:
   327	    """Yield singleton Marzban provisioning provider configured with app settings."""
   328	    global _marzban_provider
   329	    if _marzban_provider is None:
   330	        _marzban_provider = MarzbanProvisioningProvider()
   331	    return _marzban_provider
   332	
   333	
   334	async def get_provisioning_service(
   335	    session: AsyncSession = Depends(get_db),
   336	    provider: MarzbanProvisioningProvider = Depends(get_marzban_provider),
   337	) -> ProvisioningService:
   338	    """Yield ProvisioningService instance wired to current database session, Marzban provider, and CredentialService."""
   339	    prov_svc = ProvisioningService(session, provider)
   340	    cred_svc = CredentialService(session, prov_svc)
   341	    prov_svc.credential_service = cred_svc
   342	    return prov_svc
   343	
   344	
   345	async def get_credential_service(
   346	    session: AsyncSession = Depends(get_db),
   347	    provisioning_service: ProvisioningService = Depends(get_provisioning_service),
   348	) -> CredentialService:
   349	    """Yield CredentialService instance for VPN credential lifecycle and config generation."""
   350	    if provisioning_service.credential_service:
   351	        return provisioning_service.credential_service
   352	    return CredentialService(session, provisioning_service)
   353	
   354	
   355	async def get_subscription_service(
   356	    session: AsyncSession = Depends(get_db),
   357	    provisioning_service: ProvisioningService = Depends(get_provisioning_service),
   358	) -> SubscriptionService:
   359	    """Yield SubscriptionService wired to current database session and ProvisioningService."""
   360	    return SubscriptionService(session, provisioning_service=provisioning_service)
   361	
   362	
   363	_razorpay_provider: RazorpayProvider | None = None
   364	
   365	
   366	def get_razorpay_provider() -> RazorpayProvider:
   367	    """Yield singleton Razorpay payment provider."""
   368	    global _razorpay_provider
   369	    if _razorpay_provider is None:
   370	        _razorpay_provider = RazorpayProvider(settings)
   371	    return _razorpay_provider
   372	
   373	
   374	
   375	async def get_payment_service(
   376	    session: AsyncSession = Depends(get_db),
   377	    provider: RazorpayProvider = Depends(get_razorpay_provider),
   378	    subscription_service: SubscriptionService = Depends(get_subscription_service),
   379	) -> PaymentService:
   380	    """Yield PaymentService wired to current session, gateway provider, and SubscriptionService."""
   381	    return PaymentService(session, provider, subscription_service=subscription_service)
   382	
   383	
   384	async def get_webhook_service(
   385	    payment_service: PaymentService = Depends(get_payment_service),
   386	) -> WebhookService:
   387	    """Yield WebhookService wired to PaymentService."""
   388	    return WebhookService(payment_service)
   389	
   390	
   391	def get_plan_service() -> SubscriptionPlanService:
   392	    """Yield SubscriptionPlanService."""
   393	    return SubscriptionPlanService()
   394	
   395	
   396	async def get_billing_service(
   397	    subscription_service: SubscriptionService = Depends(get_subscription_service),
   398	    payment_service: PaymentService = Depends(get_payment_service),
   399	    plan_service: SubscriptionPlanService = Depends(get_plan_service),
   400	) -> BillingService:
   401	    """Yield BillingService wired to SubscriptionService, PaymentService, and SubscriptionPlanService."""
   402	    return BillingService(subscription_service, payment_service, plan_service)
   403	
   404	
   405	async def get_admin_billing_service(
   406	    session: AsyncSession = Depends(get_db),
   407	    subscription_service: SubscriptionService = Depends(get_subscription_service),
   408	    payment_service: PaymentService = Depends(get_payment_service),
   409	    provisioning_service: ProvisioningService = Depends(get_provisioning_service),
   410	) -> AdminBillingService:
   411	    """Yield AdminBillingService wired to session and domain services."""
   412	    return AdminBillingService(session, subscription_service, payment_service, provisioning_service)
   413	
   414	
   415	
   416	

```


**Tool Call: Read file `billing-server\app\services\authentication.py`**
Status: Completed

```OverREALITY/billing-server/app/services/authentication.py
     1	"""
     2	authentication.py — Core Authentication Service
     3	
     4	Provides a pure domain service responsible for answering:
     5	"Can this Account ID + Master Token authenticate?"
     6	
     7	ARCHITECTURE & DESIGN DECISIONS:
     8	1. Why authentication returns a typed result instead of bool:
     9	   Returning a simple boolean (`True`/`False`) cannot differentiate between failure modes (e.g., non-existent account
    10	   vs. invalid token vs. expired subscription vs. suspended subscription). A typed result (`AuthenticationResult`
    11	   containing an `AuthenticationReason` enum) provides clear, structured reasons that allow upper layers (like API endpoints
    12	   or audit loggers) to handle each case appropriately (e.g., returning specific error messages or status codes) while
    13	   keeping the core authentication service strictly decoupled from HTTP protocol details and status codes.
    14	
    15	2. Why account enumeration resistance matters (Timing Attack Defense):
    16	   If checking a non-existent account returned immediately without hashing the provided Master Token, an attacker could send
    17	   thousands of authentication requests with random Account IDs and measure response execution times. Requests taking ~1ms
    18	   would indicate non-existent accounts, whereas requests taking ~3ms (due to SHA-256 hashing) would reveal valid Account IDs.
    19	   By performing `verify_master_token` against a dummy hash when `account is None`, we ensure the execution time is
    20	   approximately identical to a valid account lookup, completely preventing account enumeration via network timing side channels.
    21	
    22	3. Why repositories are used instead of direct SQL:
    23	   Repositories (`AccountRepository`) encapsulate database access, queries, and SQLAlchemy session management. By depending only
    24	   on the repository layer, the authentication service remains isolated from schema internals, SQL dialects, and session
    25	   lifecycle management, while ensuring all database errors are cleanly translated into domain service exceptions without
    26	   leaking ORM internals.
    27	
    28	4. Why we avoid premature optimization:
    29	   This service is expected to handle tens or hundreds of authentications per minute, not millions. Favoring clear, auditable,
    30	   and linear code over clever performance hacks ensures maintainability and directly contributes to thorough security reviews.
    31	"""
    32	from __future__ import annotations
    33	
    34	import enum
    35	import logging
    36	import uuid
    37	from dataclasses import dataclass
    38	from datetime import datetime, timezone
    39	
    40	from app.exceptions import RepositoryError
    41	from app.models.account import Account
    42	from app.models.base import SubscriptionStatus
    43	from app.repositories.account_repository import AccountRepository
    44	from app.security import verify_master_token, SHA256_HEX_LENGTH
    45	from app.services.exceptions import AuthenticationServiceError, AccountNotActiveError
    46	
    47	logger = logging.getLogger(__name__)
    48	
    49	# Dummy SHA-256 hash used for constant-time timing attack defense when an account does not exist.
    50	# 64 hexadecimal zero characters matching the format of a valid Master Token hash.
    51	DUMMY_MASTER_TOKEN_HASH: str = "0" * SHA256_HEX_LENGTH
    52	
    53	
    54	class AuthenticationReason(str, enum.Enum):
    55	    """
    56	    Structured reasons for authentication outcomes.
    57	    Avoids returning arbitrary strings or ambiguous booleans.
    58	    """
    59	    SUCCESS = "SUCCESS"
    60	    ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
    61	    INVALID_MASTER_TOKEN = "INVALID_MASTER_TOKEN"
    62	    SUBSCRIPTION_EXPIRED = "SUBSCRIPTION_EXPIRED"
    63	    ACCOUNT_SUSPENDED = "ACCOUNT_SUSPENDED"
    64	    ACCOUNT_PENDING = "ACCOUNT_PENDING"
    65	
    66	
    67	@dataclass(frozen=True)
    68	class AuthenticationResult:
    69	    """
    70	    Typed result returned by AuthenticationService.authenticate().
    71	    Encapsulates success status, structured reason enum, and the authenticated Account model (if applicable).
    72	    """
    73	    success: bool
    74	    reason: AuthenticationReason
    75	    account: Account | None = None
    76	
    77	
    78	class AuthenticationService:
    79	    """
    80	    Core authentication service class.
    81	    Strictly independent of FastAPI routes, Request/Response objects, JWTs, refresh tokens, and middleware.
    82	    """
    83	
    84	    def __init__(self, account_repository: AccountRepository) -> None:
    85	        self.account_repo = account_repository
    86	
    87	    async def get_account(self, account_uuid: uuid.UUID) -> Account:
    88	        """
    89	        Retrieve an Account model by its internal database UUID.
    90	        Translates repository exceptions into domain service exceptions.
    91	        """
    92	        try:
    93	            return await self.account_repo.get_by_id_or_raise(account_uuid)
    94	        except RepositoryError as exc:
    95	            logger.error("Repository error while retrieving account")
    96	            raise AuthenticationServiceError("Database operation failed during account retrieval") from exc
    97	
    98	    async def get_active_account_by_uuid(self, account_uuid: uuid.UUID) -> Account:
    99	        """
   100	        Retrieve an Account by UUID and validate that it is active and not expired.
   101	        Raises AccountNotActiveError (or EntityNotFoundError) if deleted,
   102	        suspended, pending, expired, or otherwise invalid.
   103	        """
   104	        account = await self.get_account(account_uuid)
   105	
   106	        if account.status == SubscriptionStatus.SUSPENDED:
   107	            logger.info("Token validation failed: account suspended")
   108	            raise AccountNotActiveError("Account suspended")
   109	
   110	        if account.status == SubscriptionStatus.PENDING:
   111	            logger.info("Token validation failed: account pending")
   112	            raise AccountNotActiveError("Account pending")
   113	
   114	        if account.status == SubscriptionStatus.EXPIRED:
   115	            logger.info("Token validation failed: subscription expired")
   116	            raise AccountNotActiveError("Subscription expired")
   117	
   118	        if account.status != SubscriptionStatus.ACTIVE:
   119	            logger.info("Token validation failed: account inactive")
   120	            raise AccountNotActiveError("Account inactive")
   121	
   122	        if account.subscription_expires_at is not None:
   123	            now = datetime.now(timezone.utc)
   124	            expires_at = account.subscription_expires_at
   125	            if expires_at.tzinfo is None:
   126	                expires_at = expires_at.replace(tzinfo=timezone.utc)
   127	            if now >= expires_at:
   128	                logger.info("Token validation failed: subscription timestamp expired")
   129	                raise AccountNotActiveError("Subscription timestamp expired")
   130	
   131	        return account
   132	
   133	    async def authenticate(self, account_id: str, master_token: str) -> AuthenticationResult:
   134	        """
   135	        Authenticate an Account ID and Master Token credential pair against repository state.
   136	
   137	        Performs the following sequence:
   138	        1. Lookup account by Account ID (using repository).
   139	        2. If account not found -> execute timing attack defense -> return ACCOUNT_NOT_FOUND.
   140	        3. Verify Master Token against stored SHA-256 hash -> if invalid -> return INVALID_MASTER_TOKEN.
   141	        4. Check subscription status -> if SUSPENDED or PENDING -> return respective failure reason.
   142	        5. Check subscription expiry timestamp -> if expired -> return SUBSCRIPTION_EXPIRED.
   143	        6. Return SUCCESS with authenticated account.
   144	
   145	        LOGGING INVARIANT:
   146	        Never logs Account IDs, Master Tokens, or token hashes. Logs only generic outcome descriptions.
   147	        """
   148	        # Step 1: Find Account via repository
   149	        try:
   150	            account = await self.account_repo.get_by_account_id(account_id)
   151	        except RepositoryError as e:
   152	            logger.error("Authentication failed due to repository error")
   153	            raise AuthenticationServiceError("Database error during authentication lookup") from e
   154	        except Exception as e:
   155	            logger.error("Authentication failed due to unexpected database error")
   156	            raise AuthenticationServiceError("Unexpected database error during authentication lookup") from e
   157	
   158	        # Step 2: Not Found check with Timing Attack Defense
   159	        if account is None:
   160	            # TIMING ATTACK DEFENSE:
   161	            # Always execute verify_master_token against a dummy hash so that hashing and constant-time
   162	            # comparison execute even when the account does not exist. This prevents account enumeration
   163	            # based on response timing differences.
   164	            verify_master_token(master_token, DUMMY_MASTER_TOKEN_HASH)
   165	            logger.info("Authentication failed: invalid credentials")
   166	            return AuthenticationResult(
   167	                success=False,
   168	                reason=AuthenticationReason.ACCOUNT_NOT_FOUND,
   169	                account=None,
   170	            )
   171	
   172	        # Step 3: Verify Master Token
   173	        if not verify_master_token(master_token, account.master_token_hash):
   174	            logger.info("Authentication failed: invalid credentials")
   175	            return AuthenticationResult(
   176	                success=False,
   177	                reason=AuthenticationReason.INVALID_MASTER_TOKEN,
   178	                account=None,
   179	            )
   180	
   181	        # Step 4: Subscription Status check
   182	        if account.status == SubscriptionStatus.SUSPENDED:
   183	            logger.info("Authentication failed: suspended account")
   184	            return AuthenticationResult(
   185	                success=False,
   186	                reason=AuthenticationReason.ACCOUNT_SUSPENDED,
   187	                account=account,
   188	            )
   189	
   190	        if account.status == SubscriptionStatus.PENDING:
   191	            logger.info("Authentication failed: pending subscription")
   192	            return AuthenticationResult(
   193	                success=False,
   194	                reason=AuthenticationReason.ACCOUNT_PENDING,
   195	                account=account,
   196	            )
   197	
   198	        if account.status == SubscriptionStatus.EXPIRED:
   199	            logger.info("Authentication failed: expired subscription")
   200	            return AuthenticationResult(
   201	                success=False,
   202	                reason=AuthenticationReason.SUBSCRIPTION_EXPIRED,
   203	                account=account,
   204	            )
   205	
   206	        if account.status != SubscriptionStatus.ACTIVE:
   207	            logger.info("Authentication failed: expired subscription")
   208	            return AuthenticationResult(
   209	                success=False,
   210	                reason=AuthenticationReason.SUBSCRIPTION_EXPIRED,
   211	                account=account,
   212	            )
   213	
   214	        # Step 5: Subscription Expiry timestamp check
   215	        if account.subscription_expires_at is not None:
   216	            now = datetime.now(timezone.utc)
   217	            expires_at = account.subscription_expires_at
   218	            if expires_at.tzinfo is None:
   219	                expires_at = expires_at.replace(tzinfo=timezone.utc)
   220	            if now >= expires_at:
   221	                logger.info("Authentication failed: expired subscription")
   222	                return AuthenticationResult(
   223	                    success=False,
   224	                    reason=AuthenticationReason.SUBSCRIPTION_EXPIRED,
   225	                    account=account,
   226	                )
   227	
   228	        # Step 6: Authentication Success
   229	        logger.info("Authentication succeeded")
   230	        return AuthenticationResult(
   231	            success=True,
   232	            reason=AuthenticationReason.SUCCESS,
   233	            account=account,
   234	        )

```


**Tool Call: Read file `billing-server\app\services\refresh_tokens.py`**
Status: Completed

```OverREALITY/billing-server/app/services/refresh_tokens.py
     1	"""
     2	refresh_tokens.py — Core Refresh Token Rotation (RTR) Engine.
     3	
     4	Pure domain service responsible for issuing, validating, rotating, and revoking long-lived refresh tokens.
     5	Strictly decoupled from HTTP frameworks, FastAPI routing, middleware, and request/response objects.
     6	
     7	ARCHITECTURAL DESIGN & SECURITY REASONING:
     8	
     9	1. WHY SHA-256 IS SUFFICIENT FOR REFRESH TOKENS:
    10	   Refresh tokens are generated by the server via OS CSPRNG (`secrets.token_hex(32)`), providing 256 bits of
    11	   true high entropy. Unlike human-chosen passwords, a 256-bit CSPRNG secret has 2^256 possible values, making
    12	   offline dictionary attacks, rainbow tables, and brute-force guessing mathematically impossible. Therefore,
    13	   memory-hard Key Derivation Functions (like Argon2id or bcrypt) are unnecessary and would only cause severe
    14	   CPU/RAM exhaustion under high authentication load. Standard SHA-256 hashing provides optimal verification
    15	   speed and collision resistance.
    16	
    17	2. WHY REFRESH TOKENS ARE ROTATED:
    18	   Session rotation minimizes the window of vulnerability if a token is intercepted or stolen. Every time a client
    19	   requests a new short-lived access token, the current refresh token is invalidated and replaced with a newly
    20	   issued refresh token. Once rotated, an old refresh token can never be used again.
    21	
    22	3. WHY REPLAY ATTACKS REVOKE EVERY SESSION:
    23	   If an attacker intercepts an old refresh token and attempts to use it after the legitimate client has already
    24	   rotated it (or if the legitimate client attempts to use it after an attacker has stolen and rotated it), our
    25	   system detects that an already-revoked valid token (`is_revoked == True`) is being presented. This is direct
    26	   evidence of token reuse and potential session compromise. To protect the user's account, the system immediately
    27	   revokes all active refresh tokens for that account, forcing a clean re-authentication across all devices.
    28	   IMPORTANT DISTINCTION: An entirely random or unknown token string simply raises `RefreshTokenNotFoundError`
    29	   without triggering account-wide revocation. This prevents denial-of-service (DoS) attacks where malicious actors
    30	   could otherwise log out users by submitting random token strings.
    31	
    32	4. WHY TRANSACTIONS ARE MANDATORY FOR ROTATION:
    33	   Rotating a refresh token involves two database modifications: revoking the old token hash and inserting the new
    34	   token hash. If these steps were executed without atomic transaction guarantees, server crashes or database errors
    35	   could leave the database in an inconsistent state (e.g., old token revoked but new token missing, causing accidental
    36	   user lockout; or both old and new tokens active, violating single-use rotation guarantees). Executing both updates
    37	   within a single SQLAlchemy transaction ensures all-or-nothing atomicity.
    38	
    39	5. WHY REFRESH TOKENS ARE LONGER LIVED THAN ACCESS TOKENS:
    40	   Access tokens (JWTs) are stateless and verified locally without database queries, making them fast but impossible
    41	   to revoke individually before expiration. Therefore, access tokens are given short lifespans (e.g., 15 minutes) to
    42	   limit damage if compromised. Refresh tokens, conversely, require a database query on every rotation and are stored
    43	   securely as hashes. Their longer lifespan (30 days) provides user convenience (persistent login sessions) while
    44	   maintaining security through rotation, device binding, and instant database revocation.
    45	"""
    46	
    47	from __future__ import annotations
    48	
    49	import logging
    50	import uuid
    51	from dataclasses import dataclass
    52	from datetime import datetime, timezone, timedelta
    53	from typing import TYPE_CHECKING
    54	
    55	from app.exceptions import DatabaseOperationError, RepositoryError
    56	from app.models import RefreshToken
    57	from app.repositories import RefreshTokenRepository
    58	from app.security import (
    59	    generate_refresh_token,
    60	    hash_refresh_token,
    61	    REFRESH_TOKEN_EXPIRE_DAYS,
    62	)
    63	from app.services.exceptions import (
    64	    ServiceError,
    65	    RefreshTokenNotFoundError,
    66	    RefreshTokenExpiredError,
    67	    RefreshTokenRevokedError,
    68	    RefreshTokenReplayError,
    69	)
    70	
    71	if TYPE_CHECKING:
    72	    pass
    73	
    74	logger = logging.getLogger(__name__)
    75	
    76	
    77	@dataclass(frozen=True)
    78	class RefreshTokenResult:
    79	    """Typed domain result returned when a new refresh token is issued."""
    80	    token: str
    81	    expires_at: datetime
    82	    device_guid: str
    83	    account_id: uuid.UUID
    84	
    85	
    86	@dataclass(frozen=True)
    87	class RefreshRotationResult:
    88	    """Typed domain result returned upon successful refresh token rotation."""
    89	    new_token: str
    90	    expires_at: datetime
    91	    device_guid: str
    92	    account_id: uuid.UUID
    93	
    94	
    95	@dataclass(frozen=True)
    96	class RefreshTokenInfo:
    97	    """Typed domain metadata representing a verified refresh token session."""
    98	    token_id: uuid.UUID
    99	    account_id: uuid.UUID
   100	    device_guid: str
   101	    expires_at: datetime
   102	    created_at: datetime
   103	    is_revoked: bool
   104	
   105	
   106	class RefreshTokenService:
   107	    """
   108	    Core domain service managing Refresh Token Rotation (RTR), session lifecycle,
   109	    device binding, and replay attack detection.
   110	    """
   111	
   112	    def __init__(self, repo: RefreshTokenRepository) -> None:
   113	        self.repo = repo
   114	
   115	    async def _get_and_validate_token(self, plaintext_token: str, *, for_update: bool = False) -> RefreshToken:
   116	        """
   117	        Validate token existence, expiration, and check for replay attack evidence.
   118	        If for_update=True, acquires row-level exclusive lock to prevent concurrent rotation races.
   119	
   120	        Replay Attack Invariant:
   121	        - If the token hash does not exist in the database, it is unknown/unrecognized.
   122	          We raise `RefreshTokenNotFoundError` WITHOUT revoking account sessions.
   123	        - If the token hash exists AND `is_revoked == True`, it was previously valid but revoked.
   124	          This is direct evidence of reuse (replay attack). We immediately revoke all account
   125	          sessions and raise `RefreshTokenReplayError`.
   126	        """
   127	        try:
   128	            token_hash = hash_refresh_token(plaintext_token)
   129	        except (TypeError, ValueError) as exc:
   130	            raise RefreshTokenNotFoundError("Invalid refresh token format") from exc
   131	
   132	        try:
   133	            entity = await self.repo.get_by_hash(token_hash, for_update=for_update)
   134	        except RepositoryError as exc:
   135	            raise RefreshTokenServiceError("Database error querying refresh token") from exc
   136	
   137	        if entity is None:
   138	            # Entirely random or unknown token -> simple failure, NO mass logout
   139	            raise RefreshTokenNotFoundError("Refresh token not found or unrecognized")
   140	
   141	        if entity.is_revoked:
   142	            # Replay detection: reuse of a legitimately issued token that was previously revoked!
   143	            logger.warning("Replay detected! Revoking all sessions for account.")
   144	            try:
   145	                await self.repo.revoke_all_for_account(entity.account_id)
   146	            except RepositoryError as exc:
   147	                raise RefreshTokenServiceError("Database error during replay mass revocation") from exc
   148	            raise RefreshTokenReplayError(
   149	                "Replay attack detected: reuse of revoked refresh token. All sessions for this account have been revoked.",
   150	                account_id=entity.account_id,
   151	                device_guid=entity.device_guid,
   152	            )
   153	
   154	        # Defensive timezone normalization: DateTime(timezone=True) should always return
   155	        # tz-aware datetimes, but guard against driver-layer inconsistencies.
   156	        expires_at = entity.expires_at
   157	        if expires_at.tzinfo is None:
   158	            expires_at = expires_at.replace(tzinfo=timezone.utc)
   159	        if expires_at < datetime.now(timezone.utc):
   160	            raise RefreshTokenExpiredError(
   161	                "Refresh token has expired",
   162	                account_id=entity.account_id,
   163	                device_guid=entity.device_guid,
   164	            )
   165	
   166	        return entity
   167	
   168	    async def issue_refresh_token(self, account_id: uuid.UUID, device_guid: str) -> RefreshTokenResult:
   169	        """
   170	        Issue a new 256-bit CSPRNG refresh token bound to an Account ID and Device GUID.
   171	        Stores only the SHA-256 digest in the database.
   172	        """
   173	        plaintext_token = generate_refresh_token()
   174	        token_hash = hash_refresh_token(plaintext_token)
   175	        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
   176	
   177	        try:
   178	            await self.repo.create(
   179	                account_id=account_id,
   180	                device_guid=device_guid,
   181	                token_hash=token_hash,
   182	                expires_at=expires_at,
   183	            )
   184	        except RepositoryError as exc:
   185	            raise RefreshTokenServiceError("Failed to issue refresh token in database") from exc
   186	
   187	        logger.info("Refresh token issued")
   188	        return RefreshTokenResult(
   189	            token=plaintext_token,
   190	            expires_at=expires_at,
   191	            device_guid=device_guid,
   192	            account_id=account_id,
   193	        )
   194	
   195	    async def verify_refresh_token(self, plaintext_token: str) -> RefreshTokenInfo:
   196	        """
   197	        Verify a plaintext refresh token, ensuring it exists, is active, and is not expired.
   198	        Returns typed domain metadata without leaking database session state.
   199	        """
   200	        entity = await self._get_and_validate_token(plaintext_token)
   201	        return RefreshTokenInfo(
   202	            token_id=entity.id,
   203	            account_id=entity.account_id,
   204	            device_guid=entity.device_guid,
   205	            expires_at=entity.expires_at,
   206	            created_at=entity.created_at,
   207	            is_revoked=entity.is_revoked,
   208	        )
   209	
   210	    async def rotate_refresh_token(self, plaintext_token: str) -> RefreshRotationResult:
   211	        """
   212	        Perform transactional Refresh Token Rotation (RTR).
   213	        Validates the old token (with row locking), marks it revoked, issues a new token bound to the same device,
   214	        and commits both updates in a single atomic database transaction.
   215	        """
   216	        entity = await self._get_and_validate_token(plaintext_token, for_update=True)
   217	
   218	        new_plaintext = generate_refresh_token()
   219	        new_hash = hash_refresh_token(new_plaintext)
   220	        new_expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
   221	
   222	        try:
   223	            # Step 1: Insert new token entity bound to exact same device_guid within open transaction (commit=False)
   224	            new_entity = RefreshToken(
   225	                account_id=entity.account_id,
   226	                device_guid=entity.device_guid,  # Strict device binding preservation
   227	                token_hash=new_hash,
   228	                expires_at=new_expires_at,
   229	            )
   230	            await self.repo.create(new_entity, commit=False)
   231	
   232	            # Step 2: Revoke old token hash within open transaction (commit=False)
   233	            await self.repo.revoke(entity.token_hash, commit=False)
   234	
   235	            # Step 3: Commit both operations atomically in one transaction
   236	            await self.repo.session.commit()
   237	            await self.repo.session.refresh(new_entity)
   238	        except Exception as exc:
   239	            await self.repo.session.rollback()
   240	            if isinstance(exc, (ServiceError, RepositoryError)):
   241	                raise
   242	            raise RefreshTokenServiceError("Database error during atomic refresh token rotation") from exc
   243	
   244	        logger.info("Refresh token rotated")
   245	        return RefreshRotationResult(
   246	            new_token=new_plaintext,
   247	            expires_at=new_expires_at,
   248	            device_guid=entity.device_guid,
   249	            account_id=entity.account_id,
   250	        )
   251	
   252	    async def revoke_refresh_token(self, plaintext_token: str) -> bool:
   253	        """
   254	        Revoke a single refresh token by marking its database record as revoked.
   255	        Returns True if revoked, False if the token was not found or already revoked.
   256	        """
   257	        try:
   258	            token_hash = hash_refresh_token(plaintext_token)
   259	        except (TypeError, ValueError):
   260	            return False
   261	
   262	        try:
   263	            revoked = await self.repo.revoke(token_hash)
   264	        except RepositoryError as exc:
   265	            raise RefreshTokenServiceError("Database error revoking refresh token") from exc
   266	
   267	        if revoked:
   268	            logger.info("Refresh token revoked")
   269	        return revoked
   270	
   271	    async def revoke_all_for_account(self, account_id: uuid.UUID) -> int:
   272	        """
   273	        Revoke all active refresh tokens for an account.
   274	        Returns the count of newly revoked sessions.
   275	        """
   276	        try:
   277	            count = await self.repo.revoke_all_for_account(account_id)
   278	        except RepositoryError as exc:
   279	            raise RefreshTokenServiceError("Database error revoking all sessions for account") from exc
   280	
   281	        if count > 0:
   282	            logger.info("All sessions revoked")
   283	        return count

```


## Assistant

<thinking>
I'm checking the implementation details of the token rotation mechanism—specifically whether the `for_update=True` lock in `rotate_refresh_token` actually executes a SELECT FOR UPDATE query, and verifying that the repository's create and revoke operations handle concurrent rotation requests correctly without allowing double refreshes. I should also examine the auth router to see how it's structured.
</thinking>

**Tool Call: Read file `billing-server\app\repositories\refresh_token_repository.py`**
Status: Completed

```OverREALITY/billing-server/app/repositories/refresh_token_repository.py
     1	"""
     2	refresh_token_repository.py — Persistence layer for RefreshToken entities.
     3	"""
     4	from __future__ import annotations
     5	
     6	import uuid
     7	from sqlalchemy import select, update
     8	from sqlalchemy.exc import SQLAlchemyError
     9	from sqlalchemy.ext.asyncio import AsyncSession
    10	
    11	from app.exceptions import DatabaseOperationError
    12	from app.models import RefreshToken
    13	from app.repositories.base import BaseRepository
    14	
    15	
    16	class RefreshTokenRepository(BaseRepository[RefreshToken]):
    17	    """
    18	    Repository for RefreshToken model queries and operations.
    19	    Supports secure Refresh Token Rotation (RTR) and bulk session revocation.
    20	    """
    21	
    22	    def __init__(self, session: AsyncSession) -> None:
    23	        super().__init__(RefreshToken, session)
    24	
    25	    async def get_by_hash(self, token_hash: str, *, for_update: bool = False) -> RefreshToken | None:
    26	        """Retrieve a refresh token by its SHA-256 digest. If for_update=True, acquires row-level exclusive lock."""
    27	        try:
    28	            stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    29	            if for_update:
    30	                stmt = stmt.with_for_update()
    31	            result = await self.session.execute(stmt)
    32	            return result.scalar_one_or_none()
    33	        except SQLAlchemyError as exc:
    34	            raise DatabaseOperationError(
    35	                "Database error querying RefreshToken by token_hash"
    36	            ) from exc
    37	
    38	    async def revoke(self, token_hash: str, *, commit: bool = True) -> bool:
    39	        """
    40	        Revoke a single refresh token by marking is_revoked = True.
    41	        Returns True if the token existed and was revoked, False if not found.
    42	        If commit=False, flushes the session without committing the transaction.
    43	        """
    44	        try:
    45	            stmt = (
    46	                update(RefreshToken)
    47	                .where(RefreshToken.token_hash == token_hash, RefreshToken.is_revoked == False)
    48	                .values(is_revoked=True)
    49	            )
    50	            result = await self.session.execute(stmt)
    51	            if commit:
    52	                await self.session.commit()
    53	            else:
    54	                await self.session.flush()
    55	            return result.rowcount > 0
    56	        except SQLAlchemyError as exc:
    57	            await self.session.rollback()
    58	            raise DatabaseOperationError(
    59	                "Database error revoking RefreshToken"
    60	            ) from exc
    61	
    62	    async def revoke_all_for_account(self, account_id: uuid.UUID, *, commit: bool = True) -> int:
    63	        """
    64	        Revoke all active refresh tokens for a given account.
    65	        Returns the number of sessions that were newly revoked.
    66	        If commit=False, flushes the session without committing the transaction.
    67	        """
    68	        try:
    69	            stmt = (
    70	                update(RefreshToken)
    71	                .where(RefreshToken.account_id == account_id, RefreshToken.is_revoked == False)
    72	                .values(is_revoked=True)
    73	            )
    74	            result = await self.session.execute(stmt)
    75	            if commit:
    76	                await self.session.commit()
    77	            else:
    78	                await self.session.flush()
    79	            return result.rowcount
    80	        except SQLAlchemyError as exc:
    81	            await self.session.rollback()
    82	            raise DatabaseOperationError(
    83	                "Database error revoking all refresh tokens for account"
    84	            ) from exc

```


**Tool Call: Read file `billing-server\app\routers\auth.py`**
Status: Completed

```OverREALITY/billing-server/app/routers/auth.py
     1	"""
     2	auth.py — Authentication & Refresh API Endpoints Router (Phase 1.3.5)
     3	
     4	Thin orchestration layer connecting HTTP requests to domain authentication and token rotation services.
     5	Strictly decoupled from business logic, credential hashing, and direct database queries.
     6	
     7	Endpoints:
     8	  - POST /api/auth/login
     9	  - POST /api/auth/refresh
    10	  - POST /api/auth/logout
    11	  - POST /api/auth/logout-all
    12	
    13	LOGGING INVARIANT:
    14	Never logs Account IDs, Master Tokens, Refresh Tokens, JWTs, Hashes, or Device GUIDs.
    15	Logs only generic outcome descriptions: "Login succeeded", "Login failed", "Refresh succeeded", "Refresh failed", "Logout", "Logout all".
    16	"""
    17	from __future__ import annotations
    18	
    19	import logging
    20	import uuid
    21	from fastapi import APIRouter, Depends, HTTPException, Request, status
    22	
    23	from app.dependencies import (
    24	    get_auth_service,
    25	    get_current_account,
    26	    get_jwt_service,
    27	    get_refresh_service,
    28	    get_signal_service,
    29	)
    30	from app.models.account import Account
    31	from app.models.connection_signal import ConnectionEventType
    32	from app.rate_limit import require_rate_limit
    33	from app.security import JWTService
    34	from app.services import AuthenticationService, RefreshTokenService, ConnectionSignalService
    35	from app.services.exceptions import (
    36	    RefreshTokenExpiredError,
    37	    RefreshTokenNotFoundError,
    38	    RefreshTokenReplayError,
    39	    RefreshTokenRevokedError,
    40	)
    41	from app.routers.auth_models import (
    42	    AccountMeResponse,
    43	    LoginRequest,
    44	    LoginResponse,
    45	    LogoutRequest,
    46	    RefreshRequest,
    47	    RefreshResponse,
    48	    SuccessResponse,
    49	)
    50	
    51	logger = logging.getLogger(__name__)
    52	router = APIRouter(prefix="/api/auth", tags=["Authentication"])
    53	
    54	
    55	async def safe_record_signal(
    56	    signal_service: ConnectionSignalService,
    57	    account_id: uuid.UUID | None,
    58	    event_type: ConnectionEventType,
    59	    success: bool,
    60	    device_guid: str | None = None,
    61	    http_request: Request | None = None,
    62	) -> None:
    63	    """Safely record a security signal without letting exceptions disrupt authentication."""
    64	    try:
    65	        source_ip = http_request.client.host if http_request and http_request.client else None
    66	        user_agent = http_request.headers.get("user-agent") if http_request else None
    67	        await signal_service.record_signal(
    68	            account_id=account_id,
    69	            event_type=event_type,
    70	            success=success,
    71	            device_guid=device_guid,
    72	            source_ip=source_ip,
    73	            user_agent=user_agent,
    74	        )
    75	    except Exception as exc:
    76	        logger.error("Failed to record connection signal: %s", exc)
    77	
    78	
    79	@router.post(
    80	    "/login",
    81	    summary="Authenticate credentials and issue session tokens",
    82	    response_model=LoginResponse,
    83	    status_code=status.HTTP_200_OK,
    84	    dependencies=[Depends(require_rate_limit("login"))],
    85	    responses={
    86	        400: {"description": "Validation error"},
    87	        401: {"description": "Authentication failed or account inactive"},
    88	        429: {"description": "Rate limit exceeded"},
    89	        500: {"description": "Unexpected service or database error"},
    90	    },
    91	)
    92	async def login(
    93	    request: LoginRequest,
    94	    http_request: Request,
    95	    auth_service: AuthenticationService = Depends(get_auth_service),
    96	    jwt_service: JWTService = Depends(get_jwt_service),
    97	    refresh_service: RefreshTokenService = Depends(get_refresh_service),
    98	    signal_service: ConnectionSignalService = Depends(get_signal_service),
    99	) -> LoginResponse:
   100	    """
   101	    Authenticate Account ID and Master Token credential pair.
   102	    On success, issues a short-lived Ed25519 Access JWT and a long-lived rotated Refresh Token.
   103	    """
   104	    result = await auth_service.authenticate(request.account_id, request.master_token)
   105	    if not result.success or result.account is None:
   106	        logger.info("Login failed")
   107	        await safe_record_signal(
   108	            signal_service,
   109	            account_id=result.account.id if result.account else None,
   110	            event_type=ConnectionEventType.LOGIN,
   111	            success=False,
   112	            device_guid=request.device_guid,
   113	            http_request=http_request,
   114	        )
   115	        raise HTTPException(
   116	            status_code=status.HTTP_401_UNAUTHORIZED,
   117	            detail="Authentication failed: invalid credentials or inactive account",
   118	        )
   119	
   120	    access_token = jwt_service.issue_access_token(
   121	        account_uuid=result.account.id,
   122	        account_id=result.account.account_id,
   123	        device_guid=request.device_guid,
   124	    )
   125	    refresh_result = await refresh_service.issue_refresh_token(
   126	        account_id=result.account.id,
   127	        device_guid=request.device_guid,
   128	    )
   129	
   130	    logger.info("Login succeeded")
   131	    await safe_record_signal(
   132	        signal_service,
   133	        account_id=result.account.id,
   134	        event_type=ConnectionEventType.LOGIN,
   135	        success=True,
   136	        device_guid=request.device_guid,
   137	        http_request=http_request,
   138	    )
   139	    return LoginResponse(
   140	        access_token=access_token,
   141	        refresh_token=refresh_result.token,
   142	    )
   143	
   144	
   145	@router.post(
   146	    "/refresh",
   147	    summary="Rotate refresh token and issue new access token",
   148	    response_model=RefreshResponse,
   149	    status_code=status.HTTP_200_OK,
   150	    dependencies=[Depends(require_rate_limit("refresh"))],
   151	    responses={
   152	        400: {"description": "Validation error"},
   153	        401: {"description": "Invalid, expired, or replayed refresh token"},
   154	        429: {"description": "Rate limit exceeded"},
   155	        500: {"description": "Unexpected service or database error"},
   156	    },
   157	)
   158	async def refresh(
   159	    request: RefreshRequest,
   160	    http_request: Request,
   161	    refresh_service: RefreshTokenService = Depends(get_refresh_service),
   162	    jwt_service: JWTService = Depends(get_jwt_service),
   163	    auth_service: AuthenticationService = Depends(get_auth_service),
   164	    signal_service: ConnectionSignalService = Depends(get_signal_service),
   165	) -> RefreshResponse:
   166	    """
   167	    Perform Refresh Token Rotation (RTR).
   168	    Validates old refresh token, revokes it, issues a new refresh token bound to the same device,
   169	    and returns a fresh short-lived Access JWT.
   170	    """
   171	    try:
   172	        rotated = await refresh_service.rotate_refresh_token(request.refresh_token)
   173	    except Exception as exc:
   174	        logger.info("Refresh failed")
   175	        await safe_record_signal(
   176	            signal_service,
   177	            account_id=getattr(exc, "account_id", None),
   178	            event_type=ConnectionEventType.REFRESH,
   179	            success=False,
   180	            device_guid=getattr(exc, "device_guid", None),
   181	            http_request=http_request,
   182	        )
   183	        raise
   184	
   185	    account = await auth_service.get_active_account_by_uuid(rotated.account_id)
   186	    access_token = jwt_service.issue_access_token(
   187	        account_uuid=account.id,
   188	        account_id=account.account_id,
   189	        device_guid=rotated.device_guid,
   190	    )
   191	
   192	    logger.info("Refresh succeeded")
   193	    await safe_record_signal(
   194	        signal_service,
   195	        account_id=rotated.account_id,
   196	        event_type=ConnectionEventType.REFRESH,
   197	        success=True,
   198	        device_guid=rotated.device_guid,
   199	        http_request=http_request,
   200	    )
   201	    return RefreshResponse(
   202	        access_token=access_token,
   203	        refresh_token=rotated.new_token,
   204	    )
   205	
   206	
   207	@router.post(
   208	    "/logout",
   209	    summary="Revoke a single refresh token session",
   210	    response_model=SuccessResponse,
   211	    status_code=status.HTTP_200_OK,
   212	    dependencies=[Depends(require_rate_limit("refresh"))],
   213	)
   214	async def logout(
   215	    request: LogoutRequest,
   216	    http_request: Request,
   217	    refresh_service: RefreshTokenService = Depends(get_refresh_service),
   218	    signal_service: ConnectionSignalService = Depends(get_signal_service),
   219	) -> SuccessResponse:
   220	    """
   221	    Revoke only the presented refresh token session.
   222	    Idempotent: returns success even if token was already revoked or unknown.
   223	    """
   224	    account_id = None
   225	    device_guid = None
   226	    try:
   227	        info = await refresh_service.verify_refresh_token(request.refresh_token)
   228	        account_id = info.account_id
   229	        device_guid = info.device_guid
   230	    except Exception:
   231	        pass
   232	
   233	    await refresh_service.revoke_refresh_token(request.refresh_token)
   234	    logger.info("Logout")
   235	    await safe_record_signal(
   236	        signal_service,
   237	        account_id=account_id,
   238	        event_type=ConnectionEventType.LOGOUT,
   239	        success=True,
   240	        device_guid=device_guid,
   241	        http_request=http_request,
   242	    )
   243	    return SuccessResponse(success=True)
   244	
   245	
   246	@router.post(
   247	    "/logout-all",
   248	    summary="Revoke all refresh token sessions for an account",
   249	    response_model=SuccessResponse,
   250	    status_code=status.HTTP_200_OK,
   251	    dependencies=[Depends(require_rate_limit("refresh"))],
   252	)
   253	async def logout_all(
   254	    request: LogoutRequest,
   255	    http_request: Request,
   256	    refresh_service: RefreshTokenService = Depends(get_refresh_service),
   257	    signal_service: ConnectionSignalService = Depends(get_signal_service),
   258	) -> SuccessResponse:
   259	    """
   260	    Determine account identity from presented refresh token and revoke every active session
   261	    across all registered devices for that account.
   262	    Idempotent: returns success even if token was already revoked or unknown.
   263	    """
   264	    account_id = None
   265	    device_guid = None
   266	    try:
   267	        info = await refresh_service.verify_refresh_token(request.refresh_token)
   268	        account_id = info.account_id
   269	        device_guid = info.device_guid
   270	        await refresh_service.revoke_all_for_account(info.account_id)
   271	    except (
   272	        RefreshTokenNotFoundError,
   273	        RefreshTokenExpiredError,
   274	        RefreshTokenRevokedError,
   275	        RefreshTokenReplayError,
   276	    ):
   277	        pass
   278	
   279	    logger.info("Logout all")
   280	    await safe_record_signal(
   281	        signal_service,
   282	        account_id=account_id,
   283	        event_type=ConnectionEventType.LOGOUT_ALL,
   284	        success=True,
   285	        device_guid=device_guid,
   286	        http_request=http_request,
   287	    )
   288	    return SuccessResponse(success=True)
   289	
   290	
   291	@router.get(
   292	    "/me",
   293	    summary="Retrieve non-sensitive profile information for the authenticated account",
   294	    response_model=AccountMeResponse,
   295	    status_code=status.HTTP_200_OK,
   296	    responses={
   297	        401: {"description": "Missing, invalid, expired, or unauthorized bearer token"},
   298	        500: {"description": "Unexpected service or database error"},
   299	    },
   300	)
   301	async def get_me(
   302	    current_account: Account = Depends(get_current_account),
   303	) -> AccountMeResponse:
   304	    """
   305	    Retrieve current authenticated account details.
   306	    Requires a valid Ed25519 Access JWT in the Authorization Bearer header.
   307	    Rejects access if the backing account is deleted, suspended, pending, or expired.
   308	    """
   309	    return AccountMeResponse(
   310	        account_id=current_account.account_id,
   311	        status=current_account.status,
   312	        subscription_expires_at=current_account.subscription_expires_at,
   313	    )
   314	

```


**Tool Call: Read file `billing-server\app\security\crypto.py`**
Status: Completed

```OverREALITY/billing-server/app/security/crypto.py
     1	"""
     2	Cryptographic Helpers
     3	
     4	Pure cryptographic functions for hashing secrets and performing constant-time comparisons.
     5	Strictly decoupled from frameworks, databases, and authentication state. Zero logging of secrets or hashes.
     6	"""
     7	
     8	import hashlib
     9	import hmac
    10	from typing import AnyStr
    11	
    12	
    13	def hash_master_token(token: str) -> str:
    14	    """
    15	    Hash a 256-bit Master Token using SHA-256, returning a 64-character hexadecimal digest.
    16	
    17	    CRYPTOGRAPHIC REASONING — WHY SHA-256 INSTEAD OF ARGON2ID:
    18	    1. Master Tokens are generated directly by the server using a cryptographically secure
    19	       pseudorandom number generator (CSPRNG via Python's `secrets` module).
    20	    2. They contain 256 bits of true entropy, making them fundamentally different from
    21	       human-chosen passwords.
    22	    3. Because of this high entropy (2^256 possible values), they are completely immune to
    23	       offline dictionary attacks, rainbow tables, and brute-force guessing.
    24	    4. Memory-hard Key Derivation Functions (KDFs) like Argon2id are specifically designed to
    25	       protect low-entropy human passwords by making verification computationally and memory expensive.
    26	    5. Using Argon2id for high-entropy machine tokens would only impose severe CPU and memory
    27	       cost on our backend server under high authentication load without improving cryptographic security.
    28	    Therefore, SHA-256 provides optimal speed, standard cryptographic collision resistance, and complete
    29	    protection for high-entropy machine secrets.
    30	    """
    31	    if not isinstance(token, str):
    32	        raise TypeError("Master token must be a string")
    33	    return hashlib.sha256(token.encode("utf-8")).hexdigest()
    34	
    35	
    36	def compare_secrets(val1: AnyStr, val2: AnyStr) -> bool:
    37	    """
    38	    Securely compare two secret strings or bytes in constant time.
    39	
    40	    CRYPTOGRAPHIC REASONING — WHY HMAC.COMPARE_DIGEST():
    41	    Standard equality operators (`==`) in Python terminate comparison early as soon as the first
    42	    mismatched byte is encountered. An attacker can exploit this short-circuiting behavior by
    43	    measuring microscopic differences in execution time (timing attacks) to guess characters of a
    44	    secret one byte at a time.
    45	    `hmac.compare_digest()` ensures the comparison takes a constant amount of time proportional only
    46	    to the length of the strings, completely preventing timing side-channel attacks.
    47	    """
    48	    if not isinstance(val1, (str, bytes)) or not isinstance(val2, (str, bytes)):
    49	        return False
    50	    return hmac.compare_digest(val1, val2)
    51	
    52	
    53	def verify_master_token(token: str, expected_hash: str) -> bool:
    54	    """
    55	    Verify a raw Master Token against an expected SHA-256 hexadecimal digest in constant time.
    56	
    57	    CRYPTOGRAPHIC REASONING:
    58	    Combining SHA-256 hashing (`hash_master_token`) and constant-time comparison (`compare_secrets`)
    59	    into a single verification utility prevents developers from accidentally using standard equality (`==`)
    60	    or skipping hashing during authentication workflows (e.g., in Phase 1.3.2 login endpoints).
    61	    """
    62	    if not isinstance(token, str) or not isinstance(expected_hash, str):
    63	        return False
    64	    try:
    65	        computed_hash = hash_master_token(token)
    66	    except (TypeError, ValueError):
    67	        return False
    68	    return compare_secrets(computed_hash, expected_hash)
    69	
    70	
    71	def hash_refresh_token(token: str) -> str:
    72	    """
    73	    Hash a 256-bit Refresh Token using SHA-256, returning a 64-character hexadecimal digest.
    74	
    75	    CRYPTOGRAPHIC REASONING — WHY SHA-256 IS SUFFICIENT FOR REFRESH TOKENS:
    76	    1. Like Master Tokens, Refresh Tokens are generated via CSPRNG (`secrets.token_hex`), providing 256 bits
    77	       of high-entropy server-generated secret data.
    78	    2. With 2^256 possible combinations, offline brute-force or dictionary attacks are mathematically infeasible.
    79	    3. Memory-hard algorithms like Argon2id are unnecessary and would cause CPU/RAM exhaustion under high concurrency.
    80	       SHA-256 provides optimal performance and complete cryptographic security for machine tokens.
    81	    """
    82	    if not isinstance(token, str):
    83	        raise TypeError("Refresh token must be a string")
    84	    return hashlib.sha256(token.encode("utf-8")).hexdigest()
    85	
    86	
    87	def verify_refresh_token_hash(token: str, expected_hash: str) -> bool:
    88	    """
    89	    Verify a raw Refresh Token against an expected SHA-256 hexadecimal digest in constant time.
    90	    """
    91	    if not isinstance(token, str) or not isinstance(expected_hash, str):
    92	        return False
    93	    try:
    94	        computed_hash = hash_refresh_token(token)
    95	    except (TypeError, ValueError):
    96	        return False
    97	    return compare_secrets(computed_hash, expected_hash)

```


## Assistant

<thinking>
I'm noticing a potential security issue in the login endpoint where `device_guid` is accepted directly from the client request without any validation that the device is actually registered to the account or even properly formatted. I should check the LoginRequest validation rules and trace through the device registration flow to understand whether devices need to be pre-registered before login, then look at the devices router and models to confirm the expected behavior.

Also, the access and refresh tokens are bound to the `device_guid` without checking if the device is registered to the account or if the account has hit its maximum device limit—this device binding and limit enforcement might be happening elsewhere in DeviceService or the credentials endpoint, so I need to verify that. The timing defense for account enumeration looks solid with the dummy hash technique, and the SHA-256 hashing should provide constant-time behavior regardless of input length.

I'm also wondering where the Master Token is initially issued to customers—likely during account creation or payment processing—so I need to check the billing service and account repository to understand that flow. And there's a business logic question about whether an attacker with a valid master token could bypass device limits by guessing another device_guid and creating additional sessions, which means I need to verify that device limit enforcement actually exists somewhere in the codebase.

I'll now read through the account models and repository, device service and router, rate limiting implementation, and payment-related code to trace the full authentication and device management flow.
</thinking>

**Tool Call: Read file `billing-server\app\models\account.py`**
Status: Completed

```OverREALITY/billing-server/app/models/account.py
     1	"""
     2	account.py — Account model representing user subscriptions and credentials.
     3	"""
     4	from __future__ import annotations
     5	
     6	import uuid
     7	from datetime import datetime
     8	from typing import TYPE_CHECKING
     9	from sqlalchemy import String, DateTime, Enum as SQLEnum, text
    10	from sqlalchemy.orm import Mapped, mapped_column, relationship
    11	from sqlalchemy.types import Uuid
    12	
    13	from app.database import Base
    14	from app.models.base import SubscriptionStatus, TimestampMixin
    15	
    16	if TYPE_CHECKING:
    17	    from app.models.device import Device
    18	    from app.models.refresh_token import RefreshToken
    19	    from app.models.subscription import Subscription
    20	
    21	
    22	class Account(Base, TimestampMixin):
    23	    """
    24	    Accounts table.
    25	    Stores subscription state, human-readable Account ID, and hashed Master Token.
    26	    Never stores plaintext credentials or VPN traffic logs.
    27	    """
    28	    __tablename__ = "accounts"
    29	
    30	    id: Mapped[uuid.UUID] = mapped_column(
    31	        Uuid(as_uuid=True),
    32	        primary_key=True,
    33	        default=uuid.uuid4,
    34	        server_default=text("gen_random_uuid()"),
    35	    )
    36	    account_id: Mapped[str] = mapped_column(
    37	        String(32), unique=True, index=True, nullable=False
    38	    )
    39	    master_token_hash: Mapped[str] = mapped_column(
    40	        String(64), unique=True, index=True, nullable=False
    41	    )
    42	    # Invariant: marzban_username is write-only from Server 1.
    43	    # Server 1 creates/updates it via the Marzban API and never trusts values coming
    44	    # back from Marzban to overwrite its own state.
    45	    marzban_username: Mapped[str | None] = mapped_column(
    46	        String(64), unique=True, index=True, nullable=True
    47	    )
    48	    plan_id: Mapped[str] = mapped_column(
    49	        String(32),
    50	        nullable=False,
    51	        index=True,
    52	        default="free",
    53	        server_default="free",
    54	    )
    55	    status: Mapped[SubscriptionStatus] = mapped_column(
    56	        SQLEnum(
    57	            SubscriptionStatus,
    58	            name="subscription_status",
    59	            create_constraint=True,
    60	            native_enum=True,
    61	        ),
    62	        default=SubscriptionStatus.PENDING,
    63	        nullable=False,
    64	        index=True,
    65	    )
    66	    subscription_expires_at: Mapped[datetime | None] = mapped_column(
    67	        DateTime(timezone=True), index=True, nullable=True
    68	    )
    69	
    70	    # Relationships
    71	    devices: Mapped[list[Device]] = relationship(
    72	        "Device",
    73	        back_populates="account",
    74	        cascade="all, delete-orphan",
    75	        passive_deletes=True,
    76	    )
    77	    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
    78	        "RefreshToken",
    79	        back_populates="account",
    80	        cascade="all, delete-orphan",
    81	        passive_deletes=True,
    82	    )
    83	    subscriptions: Mapped[list[Subscription]] = relationship(
    84	        "Subscription",
    85	        back_populates="account",
    86	        cascade="all, delete-orphan",
    87	        passive_deletes=True,
    88	    )
    89	
    90	    def __repr__(self) -> str:
    91	        # account_id is truncated to prevent it from appearing in full in debug logs via repr().
    92	        account_id_prefix = (self.account_id or "")[:7] + "…" if self.account_id else "N/A"
    93	        return f"<Account(id={self.id}, account_id={account_id_prefix}, status={self.status})>"

```


**Tool Call: Read file `billing-server\app\services\device.py`**
Status: Completed

```OverREALITY/billing-server/app/services/device.py
     1	"""
     2	device.py — Core domain service managing client device lifecycle and registration.
     3	Strictly independent of HTTP layer, FastAPI routers, JWT tokens, and middleware.
     4	"""
     5	from __future__ import annotations
     6	
     7	import logging
     8	import uuid
     9	from datetime import datetime, timezone
    10	
    11	from app.exceptions import (
    12	    DuplicateEntityError,
    13	    RepositoryError,
    14	)
    15	from app.models import Device
    16	from app.repositories import AccountRepository, DeviceRepository
    17	from app.services.exceptions import (
    18	    DeviceLimitExceededError,
    19	    DeviceNotFoundError,
    20	    DeviceOwnershipError,
    21	    DeviceServiceError,
    22	    InactiveDeviceError,
    23	)
    24	from app.services.subscription_plan import SubscriptionPlanService
    25	
    26	logger = logging.getLogger(__name__)
    27	
    28	
    29	class DeviceService:
    30	    """
    31	    Domain service responsible for the lifecycle of registered client devices.
    32	    Enforces device ownership invariants, status checks, and timestamp tracking.
    33	    """
    34	
    35	    def __init__(
    36	        self,
    37	        device_repository: DeviceRepository,
    38	        account_repository: AccountRepository,
    39	        plan_service: SubscriptionPlanService | None = None,
    40	    ) -> None:
    41	        self.device_repo = device_repository
    42	        self.account_repo = account_repository
    43	        self.plan_service = plan_service or SubscriptionPlanService()
    44	
    45	    def _validate_friendly_name(self, name: str | None) -> str | None:
    46	        """
    47	        Validate friendly name formatting.
    48	        Rejects empty strings, whitespace-only strings, and excessively long names (>100 chars).
    49	        """
    50	        if name is None:
    51	            return None
    52	        if not isinstance(name, str):
    53	            raise DeviceServiceError("Device friendly name must be a string")
    54	        name_clean = name.strip()
    55	        if not name_clean:
    56	            raise DeviceServiceError("Device friendly name cannot be empty or whitespace")
    57	        if len(name_clean) > 100:
    58	            raise DeviceServiceError("Device friendly name exceeds maximum length of 100 characters")
    59	        return name_clean
    60	
    61	    def _normalize_device_timestamps(self, device: Device) -> Device:
    62	        """
    63	        Defensively ensure UTC timezone normalization on device timestamps.
    64	        Guards against drivers or migrations leaving tzinfo=None.
    65	        """
    66	        if device.first_seen_at and device.first_seen_at.tzinfo is None:
    67	            device.first_seen_at = device.first_seen_at.replace(tzinfo=timezone.utc)
    68	        if device.last_seen_at and device.last_seen_at.tzinfo is None:
    69	            device.last_seen_at = device.last_seen_at.replace(tzinfo=timezone.utc)
    70	        return device
    71	
    72	    async def _get_and_verify_ownership(
    73	        self, account_id: uuid.UUID, device_guid: str, *, for_update: bool = False
    74	    ) -> Device:
    75	        """
    76	        Helper to fetch a device by GUID and verify ownership against account_id.
    77	        Raises DeviceNotFoundError if missing, DeviceOwnershipError if owned by someone else.
    78	        """
    79	        try:
    80	            device = await self.device_repo.get_by_guid(device_guid, for_update=for_update)
    81	        except RepositoryError as exc:
    82	            logger.error("Repository error while querying device by GUID")
    83	            raise DeviceServiceError("Database error during device lookup") from exc
    84	
    85	        if device is None:
    86	            raise DeviceNotFoundError("Device not found")
    87	
    88	        if device.account_id != account_id:
    89	            logger.warning("Ownership violation: account attempted access to device owned by another account")
    90	            raise DeviceOwnershipError("Device is registered to another account")
    91	
    92	        return self._normalize_device_timestamps(device)
    93	
    94	    async def register_device(
    95	        self,
    96	        account_id: uuid.UUID,
    97	        device_guid: str,
    98	        friendly_name: str | None = None,
    99	    ) -> Device:
   100	        """
   101	        Register a new device or update an existing device for the same account.
   102	
   103	        Invariants:
   104	        - A device GUID may belong to exactly one account. Never multiple.
   105	        - If device already belongs to same account: update last_seen_at (and friendly_name if supplied).
   106	        - If device belongs to different account: raise DeviceOwnershipError.
   107	        """
   108	        clean_name = self._validate_friendly_name(friendly_name)
   109	
   110	        try:
   111	            device = await self.device_repo.get_by_guid(device_guid, for_update=True)
   112	        except RepositoryError as exc:
   113	            logger.error("Repository error querying device in register_device")
   114	            raise DeviceServiceError("Database error checking device existence") from exc
   115	
   116	        now = datetime.now(timezone.utc)
   117	
   118	        if device is not None:
   119	            if device.account_id != account_id:
   120	                logger.warning("Ownership violation during device registration attempt")
   121	                raise DeviceOwnershipError("Device is registered to another account")
   122	
   123	            if not device.is_active:
   124	                logger.info("Attempted registration/update on deactivated device")
   125	                raise InactiveDeviceError("Device is deactivated")
   126	
   127	            device = self._normalize_device_timestamps(device)
   128	            device.last_seen_at = now
   129	            if clean_name is not None:
   130	                device.friendly_name = clean_name
   131	
   132	            try:
   133	                updated = await self.device_repo.update(device)
   134	                return self._normalize_device_timestamps(updated)
   135	            except RepositoryError as exc:
   136	                logger.error("Repository error updating existing device in register_device")
   137	                raise DeviceServiceError("Database error updating device registration") from exc
   138	
   139	        # Device does not exist; verify account exists before creating (with row lock to prevent TOCTOU races)
   140	        try:
   141	            account = await self.account_repo.get_by_id(account_id, for_update=True)
   142	        except RepositoryError as exc:
   143	            logger.error("Repository error querying account in register_device")
   144	            raise DeviceServiceError("Database error checking account existence") from exc
   145	
   146	        if account is None:
   147	            raise DeviceServiceError("Account not found")
   148	
   149	        # Evaluate subscription plan policy and check device limits (Phase 1.4.3).
   150	        # Note on Downgrade Policy:
   151	        # If an account already owns more active devices than the new plan allows:
   152	        # - Existing devices remain untouched in the database.
   153	        # - Existing active devices continue functioning normally (updating timestamps when they check in above).
   154	        # - New device registrations are rejected until the user deactivates/removes devices below the limit.
   155	        # - Never automatically delete devices or silently deactivate them.
   156	        try:
   157	            active_count = await self.device_repo.count_active_devices_for_account(account_id)
   158	        except RepositoryError as exc:
   159	            logger.error("Repository error counting active devices in register_device")
   160	            raise DeviceServiceError("Database error checking device limit") from exc
   161	
   162	        if self.plan_service.device_limit_reached(account, active_count):
   163	            logger.info("Device registration rejected due to subscription policy.")
   164	            max_devices = self.plan_service.get_max_devices(account)
   165	            raise DeviceLimitExceededError(active_count, max_devices, account.plan_id)
   166	
   167	        try:
   168	            new_device = await self.device_repo.create(
   169	                account_id=account_id,
   170	                device_guid=device_guid,
   171	                friendly_name=clean_name,
   172	                is_active=True,
   173	                first_seen_at=now,
   174	                last_seen_at=now,
   175	            )
   176	            return self._normalize_device_timestamps(new_device)
   177	        except DuplicateEntityError as exc:
   178	            # Race condition: another transaction created the device after our read
   179	            logger.warning("Concurrent device registration detected")
   180	            try:
   181	                existing = await self.device_repo.get_by_guid(device_guid, for_update=True)
   182	            except RepositoryError as lookup_exc:
   183	                raise DeviceServiceError("Database error recovering from registration race") from lookup_exc
   184	
   185	            if existing is not None:
   186	                if existing.account_id != account_id:
   187	                    raise DeviceOwnershipError("Device is registered to another account") from exc
   188	                existing = self._normalize_device_timestamps(existing)
   189	                existing.last_seen_at = now
   190	                if clean_name is not None:
   191	                    existing.friendly_name = clean_name
   192	                try:
   193	                    updated = await self.device_repo.update(existing)
   194	                    return self._normalize_device_timestamps(updated)
   195	                except RepositoryError as update_exc:
   196	                    raise DeviceServiceError("Database error updating device after race") from update_exc
   197	
   198	            raise DeviceServiceError("Failed to register device due to duplicate constraint") from exc
   199	        except RepositoryError as exc:
   200	            logger.error("Repository error creating device in register_device")
   201	            raise DeviceServiceError("Database error creating device") from exc
   202	
   203	    async def touch_device(self, account_id: uuid.UUID, device_guid: str) -> Device:
   204	        """
   205	        Update only last_seen_at timestamp for an active device. Nothing else.
   206	        Verifies ownership against account_id.
   207	        Raises DeviceNotFoundError if missing, InactiveDeviceError if deactivated.
   208	        """
   209	        device = await self._get_and_verify_ownership(account_id, device_guid, for_update=True)
   210	
   211	        if not device.is_active:
   212	            logger.info("Attempted touch on deactivated device")
   213	            raise InactiveDeviceError("Device is deactivated")
   214	
   215	        device.last_seen_at = datetime.now(timezone.utc)
   216	        try:
   217	            updated = await self.device_repo.update(device)
   218	            return self._normalize_device_timestamps(updated)
   219	        except RepositoryError as exc:
   220	            logger.error("Repository error updating device timestamp in touch_device")
   221	            raise DeviceServiceError("Database error updating device timestamp") from exc
   222	
   223	    async def rename_device(
   224	        self, account_id: uuid.UUID, device_guid: str, friendly_name: str
   225	    ) -> Device:
   226	        """
   227	        Rename friendly_name of a device.
   228	        Must verify ownership. Return updated entity.
   229	        Does NOT update last_seen_at.
   230	        """
   231	        clean_name = self._validate_friendly_name(friendly_name)
   232	        if clean_name is None:
   233	            raise DeviceServiceError("Device friendly name cannot be None")
   234	
   235	        device = await self._get_and_verify_ownership(account_id, device_guid, for_update=True)
   236	
   237	        if not device.is_active:
   238	            logger.info("Attempted rename on deactivated device")
   239	            raise InactiveDeviceError("Device is deactivated")
   240	
   241	        device.friendly_name = clean_name
   242	        try:
   243	            updated = await self.device_repo.update(device)
   244	            return self._normalize_device_timestamps(updated)
   245	        except RepositoryError as exc:
   246	            logger.error("Repository error renaming device")
   247	            raise DeviceServiceError("Database error renaming device") from exc
   248	
   249	    async def deactivate_device(
   250	        self, account_id: uuid.UUID, device_guid: str
   251	    ) -> Device:
   252	        """
   253	        Soft deactivate device. Do NOT delete. Set is_active=False.
   254	        Must verify ownership.
   255	        If already deactivated -> raise InactiveDeviceError.
   256	        """
   257	        device = await self._get_and_verify_ownership(account_id, device_guid, for_update=True)
   258	
   259	        if not device.is_active:
   260	            logger.info("Attempted deactivation on already deactivated device")
   261	            raise InactiveDeviceError("Device is already deactivated")
   262	
   263	        device.is_active = False
   264	        try:
   265	            updated = await self.device_repo.update(device)
   266	            return self._normalize_device_timestamps(updated)
   267	        except RepositoryError as exc:
   268	            logger.error("Repository error deactivating device")
   269	            raise DeviceServiceError("Database error deactivating device") from exc
   270	
   271	    async def reactivate_device(
   272	        self, account_id: uuid.UUID, device_guid: str
   273	    ) -> Device:
   274	        """
   275	        Reactivate a deactivated device.
   276	        Must verify ownership and enforce subscription plan device limit.
   277	        If already active -> raise InactiveDeviceError.
   278	        """
   279	        device = await self._get_and_verify_ownership(account_id, device_guid, for_update=True)
   280	
   281	        if device.is_active:
   282	            logger.info("Attempted reactivation on already active device")
   283	            raise InactiveDeviceError("Device is already active")
   284	
   285	        try:
   286	            account = await self.account_repo.get_by_id(account_id, for_update=True)
   287	            if account is None:
   288	                raise DeviceServiceError("Account not found")
   289	            active_count = await self.device_repo.count_active_devices_for_account(account_id)
   290	        except RepositoryError as exc:
   291	            logger.error("Repository error checking active devices in reactivate_device")
   292	            raise DeviceServiceError("Database error checking device limit") from exc
   293	
   294	        if self.plan_service.device_limit_reached(account, active_count):
   295	            logger.info("Device reactivation rejected due to subscription policy.")
   296	            max_devices = self.plan_service.get_max_devices(account)
   297	            raise DeviceLimitExceededError(active_count, max_devices, account.plan_id)
   298	
   299	        device.is_active = True
   300	        try:
   301	            updated = await self.device_repo.update(device)
   302	            return self._normalize_device_timestamps(updated)
   303	        except RepositoryError as exc:
   304	            logger.error("Repository error reactivating device")
   305	            raise DeviceServiceError("Database error reactivating device") from exc
   306	
   307	    async def get_device(
   308	        self, account_id: uuid.UUID, device_guid: str
   309	    ) -> Device:
   310	        """
   311	        Retrieve a device by GUID.
   312	        Must verify ownership.
   313	        """
   314	        return await self._get_and_verify_ownership(account_id, device_guid)
   315	
   316	    async def get_devices_for_account(
   317	        self, account_id: uuid.UUID
   318	    ) -> list[Device]:
   319	        """
   320	        List all devices registered to an account, ordered by most recently seen first.
   321	        Raises DeviceServiceError if the account does not exist.
   322	        """
   323	        try:
   324	            account = await self.account_repo.get_by_id(account_id)
   325	        except RepositoryError as exc:
   326	            logger.error("Repository error checking account in get_devices_for_account")
   327	            raise DeviceServiceError("Database error checking account existence") from exc
   328	
   329	        if account is None:
   330	            raise DeviceServiceError("Account not found")
   331	
   332	        try:
   333	            devices = await self.device_repo.get_devices_for_account(account_id)
   334	            return [self._normalize_device_timestamps(d) for d in devices]
   335	        except RepositoryError as exc:
   336	            logger.error("Repository error querying devices for account")
   337	            raise DeviceServiceError("Database error querying devices for account") from exc

```


**Tool Call: Read file `billing-server\app\routers\devices.py`**
Status: Completed

```OverREALITY/billing-server/app/routers/devices.py
     1	"""
     2	devices.py — Device Management API Endpoints Router (Phase 1.4.2).
     3	
     4	Thin orchestration layer connecting HTTP requests to domain DeviceService.
     5	Strictly decoupled from business logic, validation logic, and direct database queries.
     6	
     7	Endpoints:
     8	  - GET    /api/devices
     9	  - GET    /api/devices/{device_guid}
    10	  - PATCH  /api/devices/{device_guid}
    11	  - DELETE /api/devices/{device_guid}
    12	  - POST   /api/devices/{device_guid}/reactivate
    13	
    14	LOGGING INVARIANT:
    15	Never logs Account IDs, database UUIDs, or Device GUIDs.
    16	Logs only generic outcome descriptions: "List devices succeeded", "Get device succeeded",
    17	"Rename device succeeded", "Deactivate device succeeded", "Reactivate device succeeded".
    18	"""
    19	from __future__ import annotations
    20	
    21	import logging
    22	import uuid
    23	from fastapi import APIRouter, Depends, Request, status
    24	
    25	from app.dependencies import get_current_account, get_device_service, get_signal_service
    26	from app.models.account import Account
    27	from app.models.connection_signal import ConnectionEventType
    28	from app.rate_limit import require_rate_limit
    29	from app.services import DeviceService, ConnectionSignalService
    30	from app.services.exceptions import InactiveDeviceError
    31	from app.routers.device_models import (
    32	    DeviceListResponse,
    33	    DeviceResponse,
    34	    RegisterDeviceRequest,
    35	    RenameDeviceRequest,
    36	    SuccessResponse,
    37	)
    38	
    39	logger = logging.getLogger(__name__)
    40	router = APIRouter(prefix="/api/devices", tags=["Devices"])
    41	
    42	
    43	async def safe_record_signal(
    44	    signal_service: ConnectionSignalService,
    45	    account_id: uuid.UUID | None,
    46	    event_type: ConnectionEventType,
    47	    success: bool,
    48	    device_guid: str | None = None,
    49	    http_request: Request | None = None,
    50	) -> None:
    51	    """Safely record a security signal without letting exceptions disrupt device management."""
    52	    try:
    53	        source_ip = http_request.client.host if http_request and http_request.client else None
    54	        user_agent = http_request.headers.get("user-agent") if http_request else None
    55	        await signal_service.record_signal(
    56	            account_id=account_id,
    57	            event_type=event_type,
    58	            success=success,
    59	            device_guid=device_guid,
    60	            source_ip=source_ip,
    61	            user_agent=user_agent,
    62	        )
    63	    except Exception as exc:
    64	        logger.error("Failed to record connection signal: %s", exc)
    65	
    66	
    67	@router.post(
    68	    "",
    69	    summary="Register a client device under the authenticated account",
    70	    response_model=DeviceResponse,
    71	    status_code=status.HTTP_200_OK,
    72	    dependencies=[Depends(require_rate_limit("device_register"))],
    73	    responses={
    74	        400: {"description": "Validation error"},
    75	        401: {"description": "Authentication failed or token invalid"},
    76	        403: {"description": "Device limit reached for subscription plan"},
    77	        429: {"description": "Rate limit exceeded"},
    78	        500: {"description": "Unexpected service or database error"},
    79	    },
    80	)
    81	async def register_device(
    82	    request: RegisterDeviceRequest,
    83	    http_request: Request,
    84	    current_account: Account = Depends(get_current_account),
    85	    device_service: DeviceService = Depends(get_device_service),
    86	    signal_service: ConnectionSignalService = Depends(get_signal_service),
    87	) -> DeviceResponse:
    88	    """Register a client device or update its timestamps if already registered."""
    89	    try:
    90	        device = await device_service.register_device(
    91	            current_account.id,
    92	            request.device_guid,
    93	            request.friendly_name,
    94	        )
    95	    except Exception:
    96	        logger.info("Register device failed")
    97	        await safe_record_signal(
    98	            signal_service,
    99	            account_id=current_account.id,
   100	            event_type=ConnectionEventType.DEVICE_REGISTER,
   101	            success=False,
   102	            device_guid=request.device_guid,
   103	            http_request=http_request,
   104	        )
   105	        raise
   106	
   107	    logger.info("Register device succeeded")
   108	    await safe_record_signal(
   109	        signal_service,
   110	        account_id=current_account.id,
   111	        event_type=ConnectionEventType.DEVICE_REGISTER,
   112	        success=True,
   113	        device_guid=request.device_guid,
   114	        http_request=http_request,
   115	    )
   116	    return DeviceResponse.model_validate(device)
   117	
   118	
   119	@router.get(
   120	    "",
   121	    summary="List all registered client devices for current account",
   122	    response_model=DeviceListResponse,
   123	    status_code=status.HTTP_200_OK,
   124	    responses={
   125	        401: {"description": "Authentication failed or token invalid"},
   126	        500: {"description": "Unexpected service or database error"},
   127	    },
   128	)
   129	async def list_devices(
   130	    current_account: Account = Depends(get_current_account),
   131	    device_service: DeviceService = Depends(get_device_service),
   132	) -> DeviceListResponse:
   133	    """Return all client devices owned by the authenticated account."""
   134	    devices = await device_service.get_devices_for_account(current_account.id)
   135	    logger.info("List devices succeeded")
   136	    return DeviceListResponse(
   137	        devices=[DeviceResponse.model_validate(d) for d in devices]
   138	    )
   139	
   140	
   141	@router.get(
   142	    "/{device_guid}",
   143	    summary="Retrieve details for a specific registered device",
   144	    response_model=DeviceResponse,
   145	    status_code=status.HTTP_200_OK,
   146	    responses={
   147	        401: {"description": "Authentication failed or token invalid"},
   148	        404: {"description": "Device not found or owned by another account"},
   149	        500: {"description": "Unexpected service or database error"},
   150	    },
   151	)
   152	async def get_device(
   153	    device_guid: str,
   154	    current_account: Account = Depends(get_current_account),
   155	    device_service: DeviceService = Depends(get_device_service),
   156	) -> DeviceResponse:
   157	    """Retrieve exactly one device. Returns 404 if device is missing or belongs to another account."""
   158	    device = await device_service.get_device(current_account.id, device_guid)
   159	    logger.info("Get device succeeded")
   160	    return DeviceResponse.model_validate(device)
   161	
   162	
   163	@router.patch(
   164	    "/{device_guid}",
   165	    summary="Update friendly name for a specific registered device",
   166	    response_model=DeviceResponse,
   167	    status_code=status.HTTP_200_OK,
   168	    responses={
   169	        400: {"description": "Validation error or device inactive"},
   170	        401: {"description": "Authentication failed or token invalid"},
   171	        404: {"description": "Device not found or owned by another account"},
   172	        500: {"description": "Unexpected service or database error"},
   173	    },
   174	)
   175	async def rename_device(
   176	    device_guid: str,
   177	    request: RenameDeviceRequest,
   178	    http_request: Request,
   179	    current_account: Account = Depends(get_current_account),
   180	    device_service: DeviceService = Depends(get_device_service),
   181	    signal_service: ConnectionSignalService = Depends(get_signal_service),
   182	) -> DeviceResponse:
   183	    """Update friendly name of an active device. Rejects updates if device is inactive."""
   184	    try:
   185	        device = await device_service.rename_device(
   186	            current_account.id, device_guid, request.friendly_name
   187	        )
   188	    except Exception:
   189	        logger.info("Rename device failed")
   190	        await safe_record_signal(
   191	            signal_service,
   192	            account_id=current_account.id,
   193	            event_type=ConnectionEventType.DEVICE_RENAME,
   194	            success=False,
   195	            device_guid=device_guid,
   196	            http_request=http_request,
   197	        )
   198	        raise
   199	
   200	    logger.info("Rename device succeeded")
   201	    await safe_record_signal(
   202	        signal_service,
   203	        account_id=current_account.id,
   204	        event_type=ConnectionEventType.DEVICE_RENAME,
   205	        success=True,
   206	        device_guid=device_guid,
   207	        http_request=http_request,
   208	    )
   209	    return DeviceResponse.model_validate(device)
   210	
   211	
   212	@router.delete(
   213	    "/{device_guid}",
   214	    summary="Soft-deactivate a registered client device",
   215	    response_model=SuccessResponse,
   216	    status_code=status.HTTP_200_OK,
   217	    responses={
   218	        401: {"description": "Authentication failed or token invalid"},
   219	        404: {"description": "Device not found or owned by another account"},
   220	        500: {"description": "Unexpected service or database error"},
   221	    },
   222	)
   223	async def deactivate_device(
   224	    device_guid: str,
   225	    http_request: Request,
   226	    current_account: Account = Depends(get_current_account),
   227	    device_service: DeviceService = Depends(get_device_service),
   228	    signal_service: ConnectionSignalService = Depends(get_signal_service),
   229	) -> SuccessResponse:
   230	    """Soft-delete a device by setting is_active to False. Operation is idempotent."""
   231	    try:
   232	        await device_service.deactivate_device(current_account.id, device_guid)
   233	    except InactiveDeviceError:
   234	        logger.info("Deactivate device succeeded (already inactive)")
   235	        await safe_record_signal(
   236	            signal_service,
   237	            account_id=current_account.id,
   238	            event_type=ConnectionEventType.DEVICE_DEACTIVATE,
   239	            success=True,
   240	            device_guid=device_guid,
   241	            http_request=http_request,
   242	        )
   243	        return SuccessResponse(success=True, message="Device deactivated successfully")
   244	    except Exception:
   245	        logger.info("Deactivate device failed")
   246	        await safe_record_signal(
   247	            signal_service,
   248	            account_id=current_account.id,
   249	            event_type=ConnectionEventType.DEVICE_DEACTIVATE,
   250	            success=False,
   251	            device_guid=device_guid,
   252	            http_request=http_request,
   253	        )
   254	        raise
   255	
   256	    logger.info("Deactivate device succeeded")
   257	    await safe_record_signal(
   258	        signal_service,
   259	        account_id=current_account.id,
   260	        event_type=ConnectionEventType.DEVICE_DEACTIVATE,
   261	        success=True,
   262	        device_guid=device_guid,
   263	        http_request=http_request,
   264	    )
   265	    return SuccessResponse(success=True, message="Device deactivated successfully")
   266	
   267	
   268	@router.post(
   269	    "/{device_guid}/reactivate",
   270	    summary="Reactivate a soft-deactivated client device",
   271	    response_model=DeviceResponse,
   272	    status_code=status.HTTP_200_OK,
   273	    responses={
   274	        400: {"description": "Validation error or device already active"},
   275	        401: {"description": "Authentication failed or token invalid"},
   276	        404: {"description": "Device not found or owned by another account"},
   277	        500: {"description": "Unexpected service or database error"},
   278	    },
   279	)
   280	async def reactivate_device(
   281	    device_guid: str,
   282	    http_request: Request,
   283	    current_account: Account = Depends(get_current_account),
   284	    device_service: DeviceService = Depends(get_device_service),
   285	    signal_service: ConnectionSignalService = Depends(get_signal_service),
   286	) -> DeviceResponse:
   287	    """Reactivate a previously deactivated device."""
   288	    try:
   289	        device = await device_service.reactivate_device(current_account.id, device_guid)
   290	    except InactiveDeviceError:
   291	        logger.info("Reactivate device succeeded (already active)")
   292	        device = await device_service.get_device(current_account.id, device_guid)
   293	        await safe_record_signal(
   294	            signal_service,
   295	            account_id=current_account.id,
   296	            event_type=ConnectionEventType.DEVICE_REACTIVATE,
   297	            success=True,
   298	            device_guid=device_guid,
   299	            http_request=http_request,
   300	        )
   301	        return DeviceResponse.model_validate(device)
   302	    except Exception:
   303	        logger.info("Reactivate device failed")
   304	        await safe_record_signal(
   305	            signal_service,
   306	            account_id=current_account.id,
   307	            event_type=ConnectionEventType.DEVICE_REACTIVATE,
   308	            success=False,
   309	            device_guid=device_guid,
   310	            http_request=http_request,
   311	        )
   312	        raise
   313	
   314	    logger.info("Reactivate device succeeded")
   315	    await safe_record_signal(
   316	        signal_service,
   317	        account_id=current_account.id,
   318	        event_type=ConnectionEventType.DEVICE_REACTIVATE,
   319	        success=True,
   320	        device_guid=device_guid,
   321	        http_request=http_request,
   322	    )
   323	    return DeviceResponse.model_validate(device)

```


**Tool Call: Read file `billing-server\app\routers\auth_models.py`**
Status: Completed

```OverREALITY/billing-server/app/routers/auth_models.py
     1	"""
     2	auth_models.py — Transport DTOs for Authentication & Refresh API Endpoints.
     3	
     4	Strictly isolates HTTP request/response models from internal database entities and domain models.
     5	Enforces clean OpenAPI documentation without exposing internal dataclasses or credentials.
     6	"""
     7	from __future__ import annotations
     8	
     9	from datetime import datetime
    10	from pydantic import BaseModel, Field
    11	
    12	from app.models import SubscriptionStatus
    13	from app.security import ACCESS_TOKEN_EXPIRE_MINUTES
    14	
    15	
    16	class LoginRequest(BaseModel):
    17	    """Payload for POST /api/auth/login."""
    18	    account_id: str = Field(..., description="Human-readable Account ID (e.g., RT-XXXX-XXXX)")
    19	    master_token: str = Field(
    20	        ...,
    21	        description="64-character hexadecimal Master Token",
    22	        json_schema_extra={"writeOnly": True},
    23	    )
    24	    device_guid: str = Field(..., description="Unique hardware or installation identifier")
    25	
    26	
    27	class RefreshRequest(BaseModel):
    28	    """Payload for POST /api/auth/refresh."""
    29	    refresh_token: str = Field(..., description="Active 64-character hexadecimal refresh token")
    30	
    31	
    32	class LogoutRequest(BaseModel):
    33	    """Payload for POST /api/auth/logout and POST /api/auth/logout-all."""
    34	    refresh_token: str = Field(..., description="Refresh token identifying the session or account to revoke")
    35	
    36	
    37	class LoginResponse(BaseModel):
    38	    """Successful authentication token pair response."""
    39	    access_token: str = Field(..., description="Short-lived Ed25519 signed Access JWT")
    40	    refresh_token: str = Field(..., description="Long-lived 256-bit CSPRNG refresh token")
    41	    token_type: str = Field(default="Bearer", description="HTTP authorization scheme")
    42	    expires_in: int = Field(
    43	        default=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    44	        description="Access token validity duration in seconds",
    45	    )
    46	
    47	
    48	class RefreshResponse(BaseModel):
    49	    """Successful refresh token rotation response."""
    50	    access_token: str = Field(..., description="New short-lived Ed25519 signed Access JWT")
    51	    refresh_token: str = Field(..., description="New rotated long-lived refresh token")
    52	    token_type: str = Field(default="Bearer", description="HTTP authorization scheme")
    53	    expires_in: int = Field(
    54	        default=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    55	        description="Access token validity duration in seconds",
    56	    )
    57	
    58	
    59	class SuccessResponse(BaseModel):
    60	    """Generic success confirmation for logout operations."""
    61	    success: bool = Field(default=True, description="Indicates operation completed successfully")
    62	
    63	
    64	class AccountMeResponse(BaseModel):
    65	    """
    66	    Response model for GET /api/auth/me returning non-sensitive account identity.
    67	    Strictly omits credentials, tokens, hashes, database UUIDs, and internal metadata.
    68	    """
    69	    account_id: str = Field(..., description="Human-readable Account ID (e.g., RT-XXXX-XXXX)")
    70	    status: SubscriptionStatus = Field(..., description="Current subscription lifecycle status")
    71	    subscription_expires_at: datetime | None = Field(
    72	        None, description="Subscription expiration timestamp (UTC)"
    73	    )
    74	

```


## Assistant

<thinking>
I'm spotting a critical vulnerability in the login flow: the `device_guid` parameter is accepted directly from the client and used to bind refresh tokens without any validation against the device registry or account ownership. This means a user with a valid master token can create unlimited sessions tied to arbitrary device identifiers, completely bypassing device limit enforcement.

The device limit is only enforced in the separate `register_device` endpoint, so if a client skips that and just calls login repeatedly with different device_guids, they can accumulate unlimited authenticated sessions and VPN credentials. The real question is whether credential issuance actually validates the device_guid against registered devices or if it just trusts whatever's embedded in the JWT — if it's the latter, the entire device binding mechanism is just cosmetic. I need to check the credential service to see if it enforces device limits before issuing VPN credentials.
</thinking>

**Tool Call: Read file `billing-server\app\routers\credentials.py`**
Status: Completed

```OverREALITY/billing-server/app/routers/credentials.py
     1	"""
     2	credentials.py — Phase 2.4 VPN Credential Lifecycle & Client Configuration Delivery API Router.
     3	Provides authenticated endpoints for retrieving and managing VPN client configurations and credentials.
     4	Enforces zero-secret logging and consumes CredentialService exclusively.
     5	"""
     6	from __future__ import annotations
     7	
     8	import logging
     9	from fastapi import APIRouter, Depends, HTTPException, status
    10	
    11	from app.dependencies import get_current_account, get_credential_service
    12	from app.models import Account
    13	from app.routers.credential_models import (
    14	    CredentialResponse,
    15	    VlessResponse,
    16	    SingboxResponse,
    17	    CredentialStatusResponse,
    18	)
    19	from app.services.credential_service import CredentialService
    20	from app.services.exceptions import (
    21	    CredentialNotFoundError,
    22	    CredentialAlreadyRevokedError,
    23	    CredentialAlreadyActiveError,
    24	    CredentialRotationFailedError,
    25	    CredentialServiceError,
    26	)
    27	
    28	logger = logging.getLogger(__name__)
    29	
    30	router = APIRouter(
    31	    prefix="/api/credentials",
    32	    tags=["VPN Credentials"],
    33	    responses={
    34	        401: {"description": "Authentication required or token invalid"},
    35	        404: {"description": "VPN profile not found"},
    36	        500: {"description": "Internal server error"},
    37	    },
    38	)
    39	
    40	
    41	@router.get(
    42	    "",
    43	    response_model=CredentialResponse,
    44	    status_code=status.HTTP_200_OK,
    45	    summary="Get active VPN profile and configuration",
    46	    description="Returns canonical VPN connection parameters and generated sing-box configuration.",
    47	)
    48	async def get_credentials(
    49	    account: Account = Depends(get_current_account),
    50	    service: CredentialService = Depends(get_credential_service),
    51	) -> CredentialResponse:
    52	    """Retrieve complete active VPN profile and configuration blob."""
    53	    try:
    54	        logger.info("Retrieving VPN credentials for account_id=%s", account.id)
    55	        data = await service.get_credentials(account.id)
    56	        return CredentialResponse(**data)
    57	    except CredentialNotFoundError as exc:
    58	        logger.info("Credentials not found for account_id=%s", account.id)
    59	        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    60	    except CredentialAlreadyRevokedError as exc:
    61	        logger.info("Credentials already revoked for account_id=%s", account.id)
    62	        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    63	    except CredentialServiceError as exc:
    64	        logger.error("Error retrieving credentials for account_id=%s", account.id)
    65	        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    66	
    67	
    68	@router.get(
    69	    "/vless",
    70	    response_model=VlessResponse,
    71	    status_code=status.HTTP_200_OK,
    72	    summary="Get canonical VLESS URI",
    73	    description="Returns the canonical VLESS reality link for client import.",
    74	)
    75	async def get_vless_uri(
    76	    account: Account = Depends(get_current_account),
    77	    service: CredentialService = Depends(get_credential_service),
    78	) -> VlessResponse:
    79	    """Retrieve VLESS URI string for the active VPN profile."""
    80	    try:
    81	        logger.info("Retrieving VLESS URI for account_id=%s", account.id)
    82	        uri = await service.get_vless_uri(account.id)
    83	        return VlessResponse(vless_uri=uri)
    84	    except CredentialNotFoundError as exc:
    85	        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    86	    except CredentialAlreadyRevokedError as exc:
    87	        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    88	    except CredentialServiceError as exc:
    89	        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    90	
    91	
    92	@router.get(
    93	    "/sing-box",
    94	    response_model=SingboxResponse,
    95	    status_code=status.HTTP_200_OK,
    96	    summary="Get sing-box JSON configuration",
    97	    description="Returns dynamic sing-box 1.8+ outbound JSON configuration.",
    98	)
    99	async def get_singbox_config(
   100	    account: Account = Depends(get_current_account),
   101	    service: CredentialService = Depends(get_credential_service),
   102	) -> SingboxResponse:
   103	    """Retrieve generated sing-box configuration dictionary."""
   104	    try:
   105	        logger.info("Retrieving sing-box config for account_id=%s", account.id)
   106	        config = await service.get_singbox_config(account.id)
   107	        return SingboxResponse(config=config)
   108	    except CredentialNotFoundError as exc:
   109	        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
   110	    except CredentialAlreadyRevokedError as exc:
   111	        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
   112	    except CredentialServiceError as exc:
   113	        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
   114	
   115	
   116	@router.post(
   117	    "/regenerate",
   118	    response_model=CredentialResponse,
   119	    status_code=status.HTTP_200_OK,
   120	    summary="Regenerate/rotate VPN credentials",
   121	    description="Atomically rotates UUID and REALITY parameters in the remote provisioning provider.",
   122	)
   123	async def regenerate_credentials(
   124	    account: Account = Depends(get_current_account),
   125	    service: CredentialService = Depends(get_credential_service),
   126	) -> CredentialResponse:
   127	    """Rotate and regenerate VPN credentials for the authenticated account."""
   128	    try:
   129	        logger.info("Regenerating credentials for account_id=%s", account.id)
   130	        data = await service.regenerate_credentials(account.id)
   131	        return CredentialResponse(**data)
   132	    except CredentialNotFoundError as exc:
   133	        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
   134	    except CredentialRotationFailedError as exc:
   135	        logger.error("Credential rotation failed for account_id=%s", account.id)
   136	        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
   137	    except CredentialServiceError as exc:
   138	        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
   139	
   140	
   141	@router.post(
   142	    "/revoke",
   143	    response_model=CredentialStatusResponse,
   144	    status_code=status.HTTP_200_OK,
   145	    summary="Revoke VPN credentials",
   146	    description="Suspends VPN access for the active profile without deleting historical records.",
   147	)
   148	async def revoke_credentials(
   149	    account: Account = Depends(get_current_account),
   150	    service: CredentialService = Depends(get_credential_service),
   151	) -> CredentialStatusResponse:
   152	    """Revoke active credentials for the authenticated account."""
   153	    try:
   154	        logger.info("Revoking credentials for account_id=%s", account.id)
   155	        await service.revoke_credentials(account.id)
   156	        return CredentialStatusResponse(status="revoked")
   157	    except CredentialNotFoundError as exc:
   158	        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
   159	    except CredentialAlreadyRevokedError as exc:
   160	        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
   161	    except CredentialServiceError as exc:
   162	        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
   163	
   164	
   165	@router.post(
   166	    "/restore",
   167	    response_model=CredentialStatusResponse,
   168	    status_code=status.HTTP_200_OK,
   169	    summary="Restore revoked VPN credentials",
   170	    description="Reactivates previously revoked or suspended VPN credentials.",
   171	)
   172	async def restore_credentials(
   173	    account: Account = Depends(get_current_account),
   174	    service: CredentialService = Depends(get_credential_service),
   175	) -> CredentialStatusResponse:
   176	    """Restore previously revoked credentials for the authenticated account."""
   177	    try:
   178	        logger.info("Restoring credentials for account_id=%s", account.id)
   179	        await service.restore_credentials(account.id)
   180	        return CredentialStatusResponse(status="restored")
   181	    except CredentialNotFoundError as exc:
   182	        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
   183	    except CredentialAlreadyActiveError as exc:
   184	        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
   185	    except CredentialServiceError as exc:
   186	        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

```


**Tool Call: Read file `billing-server\app\services\subscription_plan.py`**
Status: Completed

```OverREALITY/billing-server/app/services/subscription_plan.py
     1	"""
     2	subscription_plan.py — Domain service for resolving subscription plans and checking limits (Phase 1.4.3).
     3	"""
     4	from __future__ import annotations
     5	
     6	import logging
     7	from typing import TYPE_CHECKING
     8	
     9	from app.models.subscription_plan import PLANS_REGISTRY, SubscriptionPlan
    10	from app.services.exceptions import UnknownPlanError
    11	
    12	if TYPE_CHECKING:
    13	    from app.models.account import Account
    14	
    15	logger = logging.getLogger(__name__)
    16	
    17	
    18	class SubscriptionPlanService:
    19	    """
    20	    Pure domain service responsible for policy lookup and limit evaluation.
    21	    Does not interact with FastAPI or HTTP layers.
    22	    """
    23	
    24	    def get_plan(self, plan_id: str) -> SubscriptionPlan:
    25	        """
    26	        Resolve a SubscriptionPlan by its plan_id.
    27	        Rejects unknown plan IDs by raising UnknownPlanError.
    28	        """
    29	        if not plan_id:
    30	            raise UnknownPlanError("Plan ID cannot be empty.")
    31	
    32	        clean_id = plan_id.strip().lower()
    33	        plan = PLANS_REGISTRY.get(clean_id)
    34	        if not plan:
    35	            logger.warning("Attempted to resolve unknown subscription plan ID: %s", clean_id)
    36	            raise UnknownPlanError(f"Unknown subscription plan ID: '{clean_id}'")
    37	        return plan
    38	
    39	    def list_plans(self) -> list[SubscriptionPlan]:
    40	        """Return all registered subscription plans."""
    41	        return list(PLANS_REGISTRY.values())
    42	
    43	
    44	    def get_max_devices(self, account: Account) -> int:
    45	        """Return the maximum allowed registered devices for the given account's plan."""
    46	        plan = self.get_plan(account.plan_id)
    47	        return plan.max_devices
    48	
    49	    def get_max_concurrent_ips(self, account: Account) -> int:
    50	        """
    51	        Return the configured max_concurrent_ips for the given account's plan.
    52	        NOTE: This value is stored only in Billing/Auth. Concurrent IP enforcement belongs
    53	        to the VPN layer (Marzban + V2IpLimit/luIP).
    54	        """
    55	        plan = self.get_plan(account.plan_id)
    56	        return plan.max_concurrent_ips
    57	
    58	    def device_limit_reached(self, account: Account, current_count: int) -> bool:
    59	        """
    60	        Check if the account has reached or exceeded its device registration limit.
    61	        """
    62	        max_devices = self.get_max_devices(account)
    63	        return current_count >= max_devices

```


## Assistant

<thinking>
So credentials are tied to the account level, not individual devices—each account gets a single VLESS config that works across all connected devices. The device limit is really just an administrative tracking mechanism for billing and display purposes, not something that actually blocks VPN access. The real concurrency control happens at the VPN layer through Marzban's IP limiting features. But then login itself...

The login endpoint doesn't validate device limits or require prior device registration—it just issues tokens for whatever device_guid is provided. Device registration and limit enforcement happen on a completely separate endpoint that clients don't need to call before logging in. Since the VPN credential is shared per-account, the actual access control is just the master token, and the device_guid is purely for bookkeeping. The credentials endpoint doesn't check whether a device is registered or within limits—it only verifies the account. This means someone with a master token could log in from unlimited different devices without ever registering them, and each one would successfully retrieve the VPN config. The device limit feature isn't actually enforced as a gate on credential access, making it more of a business-logic gap than a security control—a customer could share their master token widely and each person logging in with a different device_guid would pull the VPN credentials freely without any server-side registration requirement.

The actual concurrent session enforcement is deferred to Marzban's IP limiter on the VPN layer itself, which is a legitimate architectural choice, but it does mean the login and credentials flow is completely decoupled from the device registry. I should verify whether there's any automatic device registration happening behind the scenes during login—I didn't see it in the auth code, so let me search to confirm.
</thinking>

**Tool Call: Search files for regex `register_device|device_service`**
Status: Completed

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L20-26

```
from app.dependencies import (
    get_admin_account_service,
    get_current_admin,
    get_device_service,
    get_signal_service,
    require_super_admin,
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L227-232

```
async def list_devices(
    account_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
    device_service: DeviceService = Depends(get_device_service),
) -> AdminDeviceListResponse:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L243-247

```
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Service error")

    devices = await device_service.get_devices_for_account(account.id)
    return AdminDeviceListResponse(
        devices=[
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\devices.py#L23-27

```
from fastapi import APIRouter, Depends, Request, status

from app.dependencies import get_current_account, get_device_service, get_signal_service
from app.models.account import Account
from app.models.connection_signal import ConnectionEventType
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\devices.py#L81-87

```
async def register_device(
    request: RegisterDeviceRequest,
    http_request: Request,
    current_account: Account = Depends(get_current_account),
    device_service: DeviceService = Depends(get_device_service),
    signal_service: ConnectionSignalService = Depends(get_signal_service),
) -> DeviceResponse:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\devices.py#L89-99

```
    try:
        device = await device_service.register_device(
            current_account.id,
            request.device_guid,
            request.friendly_name,
        )
    except Exception:
        logger.info("Register device failed")
        await safe_record_signal(
            signal_service,
            account_id=current_account.id,
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\devices.py#L129-132

```
async def list_devices(
    current_account: Account = Depends(get_current_account),
    device_service: DeviceService = Depends(get_device_service),
) -> DeviceListResponse:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\devices.py#L133-138

```
    """Return all client devices owned by the authenticated account."""
    devices = await device_service.get_devices_for_account(current_account.id)
    logger.info("List devices succeeded")
    return DeviceListResponse(
        devices=[DeviceResponse.model_validate(d) for d in devices]
    )
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\devices.py#L152-156

```
async def get_device(
    device_guid: str,
    current_account: Account = Depends(get_current_account),
    device_service: DeviceService = Depends(get_device_service),
) -> DeviceResponse:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\devices.py#L157-160

```
    """Retrieve exactly one device. Returns 404 if device is missing or belongs to another account."""
    device = await device_service.get_device(current_account.id, device_guid)
    logger.info("Get device succeeded")
    return DeviceResponse.model_validate(device)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\devices.py#L175-182

```
async def rename_device(
    device_guid: str,
    request: RenameDeviceRequest,
    http_request: Request,
    current_account: Account = Depends(get_current_account),
    device_service: DeviceService = Depends(get_device_service),
    signal_service: ConnectionSignalService = Depends(get_signal_service),
) -> DeviceResponse:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\devices.py#L184-194

```
    try:
        device = await device_service.rename_device(
            current_account.id, device_guid, request.friendly_name
        )
    except Exception:
        logger.info("Rename device failed")
        await safe_record_signal(
            signal_service,
            account_id=current_account.id,
            event_type=ConnectionEventType.DEVICE_RENAME,
            success=False,
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\devices.py#L223-229

```
async def deactivate_device(
    device_guid: str,
    http_request: Request,
    current_account: Account = Depends(get_current_account),
    device_service: DeviceService = Depends(get_device_service),
    signal_service: ConnectionSignalService = Depends(get_signal_service),
) -> SuccessResponse:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\devices.py#L231-241

```
    try:
        await device_service.deactivate_device(current_account.id, device_guid)
    except InactiveDeviceError:
        logger.info("Deactivate device succeeded (already inactive)")
        await safe_record_signal(
            signal_service,
            account_id=current_account.id,
            event_type=ConnectionEventType.DEVICE_DEACTIVATE,
            success=True,
            device_guid=device_guid,
            http_request=http_request,
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\devices.py#L280-286

```
async def reactivate_device(
    device_guid: str,
    http_request: Request,
    current_account: Account = Depends(get_current_account),
    device_service: DeviceService = Depends(get_device_service),
    signal_service: ConnectionSignalService = Depends(get_signal_service),
) -> DeviceResponse:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\devices.py#L288-301

```
    try:
        device = await device_service.reactivate_device(current_account.id, device_guid)
    except InactiveDeviceError:
        logger.info("Reactivate device succeeded (already active)")
        device = await device_service.get_device(current_account.id, device_guid)
        await safe_record_signal(
            signal_service,
            account_id=current_account.id,
            event_type=ConnectionEventType.DEVICE_REACTIVATE,
            success=True,
            device_guid=device_guid,
            http_request=http_request,
        )
        return DeviceResponse.model_validate(device)
```


**Tool Call: Read file `billing-server\app\services\credential_service.py`**
Status: Completed

```OverREALITY/billing-server/app/services/credential_service.py
     1	"""
     2	credential_service.py — VPN Credential Lifecycle & Client Configuration Delivery Service (Phase 2.4).
     3	Responsible for securely exposing VPN credentials to authenticated users after provisioning.
     4	Never communicates with Marzban directly; consumes ProvisioningService exclusively.
     5	Enforces zero-secret logging and generates client configuration blobs on demand.
     6	"""
     7	from __future__ import annotations
     8	
     9	import logging
    10	import urllib.parse
    11	import uuid
    12	from typing import Any
    13	from sqlalchemy.ext.asyncio import AsyncSession
    14	
    15	from app.exceptions import EntityNotFoundError
    16	from app.models import ProvisioningState, ProvisioningProfile
    17	from app.services.provisioning.provider import ProvisionedUserDTO
    18	from app.services.provisioning.service import ProvisioningService
    19	from app.services.exceptions import (
    20	    CredentialServiceError,
    21	    CredentialNotFoundError,
    22	    CredentialAlreadyRevokedError,
    23	    CredentialAlreadyActiveError,
    24	    CredentialRotationFailedError,
    25	    ProvisioningServiceError,
    26	    ProvisioningConflictError,
    27	)
    28	
    29	logger = logging.getLogger(__name__)
    30	
    31	
    32	class CredentialService:
    33	    """
    34	    Domain service for VPN credential lifecycle management.
    35	    Retrieves canonical provisioning profile from ProvisioningService and dynamically generates
    36	    VLESS URIs, sing-box configurations, and Clash placeholders on demand without storing
    37	    configuration blobs in database columns.
    38	    """
    39	
    40	    def __init__(self, session: AsyncSession, provisioning_service: ProvisioningService) -> None:
    41	        self.session = session
    42	        self.provisioning_service = provisioning_service
    43	
    44	    def _extract_vless_uri(self, links: list[str]) -> str:
    45	        """Find and return the VLESS URI from provider link list."""
    46	        for link in links:
    47	            if link.startswith("vless://"):
    48	                return link
    49	        raise CredentialNotFoundError("No VLESS URI found in remote provisioning profile.")
    50	
    51	    def _parse_vless_uri(self, uri: str, remote_user_id: str) -> dict[str, Any]:
    52	        """
    53	        Parse a canonical VLESS Reality URI into transport components.
    54	        Format: vless://uuid@hostname:port?type=tcp&security=reality&pbk=pubkey&sni=sni&sid=shortid#tag
    55	        """
    56	        try:
    57	            parsed = urllib.parse.urlparse(uri)
    58	            client_uuid = parsed.username or remote_user_id
    59	            hostname = parsed.hostname or "vpn.realitytunnel.com"
    60	            port = parsed.port or 443
    61	
    62	            query_params = urllib.parse.parse_qs(parsed.query)
    63	            transport = query_params.get("type", ["tcp"])[0]
    64	            security = query_params.get("security", ["reality"])[0]
    65	            public_key = query_params.get("pbk", [""])[0]
    66	            short_id = query_params.get("sid", [""])[0]
    67	            sni = query_params.get("sni", [hostname])[0]
    68	
    69	            return {
    70	                "server_hostname": hostname,
    71	                "port": port,
    72	                "protocol": "vless",
    73	                "transport": transport,
    74	                "security": security,
    75	                "uuid": client_uuid,
    76	                "public_key": public_key,
    77	                "short_id": short_id,
    78	                "sni": sni,
    79	                "vless_uri": uri,
    80	            }
    81	        except Exception as exc:
    82	            logger.error("Failed to parse VLESS URI structure")
    83	            raise CredentialServiceError("Malformed VLESS URI in provisioning profile") from exc
    84	
    85	    def _generate_singbox_config(self, meta: dict[str, Any]) -> dict[str, Any]:
    86	        """
    87	        Generate a canonical sing-box 1.8+ outbound configuration dictionary on demand.
    88	        Never stored in database.
    89	        """
    90	        return {
    91	            "log": {"level": "info"},
    92	            "outbounds": [
    93	                {
    94	                    "type": "vless",
    95	                    "tag": "proxy",
    96	                    "server": meta["server_hostname"],
    97	                    "server_port": meta["port"],
    98	                    "uuid": meta["uuid"],
    99	                    "flow": "xtls-rprx-vision",
   100	                    "network": meta["transport"],
   101	                    "tls": {
   102	                        "enabled": True,
   103	                        "server_name": meta["sni"],
   104	                        "utls": {"enabled": True, "fingerprint": "chrome"},
   105	                        "reality": {
   106	                            "enabled": True,
   107	                            "public_key": meta["public_key"],
   108	                            "short_id": meta["short_id"],
   109	                        },
   110	                    },
   111	                },
   112	                {"type": "direct", "tag": "direct"},
   113	            ],
   114	        }
   115	
   116	    def _generate_clash_config(self, meta: dict[str, Any]) -> dict[str, Any]:
   117	        """
   118	        Generate placeholder configuration for Clash (REALITY unsupported in standard Clash).
   119	        """
   120	        return {
   121	            "status": "unsupported",
   122	            "message": "Clash REALITY configuration is currently unsupported. Please use sing-box or VLESS URI.",
   123	            "protocol": "vless-reality",
   124	            "server": meta["server_hostname"],
   125	            "port": meta["port"],
   126	        }
   127	
   128	    def _build_credential_payload(
   129	        self,
   130	        profile: ProvisioningProfile,
   131	        user_dto: ProvisionedUserDTO,
   132	    ) -> dict[str, Any]:
   133	        """Build the full credential dictionary with generated client configs."""
   134	        vless_uri = self._extract_vless_uri(user_dto.links)
   135	        meta = self._parse_vless_uri(vless_uri, profile.remote_user_id)
   136	
   137	        singbox_config = self._generate_singbox_config(meta)
   138	        clash_config = self._generate_clash_config(meta)
   139	
   140	        return {
   141	            "server_hostname": meta["server_hostname"],
   142	            "port": meta["port"],
   143	            "protocol": meta["protocol"],
   144	            "transport": meta["transport"],
   145	            "security": meta["security"],
   146	            "uuid": meta["uuid"],
   147	            "public_key": meta["public_key"],
   148	            "short_id": meta["short_id"],
   149	            "sni": meta["sni"],
   150	            "client_config": singbox_config,
   151	            "vless_uri": meta["vless_uri"],
   152	            "singbox_config": singbox_config,
   153	            "clash_config": clash_config,
   154	        }
   155	
   156	    async def get_credentials(self, account_id: uuid.UUID) -> dict[str, Any]:
   157	        """
   158	        Retrieve active VPN profile and client configurations for an account.
   159	        Idempotent: repeated retrievals return the current active profile without regenerating.
   160	        """
   161	        try:
   162	            profile, user_dto = await self.provisioning_service.get_provisioned_user(account_id)
   163	        except EntityNotFoundError as exc:
   164	            raise CredentialNotFoundError(f"No provisioning profile found for account {account_id}") from exc
   165	        except Exception as exc:
   166	            raise CredentialServiceError(str(exc)) from exc
   167	
   168	        if profile.provisioning_state == ProvisioningState.TERMINATED:
   169	            raise CredentialNotFoundError(f"Provisioning profile for account {account_id} is terminated")
   170	
   171	        if profile.provisioning_state == ProvisioningState.SUSPENDED or user_dto.status.lower() in ("disabled", "suspended", "inactive"):
   172	            raise CredentialAlreadyRevokedError(f"Provisioning profile for account {account_id} is revoked or suspended")
   173	
   174	        logger.info("Retrieved active credentials for account_id=%s", account_id)
   175	        return self._build_credential_payload(profile, user_dto)
   176	
   177	    async def get_vless_uri(self, account_id: uuid.UUID) -> str:
   178	        """Retrieve VLESS URI for an account."""
   179	        data = await self.get_credentials(account_id)
   180	        return str(data["vless_uri"])
   181	
   182	    async def get_singbox_config(self, account_id: uuid.UUID) -> dict[str, Any]:
   183	        """Retrieve sing-box JSON configuration for an account."""
   184	        data = await self.get_credentials(account_id)
   185	        return dict(data["singbox_config"])
   186	
   187	    async def get_clash_config(self, account_id: uuid.UUID) -> dict[str, Any]:
   188	        """Retrieve Clash placeholder configuration for an account."""
   189	        data = await self.get_credentials(account_id)
   190	        return dict(data["clash_config"])
   191	
   192	    async def regenerate_credentials(self, account_id: uuid.UUID) -> dict[str, Any]:
   193	        """
   194	        Rotate and regenerate credentials for an account.
   195	        Acquires row lock, invalidates previous credential, and synchronizes with provider.
   196	        """
   197	        try:
   198	            profile, user_dto = await self.provisioning_service.rotate_user_credentials(account_id)
   199	            logger.info("Successfully rotated credentials for account_id=%s", account_id)
   200	            return self._build_credential_payload(profile, user_dto)
   201	        except EntityNotFoundError as exc:
   202	            raise CredentialNotFoundError(f"No provisioning profile found for account {account_id}") from exc
   203	        except Exception as exc:
   204	            logger.error("Failed credential rotation for account_id=%s", account_id)
   205	            raise CredentialRotationFailedError(f"Credential rotation failed: {str(exc)}") from exc
   206	
   207	    async def revoke_credentials(self, account_id: uuid.UUID, *, commit: bool = True) -> None:
   208	        """
   209	        Revoke active credentials by suspending the remote provisioning profile.
   210	        Idempotency / State Check: raises CredentialAlreadyRevokedError if already suspended.
   211	        """
   212	        profile = await self.provisioning_service.provisioning_repo.get_by_account_id(account_id, for_update=True)
   213	        if not profile or profile.provisioning_state == ProvisioningState.TERMINATED:
   214	            raise CredentialNotFoundError(f"No active provisioning profile found for account {account_id}")
   215	
   216	        if profile.provisioning_state == ProvisioningState.SUSPENDED:
   217	            raise CredentialAlreadyRevokedError(f"Credentials for account {account_id} are already revoked/suspended")
   218	
   219	        try:
   220	            await self.provisioning_service.suspend_subscription(account_id, commit=commit)
   221	            logger.info("Successfully revoked credentials for account_id=%s", account_id)
   222	        except Exception as exc:
   223	            raise CredentialServiceError(f"Failed to revoke credentials: {str(exc)}") from exc
   224	
   225	    async def restore_credentials(self, account_id: uuid.UUID, *, commit: bool = True) -> None:
   226	        """
   227	        Restore previously revoked credentials by reactivating the remote provisioning profile.
   228	        Idempotency / State Check: raises CredentialAlreadyActiveError if already active.
   229	        """
   230	        profile = await self.provisioning_service.provisioning_repo.get_by_account_id(account_id, for_update=True)
   231	        if not profile or profile.provisioning_state == ProvisioningState.TERMINATED:
   232	            raise CredentialNotFoundError(f"No provisioning profile found for account {account_id}")
   233	
   234	        if profile.provisioning_state == ProvisioningState.ACTIVE:
   235	            raise CredentialAlreadyActiveError(f"Credentials for account {account_id} are already active")
   236	
   237	        try:
   238	            await self.provisioning_service.reactivate_subscription(account_id, commit=commit)
   239	            logger.info("Successfully restored credentials for account_id=%s", account_id)
   240	        except Exception as exc:
   241	            raise CredentialServiceError(f"Failed to restore credentials: {str(exc)}") from exc
   242	
   243	    async def generate(self, account_id: uuid.UUID) -> dict[str, Any]:
   244	        """
   245	        Verify active provisioning profile and generate client configuration payload on demand.
   246	        Alias for get_credentials in event-driven provisioning workflows (Phase 2.5).
   247	        """
   248	        return await self.get_credentials(account_id)
   249	

```


## Assistant

<thinking>
The logging here uses the internal account UUID rather than sensitive identifiers like the master token or human-readable account ID, so that's acceptable from a security standpoint.

Now I'm shifting focus to the authorization layer — I need to verify that admin routes consistently enforce `get_current_admin` and `require_super_admin`, check for proper ownership validation in billing and account management to prevent horizontal privilege escalation, and confirm rate limiting is applied to login and refresh endpoints. I'll also scan the admin modules to ensure there's no accidental mixing of customer and admin authentication contexts.

Given the scope, I'm going to handle payments myself since it's critical, then delegate provisioning deep dives, database concurrency patterns, Docker/CI-CD, and security hardening to parallel sub-agents while I quickly review the admin router patterns.
</thinking>

**Tool Call: Search files for regex `@router\.(get|post|patch|delete|put)|Depends\(get_current_admin\)|Depends\(require_super_admin\)|Depends\(get_current_account\)`**
Status: Completed

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L1-11

```
"""
admin.py — Administrative Account Management Router.

Provides HTTP endpoints for operator-level account inspection and management.
This module is a THIN orchestration layer only.

ARCHITECTURAL INVARIANTS:
1. No repository access. All data operations go through AdminAccountService,
   DeviceService, or ConnectionSignalService.
2. No business logic. The router validates input, calls the service, maps to DTO, returns.
3. Every endpoint requires Depends(get_current_admin) (read) or Depends(require_super_admin) (write).
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L70-76

```
@router.get(
    "/accounts",
    summary="List all accounts (paginated)",
    response_model=AdminAccountListResponse,
    status_code=status.HTTP_200_OK,
    responses={401: {"description": "Admin authentication required"}},
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L77-82

```
async def list_accounts(
    limit: int = Query(default=50, ge=1, le=200, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    current_admin: AdminUser = Depends(get_current_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
) -> AdminAccountListResponse:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L95-104

```
@router.get(
    "/accounts/{account_id}",
    summary="Get account detail",
    response_model=AdminAccountResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Admin authentication required"},
        404: {"description": "Account not found"},
    },
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L105-109

```
async def get_account(
    account_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
) -> AdminAccountResponse:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L124-134

```
@router.patch(
    "/accounts/{account_id}/suspend",
    summary="Suspend a customer account (super-admin only)",
    response_model=AdminAccountResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Admin authentication required"},
        403: {"description": "Super-admin privilege required"},
        404: {"description": "Account not found"},
    },
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L135-139

```
async def suspend_account(
    account_id: str,
    current_admin: AdminUser = Depends(require_super_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
) -> AdminAccountResponse:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L153-163

```
@router.patch(
    "/accounts/{account_id}/activate",
    summary="Activate a customer account (super-admin only)",
    response_model=AdminAccountResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Admin authentication required"},
        403: {"description": "Super-admin privilege required"},
        404: {"description": "Account not found"},
    },
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L164-168

```
async def activate_account(
    account_id: str,
    current_admin: AdminUser = Depends(require_super_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
) -> AdminAccountResponse:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L182-192

```
@router.patch(
    "/accounts/{account_id}/extend-subscription",
    summary="Extend account subscription (super-admin only)",
    response_model=AdminAccountResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid extension duration"},
        401: {"description": "Admin authentication required"},
        403: {"description": "Super-admin privilege required"},
        404: {"description": "Account not found"},
    },
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L194-199

```
async def extend_subscription(
    account_id: str,
    body: ExtendSubscriptionRequest,
    current_admin: AdminUser = Depends(require_super_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
) -> AdminAccountResponse:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L217-226

```
@router.get(
    "/accounts/{account_id}/devices",
    summary="List devices for an account",
    response_model=AdminDeviceListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Admin authentication required"},
        404: {"description": "Account not found"},
    },
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L227-232

```
async def list_devices(
    account_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
    device_service: DeviceService = Depends(get_device_service),
) -> AdminDeviceListResponse:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L263-273

```
@router.post(
    "/accounts/{account_id}/logout-all",
    summary="Force logout all sessions for an account (super-admin only)",
    response_model=AdminLogoutAllResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Admin authentication required"},
        403: {"description": "Super-admin privilege required"},
        404: {"description": "Account not found"},
    },
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L274-278

```
async def logout_all(
    account_id: str,
    current_admin: AdminUser = Depends(require_super_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
) -> AdminLogoutAllResponse:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L296-305

```
@router.get(
    "/accounts/{account_id}/signals",
    summary="List connection signals for an account (paginated)",
    response_model=AdminSignalListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Admin authentication required"},
        404: {"description": "Account not found"},
    },
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin.py#L306-313

```
async def list_signals(
    account_id: str,
    limit: int = Query(default=50, ge=1, le=200, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    current_admin: AdminUser = Depends(get_current_admin),
    admin_account_service: AdminAccountService = Depends(get_admin_account_service),
    signal_service: ConnectionSignalService = Depends(get_signal_service),
) -> AdminSignalListResponse:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_auth.py#L26-36

```
@router.post(
    "/login",
    summary="Authenticate administrative user and issue Admin JWT",
    response_model=AdminLoginResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_rate_limit("admin_login"))],
    responses={
        400: {"description": "Validation error"},
        401: {"description": "Authentication failed or account inactive"},
        429: {"description": "Rate limit exceeded"},
        501: {"description": "MFA required but not implemented"},
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_auth.py#L65-73

```
@router.get(
    "/me",
    summary="Retrieve current administrative profile",
    response_model=AdminProfileResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Authentication failed or token invalid"},
    },
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_auth.py#L74-76

```
async def me(
    current_admin: AdminUser = Depends(get_current_admin),
) -> AdminProfileResponse:
```


## Assistant

Good, admin authorization looks properly enforced consistently. Let me check the remaining admin routers and billing/webhooks quickly, then move into payments in depth.

**Tool Call: Search files for regex `@router\.(get|post|patch|delete|put)|Depends\(get_current_admin\)|Depends\(require_super_admin\)`**
Status: Completed

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L64-68

```
@router.get(
    "/dashboard",
    response_model=AdminDashboardDTO,
    summary="Retrieve administrative billing dashboard metrics",
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L69-72

```
async def get_dashboard(
    _admin: AdminUser = Depends(get_current_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminDashboardDTO:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L82-86

```
@router.get(
    "/subscriptions",
    response_model=AdminSubscriptionListDTO,
    summary="List customer subscriptions",
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L87-93

```
async def list_subscriptions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(None, alias="status"),
    _admin: AdminUser = Depends(get_current_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminSubscriptionListDTO:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L101-105

```
@router.get(
    "/subscription/{subscription_id}",
    response_model=AdminSubscriptionDTO,
    summary="Get subscription details",
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L106-110

```
async def get_subscription(
    subscription_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminSubscriptionDTO:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L118-122

```
@router.post(
    "/subscription/{id}/activate",
    response_model=AdminSubscriptionDTO,
    summary="Activate subscription",
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L123-127

```
async def activate_subscription(
    id: str,
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminSubscriptionDTO:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L135-139

```
@router.post(
    "/subscription/{id}/grace",
    response_model=AdminSubscriptionDTO,
    summary="Put subscription in grace period",
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L140-145

```
async def grace_subscription(
    id: str,
    body: AdminSubscriptionGraceRequest = AdminSubscriptionGraceRequest(),
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminSubscriptionDTO:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L153-157

```
@router.post(
    "/subscription/{id}/expire",
    response_model=AdminSubscriptionDTO,
    summary="Expire subscription",
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L158-162

```
async def expire_subscription(
    id: str,
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminSubscriptionDTO:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L170-174

```
@router.post(
    "/subscription/{id}/cancel",
    response_model=AdminSubscriptionDTO,
    summary="Cancel subscription",
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L175-179

```
async def cancel_subscription(
    id: str,
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminSubscriptionDTO:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L187-191

```
@router.post(
    "/subscription/{id}/renew",
    response_model=AdminSubscriptionDTO,
    summary="Renew subscription expiration",
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L192-197

```
async def renew_subscription(
    id: str,
    body: AdminSubscriptionRenewRequest,
    _admin: AdminUser = Depends(require_super_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminSubscriptionDTO:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L207-211

```
@router.get(
    "/payments",
    response_model=AdminPaymentListDTO,
    summary="List payment transactions",
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L212-218

```
async def list_payments(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(None, alias="status"),
    _admin: AdminUser = Depends(get_current_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminPaymentListDTO:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L226-230

```
@router.get(
    "/payment/{payment_id}",
    response_model=AdminPaymentDTO,
    summary="Get payment details",
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_billing.py#L231-235

```
async def get_payment(
    payment_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    service: AdminBillingService = Depends(get_admin_billing_service),
) -> AdminPaymentDTO:
```


**Tool Call: Search files for regex `@router\.(get|post|patch|delete|put)|Depends\(get_current_admin\)|Depends\(require_super_admin\)`**
Status: Completed

file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_recovery.py#L45-49

```
@router.post(
    "/backups",
    summary="Create data backup snapshot",
    status_code=status.HTTP_201_CREATED,
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_recovery.py#L50-53

```
async def create_backup_snapshot(
    session: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(require_super_admin),
) -> dict[str, Any]:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_recovery.py#L62-65

```
@router.get(
    "/backups",
    summary="List stored backup snapshots",
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_recovery.py#L66-68

```
async def list_stored_backups(
    _admin: AdminUser = Depends(get_current_admin),
) -> list[dict[str, Any]]:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_recovery.py#L77-80

```
@router.get(
    "/backups/{backup_id}/preview",
    summary="Inspect restore preview without restoring",
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_recovery.py#L81-84

```
async def get_restore_preview(
    backup_id: str,
    _admin: AdminUser = Depends(get_current_admin),
) -> dict[str, Any]:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_recovery.py#L93-96

```
@router.post(
    "/backups/{backup_id}/verify",
    summary="Execute integrity and SHA-256 checksum verification",
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_recovery.py#L97-100

```
async def verify_backup_integrity(
    backup_id: str,
    _admin: AdminUser = Depends(require_super_admin),
) -> dict[str, Any]:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_recovery.py#L109-112

```
@router.post(
    "/prune",
    summary="Trigger manual retention pruning",
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\routers\admin_recovery.py#L113-115

```
async def prune_stored_backups(
    _admin: AdminUser = Depends(require_super_admin),
) -> dict[str, Any]:
```


**Tool Call: Read file `billing-server\app\routers\webhooks.py`**
Status: Completed

```OverREALITY/billing-server/app/routers/webhooks.py
     1	import logging
     2	from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
     3	from app.dependencies import get_webhook_service
     4	from app.services.payment.webhook_service import WebhookService
     5	from app.services.exceptions import (
     6	    PaymentWebhookError,
     7	    PaymentVerificationError,
     8	    ProvisioningTimeoutError,
     9	    ProvisioningUnavailableError,
    10	    ProvisioningSynchronizationError,
    11	    PaymentTimeoutError,
    12	    PaymentServiceError,
    13	    ServiceError,
    14	)
    15	
    16	
    17	logger = logging.getLogger(__name__)
    18	
    19	router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])
    20	
    21	
    22	@router.post("/razorpay", status_code=status.HTTP_200_OK)
    23	async def handle_razorpay_webhook(
    24	    request: Request,
    25	    x_razorpay_signature: str | None = Header(None),
    26	    webhook_service: WebhookService = Depends(get_webhook_service),
    27	) -> dict[str, str]:
    28	    """
    29	    Ingest Razorpay webhook notifications.
    30	    Verifies HMAC-SHA256 signature in X-Razorpay-Signature header.
    31	    Maps domain exceptions to HTTP status codes:
    32	    - 200 OK: Successfully processed or duplicate event (idempotent).
    33	    - 400 Bad Request: Invalid signature, malformed JSON, or validation error (no retry).
    34	    - 503 Service Unavailable: Transient gateway or provisioning timeout (provider retries).
    35	    """
    36	    if not x_razorpay_signature:
    37	        logger.warning("Rejected webhook request: missing X-Razorpay-Signature header")
    38	        raise HTTPException(
    39	            status_code=status.HTTP_400_BAD_REQUEST,
    40	            detail="Missing X-Razorpay-Signature header",
    41	        )
    42	
    43	    try:
    44	        raw_payload = await request.body()
    45	        await webhook_service.process_event(raw_payload, x_razorpay_signature)
    46	        return {"status": "ok"}
    47	
    48	    except (PaymentWebhookError, PaymentVerificationError, ValueError) as exc:
    49	        logger.warning("Webhook verification/validation failed: %s", str(exc))
    50	        raise HTTPException(
    51	            status_code=status.HTTP_400_BAD_REQUEST,
    52	            detail=str(exc),
    53	        )
    54	    except (ProvisioningTimeoutError, ProvisioningUnavailableError, PaymentTimeoutError) as exc:
    55	        logger.error("Transient error during webhook processing: %s", str(exc))
    56	        raise HTTPException(
    57	            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    58	            detail="Service temporarily unavailable, please retry",
    59	        )
    60	    except Exception as exc:
    61	        logger.error("Unhandled exception processing webhook: %s", str(exc))
    62	        raise HTTPException(
    63	            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    64	            detail="Internal server error",
    65	        )

```


## Assistant

Authorization enforcement across admin routers looks consistent and correct. Now let's dig into the payment/webhook subsystem in depth.

**Tool Call: List the `OverREALITY/billing-server/app/services/payment` directory's contents**
Status: Completed

# Folders:
OverREALITY\billing-server\app\services\payment\__pycache__

# Files:
OverREALITY\billing-server\app\services\payment\__init__.py
OverREALITY\billing-server\app\services\payment\provider.py
OverREALITY\billing-server\app\services\payment\razorpay.py
OverREALITY\billing-server\app\services\payment\service.py
OverREALITY\billing-server\app\services\payment\webhook_service.py


**Tool Call: Read file `billing-server\app\models\payment.py`**
Status: Completed

```OverREALITY/billing-server/app/models/payment.py
     1	"""
     2	payment.py — Payment entity representing billing transactions and gateway order lifecycle.
     3	"""
     4	from __future__ import annotations
     5	
     6	import uuid
     7	from datetime import datetime
     8	from enum import Enum
     9	from typing import TYPE_CHECKING
    10	from sqlalchemy import Integer, String, DateTime, Enum as SQLEnum, ForeignKey, text
    11	from sqlalchemy.orm import Mapped, mapped_column, relationship
    12	from sqlalchemy.types import Uuid
    13	
    14	from app.database import Base
    15	from app.models.base import TimestampMixin
    16	
    17	if TYPE_CHECKING:
    18	    from app.models.account import Account
    19	    from app.models.subscription import Subscription
    20	
    21	
    22	class PaymentStatus(str, Enum):
    23	    """
    24	    Lifecycle state of a payment transaction.
    25	    """
    26	    CREATED = "CREATED"
    27	    PENDING = "PENDING"
    28	    PAID = "PAID"
    29	    FAILED = "FAILED"
    30	    REFUNDED = "REFUNDED"
    31	    CANCELLED = "CANCELLED"
    32	
    33	
    34	class PaymentProviderType(str, Enum):
    35	    """
    36	    Supported payment gateway providers.
    37	    """
    38	    RAZORPAY = "RAZORPAY"
    39	
    40	
    41	class Payment(Base, TimestampMixin):
    42	    """
    43	    Payments table.
    44	    Stores order identifiers, monetary amounts in minor units (e.g. paise/cents),
    45	    idempotency keys, and verification status.
    46	    Never stores credit card numbers, CVV, UPI PINs, or raw bank secrets.
    47	    """
    48	    __tablename__ = "payments"
    49	
    50	    id: Mapped[uuid.UUID] = mapped_column(
    51	        Uuid(as_uuid=True),
    52	        primary_key=True,
    53	        default=uuid.uuid4,
    54	        server_default=text("gen_random_uuid()"),
    55	    )
    56	    account_id: Mapped[uuid.UUID] = mapped_column(
    57	        Uuid(as_uuid=True),
    58	        ForeignKey("accounts.id", ondelete="CASCADE"),
    59	        nullable=False,
    60	        index=True,
    61	    )
    62	    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
    63	        Uuid(as_uuid=True),
    64	        ForeignKey("subscriptions.id", ondelete="SET NULL"),
    65	        nullable=True,
    66	        index=True,
    67	    )
    68	    provider: Mapped[PaymentProviderType] = mapped_column(
    69	        SQLEnum(
    70	            PaymentProviderType,
    71	            name="payment_provider_type",
    72	            create_constraint=True,
    73	            native_enum=True,
    74	        ),
    75	        nullable=False,
    76	        default=PaymentProviderType.RAZORPAY,
    77	        index=True,
    78	    )
    79	    provider_payment_id: Mapped[str | None] = mapped_column(
    80	        String(128), index=True, nullable=True
    81	    )
    82	    provider_order_id: Mapped[str | None] = mapped_column(
    83	        String(128), index=True, nullable=True
    84	    )
    85	    amount_minor_units: Mapped[int] = mapped_column(
    86	        Integer, nullable=False
    87	    )
    88	    currency: Mapped[str] = mapped_column(
    89	        String(3), nullable=False, default="INR"
    90	    )
    91	    status: Mapped[PaymentStatus] = mapped_column(
    92	        SQLEnum(
    93	            PaymentStatus,
    94	            name="payment_status",
    95	            create_constraint=True,
    96	            native_enum=True,
    97	        ),
    98	        nullable=False,
    99	        default=PaymentStatus.CREATED,
   100	        index=True,
   101	    )
   102	    idempotency_key: Mapped[str] = mapped_column(
   103	        String(128), unique=True, index=True, nullable=False
   104	    )
   105	    paid_at: Mapped[datetime | None] = mapped_column(
   106	        DateTime(timezone=True), nullable=True
   107	    )
   108	
   109	    account: Mapped["Account"] = relationship("Account")
   110	    subscription: Mapped["Subscription | None"] = relationship("Subscription")

```


**Tool Call: Read file `billing-server\app\services\payment\webhook_service.py`**
Status: Completed

```OverREALITY/billing-server/app/services/payment/webhook_service.py
     1	import logging
     2	from typing import Any
     3	from app.models.payment import Payment
     4	from app.services.payment.service import PaymentService
     5	from app.services.exceptions import PaymentWebhookError
     6	
     7	
     8	logger = logging.getLogger(__name__)
     9	
    10	
    11	class WebhookService:
    12	    """
    13	    Dedicated service for processing incoming payment gateway webhooks.
    14	    Orchestrates the domain dependency chain:
    15	    Webhook Router -> WebhookService -> PaymentService -> SubscriptionService -> ProvisioningService -> CredentialService.
    16	    """
    17	
    18	    def __init__(self, payment_service: PaymentService) -> None:
    19	        self.payment_service = payment_service
    20	
    21	    async def process_event(
    22	        self,
    23	        raw_payload: bytes | str,
    24	        signature: str,
    25	    ) -> Payment | None:
    26	        """
    27	        Verify webhook signature, parse event DTO, and dispatch to appropriate PaymentService method.
    28	        Idempotent: duplicate webhook deliveries return clean existing state.
    29	        Zero-secret logging: logs event types and IDs without logging secrets or raw HMACs.
    30	        """
    31	        dto = await self.payment_service.provider.verify_webhook(raw_payload, signature)
    32	
    33	        logger.info(
    34	            "Processing verified webhook event=%s order_id=%s payment_id=%s",
    35	            dto.event_type,
    36	            dto.provider_order_id,
    37	            dto.provider_payment_id,
    38	        )
    39	
    40	        if dto.event_type in ("payment.captured", "payment.authorized", "order.paid"):
    41	            if not dto.provider_order_id:
    42	                raise PaymentWebhookError("Webhook payload for captured payment missing order ID")
    43	            if not dto.provider_payment_id:
    44	                raise PaymentWebhookError("Webhook payload for captured payment missing payment ID")
    45	            return await self.payment_service.confirm_payment(
    46	                provider_order_id=dto.provider_order_id,
    47	                provider_payment_id=dto.provider_payment_id,
    48	            )
    49	        elif dto.event_type in ("payment.failed",):
    50	            if not dto.provider_order_id:
    51	                raise PaymentWebhookError("Webhook payload for failed payment missing order ID")
    52	            return await self.payment_service.fail_payment(
    53	                provider_order_id=dto.provider_order_id,
    54	                reason="Webhook payment.failed event",
    55	            )
    56	        elif dto.event_type in ("refund.processed",):
    57	            return await self.payment_service.process_refund_webhook(
    58	                provider_order_id=dto.provider_order_id,
    59	                provider_payment_id=dto.provider_payment_id,
    60	            )
    61	
    62	        logger.info("Ignored unhandled webhook event type: %s", dto.event_type)
    63	        return None

```


**Tool Call: Read file `billing-server\app\services\payment\razorpay.py`**
Status: Completed

```OverREALITY/billing-server/app/services/payment/razorpay.py
     1	"""
     2	razorpay.py — Razorpay implementation of the PaymentProvider interface (Phase 2.3).
     3	Handles async HTTP communication, retries with exponential backoff, HMAC signature verification,
     4	and strict zero-secret logging.
     5	"""
     6	from __future__ import annotations
     7	
     8	import asyncio
     9	import hashlib
    10	import hmac
    11	import json
    12	import logging
    13	from typing import Any
    14	import httpx
    15	
    16	from app.config import Settings
    17	from app.services.exceptions import (
    18	    PaymentProviderError,
    19	    PaymentVerificationError,
    20	    PaymentTimeoutError,
    21	    PaymentRefundError,
    22	)
    23	from app.services.payment.provider import (
    24	    PaymentProvider,
    25	    PaymentOrderDTO,
    26	    PaymentVerificationDTO,
    27	    PaymentWebhookDTO,
    28	    PaymentRefundDTO,
    29	)
    30	
    31	logger = logging.getLogger(__name__)
    32	
    33	
    34	class RazorpayProvider(PaymentProvider):
    35	    """
    36	    Razorpay gateway integration client.
    37	    Enforces strict zero-secret logging and explicit exception translation.
    38	    Never calls SubscriptionService or ProvisioningService directly.
    39	    """
    40	
    41	    def __init__(
    42	        self,
    43	        settings: Settings,
    44	        client: httpx.AsyncClient | None = None,
    45	    ) -> None:
    46	        self.base_url = settings.razorpay_base_url.rstrip("/")
    47	        self.key_id = settings.razorpay_key_id
    48	        self.key_secret = settings.razorpay_key_secret
    49	        self.webhook_secret = settings.razorpay_webhook_secret
    50	        self.timeout = settings.razorpay_timeout_seconds
    51	        self.max_retries = settings.razorpay_max_retries
    52	        self.orders_path = settings.razorpay_orders_path
    53	        self.payments_path = settings.razorpay_payments_path
    54	        self.refunds_path = settings.razorpay_refunds_path
    55	
    56	        self._external_client = client is not None
    57	        self._client = client or httpx.AsyncClient(timeout=self.timeout)
    58	
    59	    async def _request_with_retries(
    60	        self,
    61	        method: str,
    62	        path: str,
    63	        json_data: dict[str, Any] | None = None,
    64	    ) -> dict[str, Any]:
    65	        """
    66	        Execute an HTTP request to Razorpay with exponential backoff retries for transient failures.
    67	        Never logs API keys, authorization headers, or customer secrets.
    68	        """
    69	        url = f"{self.base_url}{path}"
    70	        auth = (self.key_id, self.key_secret) if self.key_id and self.key_secret else None
    71	
    72	        last_exception: Exception | None = None
    73	        for attempt in range(1, self.max_retries + 1):
    74	            try:
    75	                response = await self._client.request(
    76	                    method=method,
    77	                    url=url,
    78	                    json=json_data,
    79	                    auth=auth,
    80	                    timeout=self.timeout,
    81	                )
    82	
    83	                if response.status_code in (500, 502, 503, 504):
    84	                    logger.warning(
    85	                        "Transient Razorpay server error status=%d on attempt=%d/%d",
    86	                        response.status_code,
    87	                        attempt,
    88	                        self.max_retries,
    89	                    )
    90	                    if attempt < self.max_retries:
    91	                        await asyncio.sleep(2 ** (attempt - 1))
    92	                        continue
    93	                    raise PaymentProviderError(
    94	                        f"Razorpay server unavailable after {self.max_retries} attempts (status {response.status_code})"
    95	                    )
    96	
    97	                if response.status_code >= 400:
    98	                    logger.error("Razorpay API error status=%d for path=%s", response.status_code, path)
    99	                    try:
   100	                        err_data = response.json()
   101	                        err_msg = err_data.get("error", {}).get("description", "Unknown Razorpay error")
   102	                    except Exception:
   103	                        err_msg = f"HTTP {response.status_code} from Razorpay"
   104	                    raise PaymentProviderError(f"Razorpay API request failed: {err_msg}")
   105	
   106	                return response.json()
   107	
   108	            except (httpx.TimeoutException, httpx.ConnectTimeout) as exc:
   109	                last_exception = exc
   110	                logger.warning(
   111	                    "Timeout connecting to Razorpay on attempt=%d/%d",
   112	                    attempt,
   113	                    self.max_retries,
   114	                )
   115	                if attempt < self.max_retries:
   116	                    await asyncio.sleep(2 ** (attempt - 1))
   117	                    continue
   118	                raise PaymentTimeoutError(
   119	                    f"Razorpay request timed out after {self.max_retries} attempts"
   120	                ) from exc
   121	
   122	            except httpx.RequestError as exc:
   123	                last_exception = exc
   124	                logger.warning(
   125	                    "Network error connecting to Razorpay on attempt=%d/%d",
   126	                    attempt,
   127	                    self.max_retries,
   128	                )
   129	                if attempt < self.max_retries:
   130	                    await asyncio.sleep(2 ** (attempt - 1))
   131	                    continue
   132	                raise PaymentProviderError(
   133	                    f"Network error communicating with Razorpay: {exc}"
   134	                ) from exc
   135	
   136	        raise PaymentProviderError("Failed to complete Razorpay request") from last_exception
   137	
   138	    async def create_order(
   139	        self,
   140	        amount_minor_units: int,
   141	        currency: str,
   142	        receipt: str,
   143	        notes: dict[str, str] | None = None,
   144	    ) -> PaymentOrderDTO:
   145	        """
   146	        Create a new payment order in Razorpay.
   147	        """
   148	        payload = {
   149	            "amount": amount_minor_units,
   150	            "currency": currency.upper(),
   151	            "receipt": receipt,
   152	            "notes": notes or {},
   153	        }
   154	        logger.info("Creating Razorpay order receipt=%s amount=%d currency=%s", receipt, amount_minor_units, currency)
   155	        data = await self._request_with_retries("POST", self.orders_path, json_data=payload)
   156	
   157	        order_id = str(data.get("id", ""))
   158	        if not order_id:
   159	            raise PaymentProviderError("Razorpay order response missing order ID")
   160	
   161	        return PaymentOrderDTO(
   162	            provider_order_id=order_id,
   163	            amount_minor_units=int(data.get("amount", amount_minor_units)),
   164	            currency=str(data.get("currency", currency)),
   165	            raw_data=data,
   166	        )
   167	
   168	    async def verify_webhook(
   169	        self,
   170	        payload: bytes | str,
   171	        signature: str,
   172	        secret: str | None = None,
   173	    ) -> PaymentWebhookDTO:
   174	        """
   175	        Verify Razorpay webhook HMAC-SHA256 signature and parse payload.
   176	        Never logs the secret or signature.
   177	        """
   178	        webhook_secret = secret or self.webhook_secret
   179	        if not webhook_secret:
   180	            raise PaymentVerificationError("Razorpay webhook secret is not configured")
   181	
   182	        raw_bytes = payload.encode("utf-8") if isinstance(payload, str) else payload
   183	        expected_sig = hmac.new(
   184	            webhook_secret.encode("utf-8"),
   185	            raw_bytes,
   186	            hashlib.sha256,
   187	        ).hexdigest()
   188	
   189	        if not hmac.compare_digest(expected_sig, signature):
   190	            logger.error("Razorpay webhook HMAC signature mismatch")
   191	            raise PaymentVerificationError("Invalid Razorpay webhook signature")
   192	
   193	        try:
   194	            data = json.loads(raw_bytes.decode("utf-8"))
   195	        except Exception as exc:
   196	            raise PaymentVerificationError("Malformed JSON in Razorpay webhook payload") from exc
   197	
   198	        event_type = str(data.get("event", ""))
   199	        payment_entity = data.get("payload", {}).get("payment", {}).get("entity", {})
   200	        order_entity = data.get("payload", {}).get("order", {}).get("entity", {})
   201	
   202	        provider_payment_id = payment_entity.get("id")
   203	        provider_order_id = payment_entity.get("order_id") or order_entity.get("id")
   204	        status = payment_entity.get("status", event_type)
   205	        amount = payment_entity.get("amount") or order_entity.get("amount")
   206	        currency = payment_entity.get("currency") or order_entity.get("currency")
   207	
   208	        logger.info("Verified Razorpay webhook event=%s status=%s", event_type, status)
   209	        return PaymentWebhookDTO(
   210	            event_type=event_type,
   211	            status=str(status),
   212	            provider_order_id=str(provider_order_id) if provider_order_id else None,
   213	            provider_payment_id=str(provider_payment_id) if provider_payment_id else None,
   214	            amount_minor_units=int(amount) if amount is not None else None,
   215	            currency=str(currency) if currency else None,
   216	            signature=signature,
   217	            payload=data,
   218	        )
   219	
   220	    async def fetch_payment(
   221	        self,
   222	        provider_payment_id: str,
   223	    ) -> PaymentVerificationDTO:
   224	        """
   225	        Fetch payment details from Razorpay to verify payment capture status.
   226	        """
   227	        path = self.payments_path.format(payment_id=provider_payment_id)
   228	        logger.info("Fetching Razorpay payment status for payment_id=%s", provider_payment_id)
   229	        data = await self._request_with_retries("GET", path)
   230	
   231	        status = str(data.get("status", ""))
   232	        is_valid = status in ("captured", "authorized")
   233	        order_id = str(data.get("order_id", ""))
   234	
   235	        return PaymentVerificationDTO(
   236	            is_valid=is_valid,
   237	            provider_order_id=order_id,
   238	            provider_payment_id=provider_payment_id,
   239	            status=status,
   240	            amount_minor_units=int(data["amount"]) if "amount" in data else None,
   241	            currency=str(data["currency"]) if "currency" in data else None,
   242	            raw_data=data,
   243	        )
   244	
   245	    async def refund_payment(
   246	        self,
   247	        provider_payment_id: str,
   248	        amount_minor_units: int | None = None,
   249	        notes: dict[str, str] | None = None,
   250	    ) -> PaymentRefundDTO:
   251	        """
   252	        Issue a refund for a captured Razorpay payment.
   253	        """
   254	        path = self.refunds_path.format(payment_id=provider_payment_id)
   255	        payload: dict[str, Any] = {}
   256	        if amount_minor_units is not None:
   257	            payload["amount"] = amount_minor_units
   258	        if notes:
   259	            payload["notes"] = notes
   260	
   261	        logger.info("Initiating Razorpay refund for payment_id=%s", provider_payment_id)
   262	        try:
   263	            data = await self._request_with_retries("POST", path, json_data=payload if payload else None)
   264	        except PaymentProviderError as exc:
   265	            raise PaymentRefundError(f"Failed to refund Razorpay payment: {exc}") from exc
   266	
   267	        refund_id = str(data.get("id", ""))
   268	        if not refund_id:
   269	            raise PaymentRefundError("Razorpay refund response missing refund ID")
   270	
   271	        return PaymentRefundDTO(
   272	            provider_refund_id=refund_id,
   273	            provider_payment_id=provider_payment_id,
   274	            amount_minor_units=int(data.get("amount", amount_minor_units or 0)),
   275	            status=str(data.get("status", "processed")),
   276	            raw_data=data,
   277	        )
   278	
   279	    async def health_check(self) -> bool:
   280	        """
   281	        Verify connectivity by querying orders endpoint with limit=1.
   282	        Returns True if reachable and authenticated, False otherwise.
   283	        """
   284	        try:
   285	            await self._request_with_retries("GET", f"{self.orders_path}?count=1")
   286	            return True
   287	        except Exception as exc:
   288	            logger.warning("Razorpay health check failed: %s", exc)
   289	            return False
   290	
   291	    async def close(self) -> None:
   292	        """Close the underlying HTTP client if owned by this provider."""
   293	        if not self._external_client:
   294	            await self._client.aclose()

```


## Assistant

<thinking>
The webhook signature verification looks solid with HMAC-SHA256 constant-time comparison, but I'm noticing there's no replay protection or idempotency check to prevent the same event from being processed multiple times. More critically, I need to verify that `confirm_payment` actually validates the payment amount against the expected order amount from the database — if it doesn't, someone could tamper with the webhook to claim a smaller payment was made for a much larger order. The key question is whether confirm_payment is idempotent—if an attacker replays a valid webhook they've captured, will it trigger duplicate actions or safely reject the replay? I need to examine the payment service implementation to see if there's any idempotency check based on payment ID or webhook event ID.
</thinking>

**Tool Call: Read file `billing-server\app\services\payment\service.py`**
Status: Completed

```
SUCCESS: File outline retrieved. This file is too large to read all at once, so the outline below shows the file's structure with line numbers.

IMPORTANT: Do NOT retry this call without line numbers - you will get the same outline.
Instead, use the line numbers below to read specific sections by calling this tool again with start_line and end_line parameters.

# File outline for D:\My projects\VPN\OverREALITY\billing-server\app\services\payment\service.py

class PaymentService [L30-385]
 def __init__ [L37-47]
 async def create_payment [L49-93]
 async def confirm_payment [L95-181]
 async def fail_payment [L183-202]
 async def refund_payment [L204-240]
 async def cancel_payment [L242-264]
 async def check_provider_health [L266-268]
 async def get_payment [L270-278]
 async def list_account_payments [L280-291]
 async def get_account_payment [L293-314]
 async def process_webhook [L318-349]
 async def process_refund_webhook [L351-385]

Showing symbols 1-13 (total symbols: 13)


NEXT STEPS: To read a specific symbol's implementation, call read_file with the same path plus start_line and end_line from the outline above.
For example, to read a function shown as [L100-150], use start_line: 100 and end_line: 150.
```


**Tool Call: Read file `billing-server\app\services\payment\service.py` (lines 1-265)**
Status: Completed

```OverREALITY/billing-server/app/services/payment/service.py
     1	"""
     2	service.py — PaymentService orchestrating payment transactions, gateway interactions,
     3	and entitlement activation via SubscriptionService (Phase 2.3).
     4	"""
     5	from __future__ import annotations
     6	
     7	import logging
     8	import uuid
     9	from datetime import datetime, timedelta, timezone
    10	from sqlalchemy.ext.asyncio import AsyncSession
    11	
    12	from app.exceptions import EntityNotFoundError
    13	from app.models import Payment, PaymentStatus, PaymentProviderType
    14	from app.models.base import SubscriptionLifecycleStatus
    15	from app.repositories import PaymentRepository, SubscriptionRepository
    16	from app.services.subscription_service import SubscriptionService
    17	from app.services.payment.provider import PaymentProvider
    18	from app.services.exceptions import (
    19	    PaymentServiceError,
    20	    PaymentNotFoundError,
    21	    PaymentVerificationError,
    22	    PaymentWebhookError,
    23	    DuplicateWebhookError,
    24	    PaymentRefundError,
    25	)
    26	
    27	logger = logging.getLogger(__name__)
    28	
    29	
    30	class PaymentService:
    31	    """
    32	    Orchestration service for payment lifecycle, webhook verification, and entitlement updates.
    33	    Strictly decoupled from VPN provisioning: all entitlement changes flow through SubscriptionService.
    34	    Never communicates with ProvisioningService or Marzban directly.
    35	    """
    36	
    37	    def __init__(
    38	        self,
    39	        session: AsyncSession,
    40	        provider: PaymentProvider,
    41	        subscription_service: SubscriptionService | None = None,
    42	    ) -> None:
    43	        self.session = session
    44	        self.provider = provider
    45	        self.payment_repo = PaymentRepository(session)
    46	        self.subscription_repo = SubscriptionRepository(session)
    47	        self.subscription_service = subscription_service or SubscriptionService(session)
    48	
    49	    async def create_payment(
    50	        self,
    51	        account_id: uuid.UUID,
    52	        amount_minor_units: int,
    53	        currency: str,
    54	        idempotency_key: str,
    55	        plan_id: str = "pro",
    56	        subscription_id: uuid.UUID | None = None,
    57	    ) -> Payment:
    58	        """
    59	        Create a new payment transaction and initiate an order on the payment gateway.
    60	        Idempotent: if idempotency_key already exists, returns the existing payment record.
    61	        """
    62	        existing = await self.payment_repo.get_by_idempotency_key(idempotency_key, for_update=True)
    63	        if existing:
    64	            logger.info("Returning existing payment id=%s for idempotency_key=%s", existing.id, idempotency_key)
    65	            return existing
    66	
    67	        receipt = f"rcpt_{idempotency_key[:24]}"
    68	        notes = {
    69	            "account_id": str(account_id),
    70	            "plan_id": plan_id,
    71	        }
    72	        if subscription_id:
    73	            notes["subscription_id"] = str(subscription_id)
    74	
    75	        order_dto = await self.provider.create_order(
    76	            amount_minor_units=amount_minor_units,
    77	            currency=currency,
    78	            receipt=receipt,
    79	            notes=notes,
    80	        )
    81	
    82	        payment = await self.payment_repo.create(
    83	            account_id=account_id,
    84	            subscription_id=subscription_id,
    85	            provider=PaymentProviderType.RAZORPAY,
    86	            provider_order_id=order_dto.provider_order_id,
    87	            amount_minor_units=order_dto.amount_minor_units,
    88	            currency=order_dto.currency,
    89	            status=PaymentStatus.CREATED,
    90	            idempotency_key=idempotency_key,
    91	        )
    92	        logger.info("Created new payment id=%s order_id=%s status=%s", payment.id, payment.provider_order_id, payment.status.value)
    93	        return payment
    94	
    95	    async def confirm_payment(
    96	        self,
    97	        provider_order_id: str,
    98	        provider_payment_id: str,
    99	        signature: str | None = None,
   100	        raw_payload: bytes | str | None = None,
   101	        plan_id: str = "pro",
   102	    ) -> Payment:
   103	        """
   104	        Confirm a payment upon gateway webhook or redirect verification.
   105	        Must:
   106	        1. Verify webhook signature (if provided).
   107	        2. Verify provider payment status via fetch_payment.
   108	        3. Verify idempotency using row lock (for_update=True).
   109	        4. Persist payment state to PAID.
   110	        5. Activate or renew subscription via SubscriptionService.
   111	        """
   112	        if signature and raw_payload:
   113	            await self.provider.verify_webhook(raw_payload, signature)
   114	
   115	        payment = await self.payment_repo.get_by_provider_order_id(provider_order_id, for_update=True)
   116	        if not payment and provider_payment_id:
   117	            payment = await self.payment_repo.get_by_provider_payment_id(provider_payment_id, for_update=True)
   118	        if not payment:
   119	            raise EntityNotFoundError(f"Payment for order ID {provider_order_id} not found.")
   120	
   121	        if payment.status == PaymentStatus.PAID:
   122	            logger.info("Payment id=%s (order=%s) is already PAID. Idempotent return.", payment.id, provider_order_id)
   123	            return payment
   124	
   125	        verification = await self.provider.fetch_payment(provider_payment_id)
   126	        if not verification.is_valid:
   127	            raise PaymentVerificationError(
   128	                f"Payment {provider_payment_id} is not valid or captured on the gateway (status={verification.status})"
   129	            )
   130	
   131	        try:
   132	            now = datetime.now(timezone.utc)
   133	            payment.provider_payment_id = provider_payment_id
   134	            payment.status = PaymentStatus.PAID
   135	            payment.paid_at = now
   136	            await self.payment_repo.update(payment, commit=False)
   137	
   138	            # Entitlement Activation via SubscriptionService
   139	            if payment.subscription_id:
   140	                sub = await self.subscription_repo.get_by_id(payment.subscription_id, for_update=True)
   141	                if sub:
   142	                    if sub.status in (SubscriptionLifecycleStatus.ACTIVE, SubscriptionLifecycleStatus.GRACE, SubscriptionLifecycleStatus.TRIAL):
   143	                        new_expires_at = max(sub.expires_at, now) + timedelta(days=30)
   144	                        await self.subscription_service.renew_subscription(sub.id, new_expires_at, commit=False)
   145	                    else:
   146	                        await self.subscription_service.activate_subscription(sub.id, commit=False)
   147	                    await self.session.commit()
   148	                    await self.session.refresh(payment)
   149	                    logger.info("Updated existing subscription id=%s for payment id=%s", sub.id, payment.id)
   150	                    return payment
   151	
   152	            # Look for an existing active subscription for this account
   153	            existing_active = await self.subscription_repo.get_active_for_account(payment.account_id, now, for_update=True)
   154	            if existing_active:
   155	                new_expires_at = max(existing_active.expires_at, now) + timedelta(days=30)
   156	                renewed = await self.subscription_service.renew_subscription(existing_active.id, new_expires_at, commit=False)
   157	                payment.subscription_id = renewed.id
   158	                await self.payment_repo.update(payment, commit=False)
   159	                await self.session.commit()
   160	                await self.session.refresh(payment)
   161	                logger.info("Renewed active subscription id=%s for payment id=%s", renewed.id, payment.id)
   162	                return payment
   163	
   164	            # Otherwise, create a new active subscription for the account
   165	            new_sub = await self.subscription_service.create_subscription(
   166	                account_id=payment.account_id,
   167	                plan_id=plan_id,
   168	                starts_at=now,
   169	                expires_at=now + timedelta(days=30),
   170	                status=SubscriptionLifecycleStatus.ACTIVE,
   171	                commit=False,
   172	            )
   173	            payment.subscription_id = new_sub.id
   174	            await self.payment_repo.update(payment, commit=False)
   175	            await self.session.commit()
   176	            await self.session.refresh(payment)
   177	            logger.info("Created and linked new subscription id=%s for payment id=%s", new_sub.id, payment.id)
   178	            return payment
   179	        except Exception:
   180	            await self.session.rollback()
   181	            raise
   182	
   183	    async def fail_payment(
   184	        self,
   185	        provider_order_id: str,
   186	        reason: str | None = None,
   187	    ) -> Payment:
   188	        """
   189	        Mark a payment as failed after notification from the gateway.
   190	        Idempotent if already marked FAILED or CANCELLED.
   191	        """
   192	        payment = await self.payment_repo.get_by_provider_order_id(provider_order_id, for_update=True)
   193	        if not payment:
   194	            raise EntityNotFoundError(f"Payment for order ID {provider_order_id} not found.")
   195	
   196	        if payment.status in (PaymentStatus.PAID, PaymentStatus.REFUNDED, PaymentStatus.FAILED, PaymentStatus.CANCELLED):
   197	            return payment
   198	
   199	        payment.status = PaymentStatus.FAILED
   200	        await self.payment_repo.update(payment)
   201	        logger.info("Marked payment id=%s as FAILED. Reason: %s", payment.id, reason or "Gateway notification")
   202	        return payment
   203	
   204	    async def refund_payment(
   205	        self,
   206	        payment_id: uuid.UUID,
   207	        amount_minor_units: int | None = None,
   208	        notes: dict[str, str] | None = None,
   209	    ) -> Payment:
   210	        """
   211	        Issue a refund for a paid transaction via the gateway provider.
   212	        """
   213	        payment = await self.payment_repo.get_by_id(payment_id, for_update=True)
   214	        if not payment:
   215	            raise EntityNotFoundError(f"Payment with ID {payment_id} not found.")
   216	
   217	        if payment.status != PaymentStatus.PAID:
   218	            raise PaymentRefundError(f"Cannot refund payment id={payment_id} in status {payment.status.value}")
   219	
   220	        if not payment.provider_payment_id:
   221	            raise PaymentRefundError(f"Payment id={payment_id} is missing provider_payment_id")
   222	
   223	        try:
   224	            await self.provider.refund_payment(
   225	                provider_payment_id=payment.provider_payment_id,
   226	                amount_minor_units=amount_minor_units or payment.amount_minor_units,
   227	                notes=notes,
   228	            )
   229	
   230	            payment.status = PaymentStatus.REFUNDED
   231	            await self.payment_repo.update(payment, commit=False)
   232	            if payment.subscription_id:
   233	                await self.subscription_service.cancel_subscription(payment.subscription_id, commit=False)
   234	            await self.session.commit()
   235	            await self.session.refresh(payment)
   236	            logger.info("Refunded payment id=%s amount=%s", payment.id, amount_minor_units or payment.amount_minor_units)
   237	            return payment
   238	        except Exception:
   239	            await self.session.rollback()
   240	            raise
   241	
   242	    async def cancel_payment(
   243	        self,
   244	        payment_id: uuid.UUID,
   245	        *,
   246	        commit: bool = True,
   247	    ) -> Payment:
   248	        """
   249	        Cancel a pending or created payment before capture.
   250	        """
   251	        payment = await self.payment_repo.get_by_id(payment_id, for_update=True)
   252	        if not payment:
   253	            raise EntityNotFoundError(f"Payment with ID {payment_id} not found.")
   254	
   255	        if payment.status in (PaymentStatus.PAID, PaymentStatus.REFUNDED):
   256	            raise PaymentServiceError(f"Cannot cancel payment id={payment_id} in status {payment.status.value}")
   257	
   258	        if payment.status == PaymentStatus.CANCELLED:
   259	            return payment
   260	
   261	        payment.status = PaymentStatus.CANCELLED
   262	        await self.payment_repo.update(payment, commit=commit)
   263	        logger.info("Cancelled payment id=%s", payment.id)
   264	        return payment
   265	

```


## Assistant

<thinking>
Looking at the `confirm_payment` function, it's using a row lock to prevent concurrent processing of the same payment, then checking if the payment status is already marked as paid to handle replayed webhooks idempotently. After that, it's verifying the payment details directly with Razorpay's API to ensure the webhook data is legitimate.

But there's a critical gap: the code never validates that the amount actually paid matches what was expected for the order. It retrieves the verification data which includes the amount, but doesn't compare it against the order's amount. This could be exploitable if the amount is client-controlled rather than derived server-side from the plan pricing. I need to check the billing router and service to see whether the amount parameter comes from the client request or is determined by the server based on the selected plan.

Concurrency-wise, the payment confirmation handles locking properly — different payments lock their respective rows, and subscription rows are fetched with for_update to prevent race conditions. However, there's a potential issue if two webhook deliveries for different orders arrive concurrently for the same account: both would query for an existing active subscription with for_update, and if none exists yet, the second request might not be properly blocked from creating a duplicate subscription since there's no row to lock on.

This is a classic phantom read problem — I need to check whether the Subscription model enforces a unique constraint on (account_id, status=ACTIVE) or if the repository uses serializable isolation or advisory locks to prevent duplicate active subscriptions. I should also review the billing service for amount validation and whether it trusts client-supplied values or derives them from the plan.
</thinking>

**Tool Call: Read file `billing-server\app\routers\billing.py`**
Status: Completed

```OverREALITY/billing-server/app/routers/billing.py
     1	"""
     2	billing.py — Customer Billing API Endpoints Router (Phase 2.7).
     3	
     4	Thin orchestration layer connecting HTTP requests to domain BillingService.
     5	Strictly decoupled from business logic, validation logic, and direct database queries.
     6	
     7	Endpoints:
     8	  - GET  /api/billing/subscription
     9	  - GET  /api/billing/plans
    10	  - GET  /api/billing/payments
    11	  - GET  /api/billing/payment/{payment_id}
    12	  - POST /api/billing/purchase
    13	  - POST /api/billing/cancel-auto-renew
    14	  - POST /api/billing/reactivate
    15	
    16	SECURITY & LOGGING INVARIANTS:
    17	1. Requires authenticated active customer JWT for all endpoints.
    18	2. Anti-IDOR: Account A cannot read Account B's resources. Returns 404 on cross-account access attempts.
    19	3. Zero-Secret Logging: Never logs payment payloads, customer identifiers, or credentials. Logs only generic event descriptions.
    20	"""
    21	from __future__ import annotations
    22	
    23	import logging
    24	from fastapi import APIRouter, Depends, Query, status
    25	
    26	from app.dependencies import get_current_account, get_billing_service
    27	from app.models.account import Account
    28	from app.services import BillingService
    29	from app.services.billing_dtos import (
    30	
    31	    SubscriptionDTO,
    32	    PlanDTO,
    33	    PaymentDTO,
    34	    PaymentListDTO,
    35	    PurchaseRequestDTO,
    36	    PurchaseResponseDTO,
    37	)
    38	
    39	logger = logging.getLogger(__name__)
    40	router = APIRouter(prefix="/api/billing", tags=["Billing"])
    41	
    42	
    43	@router.get(
    44	    "/subscription",
    45	    summary="Get active subscription details",
    46	    response_model=SubscriptionDTO,
    47	    status_code=status.HTTP_200_OK,
    48	    responses={
    49	        401: {"description": "Authentication required"},
    50	        500: {"description": "Unexpected service error"},
    51	    },
    52	)
    53	async def get_subscription(
    54	    current_account: Account = Depends(get_current_account),
    55	    billing_service: BillingService = Depends(get_billing_service),
    56	) -> SubscriptionDTO:
    57	    """
    58	    Retrieve customer view of their current active subscription.
    59	    Returns clean default DTO with status 'NONE' if no subscription is active.
    60	    """
    61	    logger.info("Customer subscription lookup.")
    62	    return await billing_service.get_customer_subscription(current_account.id)
    63	
    64	
    65	@router.get(
    66	    "/plans",
    67	    summary="List available subscription plans",
    68	    response_model=list[PlanDTO],
    69	    status_code=status.HTTP_200_OK,
    70	    responses={
    71	        401: {"description": "Authentication required"},
    72	        500: {"description": "Unexpected service error"},
    73	    },
    74	)
    75	async def list_plans(
    76	    current_account: Account = Depends(get_current_account),
    77	    billing_service: BillingService = Depends(get_billing_service),
    78	) -> list[PlanDTO]:
    79	    """
    80	    List all available subscription plans and their configured limits and pricing from the registry.
    81	    """
    82	    logger.info("Customer plans listing lookup.")
    83	    return billing_service.list_plans()
    84	
    85	
    86	@router.get(
    87	    "/payments",
    88	    summary="List customer payment history",
    89	    response_model=PaymentListDTO,
    90	    status_code=status.HTTP_200_OK,
    91	    responses={
    92	        401: {"description": "Authentication required"},
    93	        500: {"description": "Unexpected service error"},
    94	    },
    95	)
    96	async def list_payments(
    97	    limit: int = Query(default=20, ge=1, le=100, description="Page size limit"),
    98	    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    99	    current_account: Account = Depends(get_current_account),
   100	    billing_service: BillingService = Depends(get_billing_service),
   101	) -> PaymentListDTO:
   102	    """
   103	    Retrieve paginated payment history for the authenticated customer account, newest first.
   104	    """
   105	    logger.info("Customer payment history lookup.")
   106	    return await billing_service.list_customer_payments(current_account.id, limit=limit, offset=offset)
   107	
   108	
   109	@router.get(
   110	    "/payment/{payment_id}",
   111	    summary="Get payment transaction details",
   112	    response_model=PaymentDTO,
   113	    status_code=status.HTTP_200_OK,
   114	    responses={
   115	        401: {"description": "Authentication required"},
   116	        404: {"description": "Payment not found or owned by another account"},
   117	        500: {"description": "Unexpected service error"},
   118	    },
   119	)
   120	async def get_payment(
   121	    payment_id: str,
   122	    current_account: Account = Depends(get_current_account),
   123	    billing_service: BillingService = Depends(get_billing_service),
   124	) -> PaymentDTO:
   125	    """
   126	    Retrieve details of a specific payment transaction.
   127	    Enforces Anti-IDOR: returns 404 if payment does not exist or belongs to another account.
   128	    """
   129	    logger.info("Customer payment detail lookup.")
   130	    return await billing_service.get_customer_payment(current_account.id, payment_id)
   131	
   132	
   133	@router.post(
   134	    "/purchase",
   135	    summary="Initiate subscription purchase order",
   136	    response_model=PurchaseResponseDTO,
   137	    status_code=status.HTTP_200_OK,
   138	    responses={
   139	        400: {"description": "Validation error or invalid plan ID"},
   140	        401: {"description": "Authentication required"},
   141	        409: {"description": "Idempotency key conflict"},
   142	        500: {"description": "Unexpected service or gateway error"},
   143	    },
   144	)
   145	async def purchase_subscription(
   146	    request: PurchaseRequestDTO,
   147	    current_account: Account = Depends(get_current_account),
   148	    billing_service: BillingService = Depends(get_billing_service),
   149	) -> PurchaseResponseDTO:
   150	    """
   151	    Initiate a new subscription purchase order via payment gateway provider.
   152	    Does NOT activate subscription; activation happens exclusively via verified webhooks.
   153	    """
   154	    logger.info("Initiating subscription purchase order.")
   155	    return await billing_service.purchase_subscription(current_account.id, request)
   156	
   157	
   158	@router.post(
   159	    "/cancel-auto-renew",
   160	    summary="Disable automatic renewal for active subscription",
   161	    response_model=SubscriptionDTO,
   162	    status_code=status.HTTP_200_OK,
   163	    responses={
   164	        400: {"description": "Subscription already cancelled or invalid state"},
   165	        401: {"description": "Authentication required"},
   166	        404: {"description": "No active subscription found"},
   167	        500: {"description": "Unexpected service error"},
   168	    },
   169	)
   170	async def cancel_auto_renew(
   171	    current_account: Account = Depends(get_current_account),
   172	    billing_service: BillingService = Depends(get_billing_service),
   173	) -> SubscriptionDTO:
   174	    """
   175	    Disable automatic renewal for the customer's active subscription. Idempotent.
   176	    """
   177	    logger.info("Disabling auto renewal for customer subscription.")
   178	    return await billing_service.cancel_auto_renew(current_account.id)
   179	
   180	
   181	@router.post(
   182	    "/reactivate",
   183	    summary="Reactivate automatic renewal for active subscription",
   184	    response_model=SubscriptionDTO,
   185	    status_code=status.HTTP_200_OK,
   186	    responses={
   187	        400: {"description": "Subscription cancelled or invalid state"},
   188	        401: {"description": "Authentication required"},
   189	        404: {"description": "No active subscription found"},
   190	        500: {"description": "Unexpected service error"},
   191	    },
   192	)
   193	async def reactivate_subscription(
   194	    current_account: Account = Depends(get_current_account),
   195	    billing_service: BillingService = Depends(get_billing_service),
   196	) -> SubscriptionDTO:
   197	    """
   198	    Enable automatic renewal for the customer's active subscription. Idempotent.
   199	    """
   200	    logger.info("Reactivating auto renewal for customer subscription.")
   201	    return await billing_service.reactivate_auto_renew(current_account.id)

```


**Tool Call: Read file `billing-server\app\models\subscription.py`**
Status: Completed

```OverREALITY/billing-server/app/models/subscription.py
     1	"""
     2	subscription.py — Subscription entity representing account billing subscription contracts.
     3	"""
     4	from __future__ import annotations
     5	
     6	import uuid
     7	from datetime import datetime
     8	from typing import TYPE_CHECKING
     9	from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, String, text
    10	from sqlalchemy.orm import Mapped, mapped_column, relationship
    11	from sqlalchemy.types import Uuid
    12	
    13	from app.database import Base
    14	from app.models.base import SubscriptionLifecycleStatus, TimestampMixin
    15	
    16	if TYPE_CHECKING:
    17	    from app.models.account import Account
    18	
    19	
    20	class Subscription(Base, TimestampMixin):
    21	    """
    22	    Subscriptions table (Phase 2.1).
    23	    Stores independent subscription lifecycle state, plan association, timestamps, and renewal status.
    24	    Never stores payment gateway tokens or credit card data.
    25	    """
    26	    __tablename__ = "subscriptions"
    27	
    28	    id: Mapped[uuid.UUID] = mapped_column(
    29	        Uuid(as_uuid=True),
    30	        primary_key=True,
    31	        default=uuid.uuid4,
    32	        server_default=text("gen_random_uuid()"),
    33	    )
    34	    account_id: Mapped[uuid.UUID] = mapped_column(
    35	        Uuid(as_uuid=True),
    36	        ForeignKey("accounts.id", ondelete="CASCADE"),
    37	        nullable=False,
    38	        index=True,
    39	    )
    40	    plan_id: Mapped[str] = mapped_column(
    41	        String(32),
    42	        nullable=False,
    43	        index=True,
    44	        default="free",
    45	        server_default="free",
    46	    )
    47	    status: Mapped[SubscriptionLifecycleStatus] = mapped_column(
    48	        SQLEnum(
    49	            SubscriptionLifecycleStatus,
    50	            name="subscription_lifecycle_status",
    51	            create_constraint=True,
    52	            native_enum=True,
    53	        ),
    54	        default=SubscriptionLifecycleStatus.ACTIVE,
    55	        nullable=False,
    56	        index=True,
    57	    )
    58	    starts_at: Mapped[datetime] = mapped_column(
    59	        DateTime(timezone=True),
    60	        nullable=False,
    61	    )
    62	    expires_at: Mapped[datetime] = mapped_column(
    63	        DateTime(timezone=True),
    64	        nullable=False,
    65	        index=True,
    66	    )
    67	    grace_expires_at: Mapped[datetime | None] = mapped_column(
    68	        DateTime(timezone=True),
    69	        nullable=True,
    70	    )
    71	    auto_renew: Mapped[bool] = mapped_column(
    72	        Boolean(),
    73	        default=True,
    74	        server_default="true",
    75	        nullable=False,
    76	    )
    77	
    78	    # Relationships
    79	    account: Mapped[Account] = relationship(
    80	        "Account",
    81	        back_populates="subscriptions",
    82	    )
    83	
    84	    def __repr__(self) -> str:
    85	        return f"<Subscription(id={self.id}, account_id={self.account_id}, plan_id={self.plan_id}, status={self.status})>"

```


**Tool Call: Read file `billing-server\app\repositories\subscription_repository.py`**
Status: Completed

```OverREALITY/billing-server/app/repositories/subscription_repository.py
     1	"""
     2	subscription_repository.py — Persistence layer for Subscription entities (Phase 2.1).
     3	"""
     4	from __future__ import annotations
     5	
     6	import uuid
     7	from datetime import datetime
     8	from sqlalchemy import select, or_, and_, func
     9	from sqlalchemy.exc import SQLAlchemyError
    10	
    11	from sqlalchemy.ext.asyncio import AsyncSession
    12	
    13	from app.exceptions import DatabaseOperationError
    14	from app.models import Subscription, SubscriptionLifecycleStatus
    15	from app.repositories.base import BaseRepository
    16	
    17	
    18	class SubscriptionRepository(BaseRepository[Subscription]):
    19	    """
    20	    Repository for Subscription model queries and CRUD operations.
    21	    Manages subscription lifecycle persistence and active contract lookups.
    22	    """
    23	
    24	    def __init__(self, session: AsyncSession) -> None:
    25	        super().__init__(Subscription, session)
    26	
    27	    async def get_by_account_id(self, account_id: uuid.UUID) -> list[Subscription]:
    28	        """
    29	        List all subscriptions for an account, ordered by creation time descending.
    30	        """
    31	        try:
    32	            stmt = (
    33	                select(Subscription)
    34	                .where(Subscription.account_id == account_id)
    35	                .order_by(Subscription.created_at.desc())
    36	            )
    37	            result = await self.session.execute(stmt)
    38	            return list(result.scalars().all())
    39	        except SQLAlchemyError as exc:
    40	            raise DatabaseOperationError(
    41	                "Database error querying subscriptions for account"
    42	            ) from exc
    43	
    44	    async def get_active_for_account(
    45	        self, account_id: uuid.UUID, now: datetime, *, for_update: bool = False
    46	    ) -> Subscription | None:
    47	        """
    48	        Retrieve the current active, trial, or unexpired grace subscription for an account.
    49	        If for_update=True, acquires row-level exclusive lock (SELECT ... FOR UPDATE).
    50	        """
    51	        try:
    52	            stmt = (
    53	                select(Subscription)
    54	                .where(Subscription.account_id == account_id)
    55	                .where(
    56	                    Subscription.status.in_([
    57	                        SubscriptionLifecycleStatus.TRIAL,
    58	                        SubscriptionLifecycleStatus.ACTIVE,
    59	                        SubscriptionLifecycleStatus.GRACE,
    60	                    ])
    61	                )
    62	                .where(
    63	                    or_(
    64	                        Subscription.expires_at > now,
    65	                        and_(
    66	                            Subscription.status == SubscriptionLifecycleStatus.GRACE,
    67	                            Subscription.grace_expires_at.is_not(None),
    68	                            Subscription.grace_expires_at > now,
    69	                        ),
    70	                    )
    71	                )
    72	                .order_by(Subscription.created_at.desc())
    73	            )
    74	            if for_update:
    75	                stmt = stmt.with_for_update()
    76	            result = await self.session.execute(stmt)
    77	            return result.scalars().first()
    78	        except SQLAlchemyError as exc:
    79	            raise DatabaseOperationError(
    80	                "Database error querying active subscription for account"
    81	            ) from exc
    82	
    83	    async def get_expired_active_subscriptions(
    84	        self, now: datetime, *, for_update: bool = False
    85	    ) -> list[Subscription]:
    86	        """
    87	        Retrieve all active subscriptions whose expiration timestamp has passed.
    88	        If for_update=True, acquires row-level exclusive lock (SELECT ... FOR UPDATE).
    89	        """
    90	        try:
    91	            stmt = (
    92	                select(Subscription)
    93	                .where(Subscription.status == SubscriptionLifecycleStatus.ACTIVE)
    94	                .where(Subscription.expires_at <= now)
    95	            )
    96	            if for_update:
    97	                stmt = stmt.with_for_update()
    98	            result = await self.session.execute(stmt)
    99	            return list(result.scalars().all())
   100	        except SQLAlchemyError as exc:
   101	            raise DatabaseOperationError(
   102	                "Database error querying expired active subscriptions"
   103	            ) from exc
   104	
   105	    async def get_expired_grace_subscriptions(
   106	        self, now: datetime, *, for_update: bool = False
   107	    ) -> list[Subscription]:
   108	        """
   109	        Retrieve all grace subscriptions whose grace period timestamp has elapsed.
   110	        If for_update=True, acquires row-level exclusive lock (SELECT ... FOR UPDATE).
   111	        """
   112	        try:
   113	            stmt = (
   114	                select(Subscription)
   115	                .where(Subscription.status == SubscriptionLifecycleStatus.GRACE)
   116	                .where(Subscription.grace_expires_at.is_not(None))
   117	                .where(Subscription.grace_expires_at <= now)
   118	            )
   119	            if for_update:
   120	                stmt = stmt.with_for_update()
   121	            result = await self.session.execute(stmt)
   122	            return list(result.scalars().all())
   123	        except SQLAlchemyError as exc:
   124	            raise DatabaseOperationError(
   125	                "Database error querying expired grace subscriptions"
   126	            ) from exc
   127	
   128	    async def list_all_paginated(
   129	        self,
   130	        limit: int = 50,
   131	        offset: int = 0,
   132	        status: SubscriptionLifecycleStatus | None = None,
   133	    ) -> list[Subscription]:
   134	        """
   135	        Retrieve a paginated list of all subscriptions across all accounts.
   136	        Optionally filter by lifecycle status.
   137	        """
   138	        try:
   139	            stmt = select(Subscription).order_by(Subscription.created_at.desc()).limit(limit).offset(offset)
   140	            if status is not None:
   141	                stmt = stmt.where(Subscription.status == status)
   142	            result = await self.session.execute(stmt)
   143	            return list(result.scalars().all())
   144	        except SQLAlchemyError as exc:
   145	            raise DatabaseOperationError(
   146	                "Database error querying paginated subscriptions"
   147	            ) from exc
   148	
   149	    async def count_all(self, status: SubscriptionLifecycleStatus | None = None) -> int:
   150	        """
   151	        Count total subscriptions across all accounts, optionally filtered by lifecycle status.
   152	        """
   153	        try:
   154	            stmt = select(func.count()).select_from(Subscription)
   155	            if status is not None:
   156	                stmt = stmt.where(Subscription.status == status)
   157	            result = await self.session.execute(stmt)
   158	            return int(result.scalar_one() or 0)
   159	        except SQLAlchemyError as exc:
   160	            raise DatabaseOperationError(
   161	                "Database error counting subscriptions"
   162	            ) from exc
   163	
   164	

```


## Assistant

<thinking>
There's no unique constraint protecting against duplicate active subscriptions at the database level, which means the `confirm_payment` function has a real race condition—two concurrent confirmations for the same account could both check for existing active subscriptions, find none, and create duplicates before either transaction commits.

The likelihood depends on specific scenarios like duplicate webhook retries from Razorpay hitting the system simultaneously, but it's a legitimate billing correctness issue worth flagging as Medium/High severity since it could cause double-extending validity or subscription miscounts, even if it doesn't directly impact security.

Now I need to examine the `purchase_subscription` method in billing_service.py to determine whether the subscription price and amount are validated server-side or derived from the client request.
</thinking>

**Tool Call: Read file `billing-server\app\services\billing_service.py`**
Status: Completed

```OverREALITY/billing-server/app/services/billing_service.py
     1	"""
     2	billing_service.py — BillingService orchestration layer for Customer Billing API (Phase 2.7).
     3	
     4	Strictly enforces architectural boundaries:
     5	- Bridges domain services (SubscriptionService, PaymentService, SubscriptionPlanService) and customer routers.
     6	- Converts internal domain models into secure customer DTOs.
     7	- Never leaks internal database UUIDs (account.id, payment.id, subscription.id) or provider secrets.
     8	- Performs zero database repository queries directly; relies exclusively on domain services.
     9	"""
    10	from __future__ import annotations
    11	
    12	import logging
    13	import uuid
    14	from typing import Any
    15	
    16	from app.models.account import Account
    17	from app.models.payment import Payment
    18	from app.models.subscription import Subscription
    19	from app.services.payment.service import PaymentService
    20	from app.services.subscription_service import SubscriptionService
    21	from app.services.subscription_plan import SubscriptionPlanService
    22	from app.services.billing_dtos import (
    23	    SubscriptionDTO,
    24	    PlanDTO,
    25	    PaymentDTO,
    26	    PaymentListDTO,
    27	    PurchaseRequestDTO,
    28	    PurchaseResponseDTO,
    29	)
    30	
    31	logger = logging.getLogger(__name__)
    32	
    33	
    34	class BillingService:
    35	    """
    36	    Orchestration service for customer billing views and actions.
    37	    Decoupled from routers and databases.
    38	    """
    39	
    40	    def __init__(
    41	        self,
    42	        subscription_service: SubscriptionService,
    43	        payment_service: PaymentService,
    44	        plan_service: SubscriptionPlanService,
    45	    ) -> None:
    46	        self.subscription_service = subscription_service
    47	        self.payment_service = payment_service
    48	        self.plan_service = plan_service
    49	
    50	    async def get_customer_subscription(self, account_id: uuid.UUID) -> SubscriptionDTO:
    51	        """
    52	        Retrieve customer view of their current active subscription.
    53	        If none exists, returns a clean DTO with lifecycle_status='NONE' without throwing 404 or 500.
    54	        """
    55	        sub = await self.subscription_service.get_active_subscription(account_id)
    56	        if not sub:
    57	            logger.info("Account %s has no active subscription; returning clean default DTO", account_id)
    58	            return SubscriptionDTO(
    59	                plan="none",
    60	                lifecycle_status="NONE",
    61	                started_at=None,
    62	                expires_at=None,
    63	                grace_until=None,
    64	                auto_renew=False,
    65	            )
    66	
    67	        return SubscriptionDTO(
    68	            plan=sub.plan_id,
    69	            lifecycle_status=sub.status.value,
    70	            started_at=sub.starts_at,
    71	            expires_at=sub.expires_at,
    72	            grace_until=sub.grace_expires_at,
    73	            auto_renew=sub.auto_renew,
    74	        )
    75	
    76	    def list_plans(self) -> list[PlanDTO]:
    77	        """
    78	        Return available subscription plans from the code-defined registry.
    79	        Requires zero database queries.
    80	        """
    81	        plans = self.plan_service.list_plans()
    82	        return [
    83	            PlanDTO(
    84	                plan_id=p.plan_id,
    85	                name=p.display_name,
    86	                price=p.price_minor_units,
    87	                currency=p.currency,
    88	                max_devices=p.max_devices,
    89	
    90	                max_concurrent_ips=p.max_concurrent_ips,
    91	                quota=p.data_quota_bytes,
    92	            )
    93	            for p in plans
    94	        ]
    95	
    96	    def _map_payment_dto(self, payment: Payment) -> PaymentDTO:
    97	        """
    98	        Map Payment entity to PaymentDTO.
    99	        Uses provider_order_id as the primary public payment_id to prevent leaking DB UUIDs.
   100	        If provider_order_id is missing, falls back to provider_payment_id or stringified UUID.
   101	        """
   102	        public_id = payment.provider_order_id or payment.provider_payment_id or str(payment.id)
   103	        return PaymentDTO(
   104	            payment_id=public_id,
   105	            provider=payment.provider.value,
   106	            amount=payment.amount_minor_units,
   107	            currency=payment.currency,
   108	            status=payment.status.value,
   109	            created_at=payment.created_at,
   110	        )
   111	
   112	    async def list_customer_payments(
   113	        self, account_id: uuid.UUID, limit: int = 20, offset: int = 0
   114	    ) -> PaymentListDTO:
   115	        """
   116	        Retrieve paginated payment history for an account, ordered newest first.
   117	        """
   118	        payments, total = await self.payment_service.list_account_payments(account_id, limit, offset)
   119	        dto_list = [self._map_payment_dto(p) for p in payments]
   120	        return PaymentListDTO(
   121	            payments=dto_list,
   122	            total=total,
   123	            limit=min(max(1, limit), 100),
   124	            offset=max(0, offset),
   125	        )
   126	
   127	    async def get_customer_payment(
   128	        self, account_id: uuid.UUID, payment_identifier: str
   129	    ) -> PaymentDTO:
   130	        """
   131	        Retrieve a specific payment by identifier. Enforces Anti-IDOR via domain service.
   132	        """
   133	        payment = await self.payment_service.get_account_payment(account_id, payment_identifier)
   134	        return self._map_payment_dto(payment)
   135	
   136	    async def purchase_subscription(
   137	        self, account_id: uuid.UUID, request: PurchaseRequestDTO
   138	    ) -> PurchaseResponseDTO:
   139	        """
   140	        Initiate an order for a subscription purchase via PaymentService.
   141	        Does NOT activate the subscription; activation occurs exclusively via verified webhooks.
   142	        """
   143	        plan = self.plan_service.get_plan(request.plan_id)
   144	        amount_minor_units = request.amount if request.amount is not None else plan.price_minor_units
   145	
   146	        payment = await self.payment_service.create_payment(
   147	
   148	            account_id=account_id,
   149	            amount_minor_units=amount_minor_units,
   150	            currency=request.currency,
   151	            idempotency_key=request.idempotency_key,
   152	            plan_id=request.plan_id,
   153	        )
   154	
   155	        public_id = payment.provider_order_id or payment.provider_payment_id or str(payment.id)
   156	        return PurchaseResponseDTO(
   157	            payment_id=public_id,
   158	            provider=payment.provider.value,
   159	            amount=payment.amount_minor_units,
   160	            currency=payment.currency,
   161	            status=payment.status.value,
   162	            created_at=payment.created_at,
   163	        )
   164	
   165	    async def cancel_auto_renew(self, account_id: uuid.UUID) -> SubscriptionDTO:
   166	        """
   167	        Disable automatic renewal for the customer's active subscription. Idempotent.
   168	        """
   169	        sub = await self.subscription_service.update_auto_renew(account_id, auto_renew=False)
   170	        return SubscriptionDTO(
   171	            plan=sub.plan_id,
   172	            lifecycle_status=sub.status.value,
   173	            started_at=sub.starts_at,
   174	            expires_at=sub.expires_at,
   175	            grace_until=sub.grace_expires_at,
   176	            auto_renew=sub.auto_renew,
   177	        )
   178	
   179	    async def reactivate_auto_renew(self, account_id: uuid.UUID) -> SubscriptionDTO:
   180	        """
   181	        Enable automatic renewal for the customer's active subscription. Idempotent.
   182	        """
   183	        sub = await self.subscription_service.update_auto_renew(account_id, auto_renew=True)
   184	        return SubscriptionDTO(
   185	            plan=sub.plan_id,
   186	            lifecycle_status=sub.status.value,
   187	            started_at=sub.starts_at,
   188	            expires_at=sub.expires_at,
   189	            grace_until=sub.grace_expires_at,
   190	            auto_renew=sub.auto_renew,
   191	        )

```


**Tool Call: Read file `billing-server\app\services\billing_dtos.py`**
Status: Completed

```OverREALITY/billing-server/app/services/billing_dtos.py
     1	"""
     2	billing_dtos.py — Dedicated Pydantic Data Transfer Objects for Customer Billing API (Phase 2.7).
     3	
     4	SECURITY CONTRACT:
     5	- Never exposes internal SQLAlchemy models or primary key UUIDs (account.id, payment.id, subscription.id).
     6	- Never exposes provider secrets, raw signature payloads, or admin hashes.
     7	- Exposes only human-readable identifiers and timestamps.
     8	"""
     9	from __future__ import annotations
    10	
    11	from datetime import datetime
    12	from pydantic import BaseModel, Field
    13	
    14	
    15	class SubscriptionDTO(BaseModel):
    16	    """
    17	    Customer view of their subscription entitlement.
    18	    When no subscription exists, clean default values (e.g. status='NONE') are returned.
    19	    """
    20	    plan: str = Field(description="Subscription plan identifier (e.g. 'pro', 'free', or 'none')")
    21	    lifecycle_status: str = Field(description="Current lifecycle status (e.g. 'ACTIVE', 'GRACE', 'EXPIRED', 'NONE')")
    22	    started_at: datetime | None = Field(default=None, description="Subscription start timestamp (UTC)")
    23	    expires_at: datetime | None = Field(default=None, description="Subscription expiry timestamp (UTC)")
    24	    grace_until: datetime | None = Field(default=None, description="Grace period expiry timestamp (UTC) if in GRACE")
    25	    auto_renew: bool = Field(default=False, description="Whether automatic renewal is enabled")
    26	
    27	    model_config = {"from_attributes": True}
    28	
    29	
    30	class PlanDTO(BaseModel):
    31	    """
    32	    Customer view of an available subscription plan from the registry.
    33	    """
    34	    plan_id: str = Field(description="Unique plan identifier (e.g. 'free', 'pro', 'family')")
    35	    name: str = Field(description="Display name of the plan")
    36	    price: int = Field(description="Price in minor units (e.g. paise or cents)")
    37	    currency: str = Field(default="INR", description="3-letter currency code")
    38	    max_devices: int = Field(description="Maximum registered devices allowed")
    39	
    40	    max_concurrent_ips: int = Field(description="Maximum concurrent VPN connections allowed")
    41	    quota: int = Field(description="Data traffic quota in bytes")
    42	
    43	    model_config = {"from_attributes": True}
    44	
    45	
    46	class PaymentDTO(BaseModel):
    47	    """
    48	    Customer view of a payment transaction.
    49	    payment_id is the gateway order or payment ID, never an internal database UUID.
    50	    """
    51	    payment_id: str = Field(description="Provider order ID or payment ID")
    52	    provider: str = Field(description="Payment gateway provider (e.g. 'RAZORPAY')")
    53	    amount: int = Field(description="Payment amount in minor units")
    54	    currency: str = Field(description="3-letter currency code (e.g. 'INR')")
    55	    status: str = Field(description="Payment lifecycle status (e.g. 'CREATED', 'PAID', 'FAILED')")
    56	    created_at: datetime = Field(description="Transaction creation timestamp (UTC)")
    57	
    58	    model_config = {"from_attributes": True}
    59	
    60	
    61	class PaymentListDTO(BaseModel):
    62	    """
    63	    Paginated list of payment history items.
    64	    """
    65	    payments: list[PaymentDTO] = Field(description="List of payment transactions")
    66	    total: int = Field(description="Total number of payments matching the query")
    67	    limit: int = Field(description="Maximum number of items returned")
    68	    offset: int = Field(description="Number of items skipped")
    69	
    70	    model_config = {"from_attributes": True}
    71	
    72	
    73	class PurchaseRequestDTO(BaseModel):
    74	    """
    75	    Request payload to initiate a new subscription purchase order.
    76	    """
    77	    plan_id: str = Field(default="pro", description="Plan identifier to purchase")
    78	    idempotency_key: str = Field(min_length=8, max_length=64, description="Unique idempotency key to prevent duplicate orders")
    79	    amount: int | None = Field(default=None, description="Optional custom amount in minor units; defaults to plan price if omitted")
    80	    currency: str = Field(default="INR", min_length=3, max_length=3, description="Currency code")
    81	
    82	
    83	class PurchaseResponseDTO(BaseModel):
    84	    """
    85	    Response payload returned upon order creation.
    86	    Does NOT activate subscription; activation happens exclusively via webhooks.
    87	    """
    88	    payment_id: str = Field(description="Gateway order ID required by client checkout SDK")
    89	    provider: str = Field(description="Payment gateway provider")
    90	    amount: int = Field(description="Order amount in minor units")
    91	    currency: str = Field(description="Currency code")
    92	    status: str = Field(description="Order status")
    93	    created_at: datetime = Field(description="Order creation timestamp (UTC)")
    94	
    95	    model_config = {"from_attributes": True}

```


## Assistant

<thinking>
I've spotted a critical vulnerability in the billing system. The `PurchaseRequestDTO.amount` field is optional and client-controlled, but when provided, it bypasses the plan's actual price and gets used directly in the purchase logic. This means a malicious customer could call the purchase endpoint with any amount they want, completely overriding what they should actually be charged.

The attack is straightforward: request the "pro" plan but specify `amount: 100` (₹1) instead of the correct price (₹999). The server creates a Razorpay order for that attacker-controlled amount, the customer pays just ₹1, and the webhook confirmation doesn't validate that the payment amount matches the plan price — it only checks that payment was authorized, then activates the full subscription regardless of what was actually paid. This is a classic e-commerce price-tampering vulnerability that needs to be flagged as Critical and blocks production.

The fix is straightforward: remove the `amount` field from the request entirely and always derive the charge amount strictly from the plan's price server-side. As a defense-in-depth measure, the payment confirmation should also verify that the captured amount matches what was expected. I need to check if there's any server-side validation I might have missed that would prevent this, but from reading the purchase function, there's no such check in place.

Let me verify the billing DTOs don't have any Pydantic validators that would constrain the amount field, and then check the test suite to see if there's a test that reveals the intended behavior here.
</thinking>

**Tool Call: Search files for regex `amount`**
Status: Completed

file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_billing_api.py#L47-51

```
    provider.create_order.return_value = PaymentOrderDTO(
        provider_order_id="order_test_123456",
        amount_minor_units=49900,
        currency="INR",
    )
```


file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_billing_api.py#L140-148

```
    p1 = await pay_repo.create(
        account_id=acc.id,
        provider=PaymentProviderType.RAZORPAY,
        amount_minor_units=49900,
        currency="INR",
        status=PaymentStatus.CREATED,
        provider_order_id="order_test_100",
        idempotency_key="key_100",
    )
```


file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_billing_api.py#L149-157

```
    p2 = await pay_repo.create(
        account_id=acc.id,
        provider=PaymentProviderType.RAZORPAY,
        amount_minor_units=49900,
        currency="INR",
        status=PaymentStatus.CREATED,
        provider_order_id="order_test_200",
        idempotency_key="key_200",
    )
```


file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_billing_api.py#L171-175

```
    pay_data = get_resp.json()
    assert pay_data["payment_id"] == "order_test_100"
    assert pay_data["amount"] == 49900
    assert pay_data["status"] == "CREATED"

```


file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_billing_api.py#L192-200

```
    await pay_repo.create(
        account_id=acc_a.id,
        provider=PaymentProviderType.RAZORPAY,
        amount_minor_units=49900,
        currency="INR",
        status=PaymentStatus.CREATED,
        provider_order_id="order_secret_a",
        idempotency_key="key_secret_a",
    )
```


file://D:\My projects\VPN\OverREALITY\billing-server\tests\routers\test_billing_api.py#L214-224

```
    """POST /api/billing/purchase initiates order via payment gateway and returns order details."""
    headers, _ = await get_auth_headers(client_with_mock_provider, account_factory, "RT-PUR-1")
    req_data = {
        "plan_id": "pro",
        "idempotency_key": "idem_purchase_001",
    }
    resp = await client_with_mock_provider.post("/api/billing/purchase", json=req_data, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["payment_id"] == "order_test_123456"
    assert data["amount"] == 49900
```


## Assistant

<thinking>
So I've confirmed there's no test coverage for the amount override—it's a genuine critical vulnerability where the "amount" field can be manipulated without any validation. This is a well-documented finding with specific file and line references. Now I'm moving on to check subscription_service.py for lifecycle locking issues, then I'll delegate the remaining areas like provisioning, database concurrency concerns across repos and the scheduler, lifecycle job service, Docker and CI setup, and security considerations.

Let me start by examining subscription_service.py directly since it's central to the payment system and connects to what I've already found.
</thinking>

**Tool Call: Read file `billing-server\app\services\subscription_service.py`**
Status: Completed

```OverREALITY/billing-server/app/services/subscription_service.py
     1	"""
     2	subscription_service.py — Domain service for managing subscription contracts and lifecycle transitions (Phase 2.1).
     3	"""
     4	from __future__ import annotations
     5	
     6	import logging
     7	import uuid
     8	from typing import Any
     9	from datetime import datetime, timedelta, timezone
    10	from sqlalchemy.ext.asyncio import AsyncSession
    11	
    12	from app.exceptions import EntityNotFoundError, DatabaseOperationError
    13	from app.models import Subscription, SubscriptionLifecycleStatus
    14	from app.models.subscription_plan import PLANS_REGISTRY
    15	from app.repositories import AccountRepository, SubscriptionRepository
    16	from app.services.exceptions import (
    17	    UnknownPlanError,
    18	    SubscriptionNotFoundError,
    19	    InvalidSubscriptionStateError,
    20	    SubscriptionAlreadyActiveError,
    21	)
    22	
    23	logger = logging.getLogger(__name__)
    24	
    25	
    26	class SubscriptionService:
    27	    """
    28	    Pure domain service responsible for subscription creation, renewal, cancellation,
    29	    and lifecycle transitions. Independent of HTTP and framework layers.
    30	    """
    31	
    32	    def __init__(self, session: AsyncSession, provisioning_service: Any | None = None) -> None:
    33	        self.session = session
    34	        self.provisioning_service = provisioning_service
    35	        self.repository = SubscriptionRepository(session)
    36	        self.account_repo = AccountRepository(session)
    37	
    38	    async def create_subscription(
    39	        self,
    40	        account_id: uuid.UUID,
    41	        plan_id: str,
    42	        starts_at: datetime,
    43	        expires_at: datetime,
    44	        *,
    45	        auto_renew: bool = True,
    46	        status: SubscriptionLifecycleStatus = SubscriptionLifecycleStatus.ACTIVE,
    47	        commit: bool = True,
    48	    ) -> Subscription:
    49	        """
    50	        Create a new subscription contract for an account.
    51	        Validates account existence, plan validity, and verifies no conflicting active subscription exists.
    52	        """
    53	        account = await self.account_repo.get_by_id(account_id)
    54	        if not account:
    55	            raise EntityNotFoundError(f"Account with ID {account_id} not found.")
    56	
    57	        clean_plan_id = (plan_id or "").strip().lower()
    58	        if clean_plan_id not in PLANS_REGISTRY:
    59	            raise UnknownPlanError(f"Unknown subscription plan ID: '{clean_plan_id}'")
    60	
    61	        now = datetime.now(timezone.utc)
    62	        existing_active = await self.repository.get_active_for_account(account_id, now, for_update=True)
    63	        if existing_active:
    64	            raise SubscriptionAlreadyActiveError(
    65	                f"Account {account_id} already has an active subscription (id={existing_active.id})."
    66	            )
    67	
    68	        subscription = await self.repository.create(
    69	            account_id=account_id,
    70	            plan_id=clean_plan_id,
    71	            status=status,
    72	            starts_at=starts_at,
    73	            expires_at=expires_at,
    74	            auto_renew=auto_renew,
    75	            commit=commit,
    76	        )
    77	        logger.info("Created new subscription id=%s for plan=%s status=%s", subscription.id, clean_plan_id, status.value)
    78	        if self.provisioning_service and status == SubscriptionLifecycleStatus.ACTIVE:
    79	            await self.provisioning_service.provision_subscription(account_id, clean_plan_id, expires_at, commit=commit)
    80	        return subscription
    81	
    82	    async def activate_subscription(self, subscription_id: uuid.UUID, *, commit: bool = True) -> Subscription:
    83	        """
    84	        Activate a pending, trial, or grace subscription.
    85	        Idempotent if already ACTIVE. Blocks activation of CANCELLED or EXPIRED subscriptions.
    86	        """
    87	        sub = await self.repository.get_by_id(subscription_id, for_update=True)
    88	        if not sub:
    89	            raise SubscriptionNotFoundError(f"Subscription {subscription_id} not found.")
    90	
    91	        if sub.status == SubscriptionLifecycleStatus.CANCELLED:
    92	            raise InvalidSubscriptionStateError("Cannot activate a cancelled subscription.")
    93	        if sub.status == SubscriptionLifecycleStatus.EXPIRED:
    94	            raise InvalidSubscriptionStateError("Cannot activate an expired subscription.")
    95	        if sub.status == SubscriptionLifecycleStatus.ACTIVE:
    96	            return sub
    97	
    98	        sub.status = SubscriptionLifecycleStatus.ACTIVE
    99	        sub.grace_expires_at = None
   100	        await self.repository.update(sub, commit=commit)
   101	        logger.info("Activated subscription id=%s", sub.id)
   102	        if self.provisioning_service:
   103	            await self.provisioning_service.provision_subscription(sub.account_id, sub.plan_id, sub.expires_at, commit=commit)
   104	        return sub
   105	
   106	    async def renew_subscription(self, subscription_id: uuid.UUID, new_expires_at: datetime, *, commit: bool = True) -> Subscription:
   107	        """
   108	        Renew an existing subscription by extending its expiration date and resetting status to ACTIVE.
   109	        Blocks renewal of CANCELLED subscriptions.
   110	        """
   111	        sub = await self.repository.get_by_id(subscription_id, for_update=True)
   112	        if not sub:
   113	            raise SubscriptionNotFoundError(f"Subscription {subscription_id} not found.")
   114	
   115	        if sub.status == SubscriptionLifecycleStatus.CANCELLED:
   116	            raise InvalidSubscriptionStateError("Cannot renew a cancelled subscription.")
   117	
   118	        sub.expires_at = new_expires_at
   119	        sub.status = SubscriptionLifecycleStatus.ACTIVE
   120	        sub.grace_expires_at = None
   121	        await self.repository.update(sub, commit=commit)
   122	        logger.info("Renewed subscription id=%s until %s", sub.id, new_expires_at.isoformat())
   123	        if self.provisioning_service:
   124	            await self.provisioning_service.extend_subscription(sub.account_id, new_expires_at, commit=commit)
   125	        return sub
   126	
   127	    async def cancel_subscription(self, subscription_id: uuid.UUID, *, commit: bool = True) -> Subscription:
   128	        """
   129	        Cancel a subscription and disable auto-renewal.
   130	        Idempotent if already CANCELLED.
   131	        """
   132	        sub = await self.repository.get_by_id(subscription_id, for_update=True)
   133	        if not sub:
   134	            raise SubscriptionNotFoundError(f"Subscription {subscription_id} not found.")
   135	
   136	        if sub.status == SubscriptionLifecycleStatus.CANCELLED:
   137	            return sub
   138	
   139	        sub.status = SubscriptionLifecycleStatus.CANCELLED
   140	        sub.auto_renew = False
   141	        await self.repository.update(sub, commit=commit)
   142	        logger.info("Cancelled subscription id=%s", sub.id)
   143	        if self.provisioning_service:
   144	            await self.provisioning_service.suspend_subscription(sub.account_id, commit=commit)
   145	        return sub
   146	
   147	    async def enter_grace_period(self, subscription_id: uuid.UUID, grace_duration_days: int = 7, *, commit: bool = True) -> Subscription:
   148	        """
   149	        Transition an ACTIVE subscription into a GRACE period after payment failure or renewal warning.
   150	        Requires the subscription to be currently ACTIVE with auto_renew enabled.
   151	        """
   152	        sub = await self.repository.get_by_id(subscription_id, for_update=True)
   153	        if not sub:
   154	            raise SubscriptionNotFoundError(f"Subscription {subscription_id} not found.")
   155	
   156	        if sub.status != SubscriptionLifecycleStatus.ACTIVE:
   157	            raise InvalidSubscriptionStateError(
   158	                f"Cannot enter grace period from status '{sub.status.value}'; must be ACTIVE."
   159	            )
   160	        if not sub.auto_renew:
   161	            raise InvalidSubscriptionStateError("Cannot enter grace period when auto-renew is disabled.")
   162	
   163	        now = datetime.now(timezone.utc)
   164	        sub.status = SubscriptionLifecycleStatus.GRACE
   165	        sub.grace_expires_at = now + timedelta(days=grace_duration_days)
   166	        await self.repository.update(sub, commit=commit)
   167	        logger.info("Subscription id=%s entered grace period until %s", sub.id, sub.grace_expires_at.isoformat())
   168	        return sub
   169	
   170	    async def expire_subscription(self, subscription_id: uuid.UUID, *, commit: bool = True) -> Subscription:
   171	        """
   172	        Mark a subscription as EXPIRED when it reaches end of term or grace period without renewal.
   173	        Cannot expire a CANCELLED subscription.
   174	        """
   175	        sub = await self.repository.get_by_id(subscription_id, for_update=True)
   176	        if not sub:
   177	            raise SubscriptionNotFoundError(f"Subscription {subscription_id} not found.")
   178	
   179	        if sub.status == SubscriptionLifecycleStatus.CANCELLED:
   180	            raise InvalidSubscriptionStateError("Cannot expire an already cancelled subscription.")
   181	
   182	        sub.status = SubscriptionLifecycleStatus.EXPIRED
   183	        await self.repository.update(sub, commit=commit)
   184	        logger.info("Expired subscription id=%s", sub.id)
   185	        if self.provisioning_service:
   186	            await self.provisioning_service.suspend_subscription(sub.account_id, commit=commit)
   187	        return sub
   188	
   189	    async def get_active_subscription(self, account_id: uuid.UUID) -> Subscription | None:
   190	        """
   191	        Retrieve the current active, trial, or unexpired grace subscription for an account.
   192	        """
   193	        now = datetime.now(timezone.utc)
   194	        return await self.repository.get_active_for_account(account_id, now)
   195	
   196	    async def update_auto_renew(self, account_id: uuid.UUID, auto_renew: bool, *, commit: bool = True) -> Subscription:
   197	        """
   198	        Update auto_renew status for an account's active subscription.
   199	        Idempotent: returns cleanly without DB writes if already set to requested state.
   200	        """
   201	        now = datetime.now(timezone.utc)
   202	        sub = await self.repository.get_active_for_account(account_id, now, for_update=True)
   203	        if not sub:
   204	            raise SubscriptionNotFoundError("No active subscription found for account.")
   205	
   206	        if sub.status == SubscriptionLifecycleStatus.CANCELLED:
   207	            raise InvalidSubscriptionStateError("Cannot update auto-renew on a cancelled subscription.")
   208	
   209	        if sub.auto_renew == auto_renew:
   210	            logger.info("Subscription id=%s already has auto_renew=%s. Idempotent return.", sub.id, auto_renew)
   211	            return sub
   212	
   213	        sub.auto_renew = auto_renew
   214	        await self.repository.update(sub, commit=commit)
   215	        logger.info("Updated subscription id=%s auto_renew=%s", sub.id, auto_renew)
   216	        return sub
   217	

```


## Assistant

<thinking>
I've found the same race condition in the `create_subscription` function—the existing active subscription check uses SELECT FOR UPDATE, but that doesn't lock rows that don't exist yet, leaving a window where duplicate ACTIVE/TRIAL/GRACE subscriptions can be created for the same account. There's no unique constraint at the database level to prevent this, just an application-level advisory lock that's insufficient. It's a real vulnerability, though the practical impact is moderate since it results in duplicate subscription rows rather than privilege escalation.

Now I'm planning to delegate the remaining work across parallel sub-agents: one for provisioning, credentials, and Marzban integration; another for database concurrency and scheduler issues; and a third for Docker, CI/CD, and security hardening. I'll prepare detailed, self-contained prompts with exact file paths for each.
</thinking>

I now have deep findings on Auth/AuthZ/Payments. Let me delegate the remaining large subsystems (Provisioning/Credentials, Database/Concurrency/Scheduler, and Docker/CI-CD/Security-hardening/Secrets) to parallel sub-agents for thorough, evidence-based review.

**Tool Call: Auditing provisioning & Marzban integration**
Status: Completed

# Security & Correctness Audit — Provisioning / Retry / Scheduler Subsystem

**Scope reviewed (full file reads):** `app/services/provisioning/service.py`, `provider.py`, `marzban.py`; `app/services/credential_service.py`; `app/models/provisioning.py`, `provisioning_retry.py`; `app/repositories/provisioning_repository.py`, `provisioning_retry_repository.py`; `app/scheduler.py`; `app/services/lifecycle_job_service.py`; `app/services/subscription_service.py` (partial, for lock-behavior verification); `app/repositories/base.py`; `Dockerfile`; `docker-compose.prod.yml`; relevant Alembic migrations.

---

## Findings

### HIGH — Stale local `SUSPENDED` state can permanently deny a legitimately reactivated paying customer
- **File/Function:** `app/services/credential_service.py::CredentialService.get_credentials` (lines 168–172), in combination with `app/services/provisioning/service.py::ProvisioningService.reactivate_subscription` (lines 274–305).
- **Root cause:** `reactivate_subscription` calls `self.provider.unsuspend_user(...)` (remote mutation) **before** the local DB commit (line 292). If the process crashes/OOMs/is killed between the remote call succeeding and the commit, the remote Marzban account is `active`, but the local `provisioning_profiles.provisioning_state` row remains `SUSPENDED`.
- `get_credentials` checks **local** `profile.provisioning_state == SUSPENDED` and raises `CredentialAlreadyRevokedError` **before** it ever inspects the live `user_dto.status` fetched from Marzban. The short-circuit on stale local state means the live-remote check that would otherwise "self-heal" this divergence (as it does for the opposite direction, see Safe section) never executes.
- **Attack/failure scenario:** Customer pays → admin/automation calls `restore_credentials` → remote unsuspend succeeds → process crash/redeploy before commit → customer is billed but permanently blocked from `GET /api/credentials*` with HTTP 400 `CredentialAlreadyRevokedError`, indefinitely, until an admin manually calls the `POST /admin/provisioning/{id}/sync` endpoint (`AdminBillingService.sync_provisioning` → `ProvisioningService.synchronize`). No scheduled job performs this reconciliation automatically (see "Needs Verification / Safe" section — no periodic `synchronize()` sweep exists).
- **Severity:** High (customer-facing denial of paid service, silent, requires manual admin intervention).
- **Likelihood:** Low-to-medium — requires a crash/kill exactly in the remote-call-to-commit window (a few ms), but this window exists on every deploy, OOM-kill, or infra hiccup, and is a repeatable class of bug across all provider-mutating methods (see Medium finding below).
- **Fix:** Reorder to commit-first-then-mutate-remote-with-compensation, OR make the read path authoritative on live remote state (fetch `user_dto` before deciding revocation), OR wrap remote+local mutation in a saga: on remote success, retry local commit with backoff before returning; if commit ultimately fails, enqueue a reconciliation task keyed on `remote_user_id` so the next `synchronize()` call (or a new scheduled reconciliation job) corrects it. Minimal fix: in `get_credentials`, always fetch `user_dto` (already done) and prefer the **live** `user_dto.status` over the cached `profile.provisioning_state` when they disagree, and trigger an async `synchronize()` in that case.

### MEDIUM — Remote Marzban mutation always precedes local durable commit; no compensating transaction on crash
- **File/Function:** `app/services/provisioning/service.py` — `provision_subscription` (147–151 before 178–182), `extend_subscription` (211 before 220), `suspend_subscription` (251 before 260), `reactivate_subscription` (282 before 291), `terminate_subscription` (323 before 332), `rotate_user_credentials` (422 before 438).
- **Root cause:** Every state-changing method calls the Marzban provider (`create_user`/`update_user`/`suspend_user`/`unsuspend_user`/`delete_user`/`reset_user_credentials`) first, then commits locally. There is no two-phase-commit, outbox pattern, or compensating rollback of the remote side if the local commit subsequently fails (e.g., DB connection drop, deadlock, or process kill right after the remote call).
- **Impact by operation:**
  - `create_user`: **Self-healing** — usernames are deterministic (`user_{account_id}`), and the code explicitly catches `ProvisioningConflictError` on retry and falls back to `update_user`. Low risk (see Safe section).
  - `suspend_user`/`delete_user`: Both are idempotent remote operations, so a retry after crash converges correctly. Low risk.
  - `unsuspend_user` (reactivate): **Not idempotent from the reader's perspective** because of the credential-service short-circuit described above (High finding).
  - `reset_user_credentials`: **Not idempotent and not safe to retry blindly** — if the remote reset succeeds (issuing a brand-new UUID/keys) but the local commit fails/crashes before persisting `last_sync_at`, the old cached `ProvisionedUserDTO`/links a client may have just fetched are now invalid, and there is no record that a rotation happened. A subsequent retry would call `reset_user_credentials` **again**, invalidating the credentials a second time. This compounds with the scheduler duplicate-execution finding below.
- **Fix:** For non-idempotent remote ops (`reset_user_credentials` in particular), persist a `PENDING_ROTATION` marker (or write-ahead log row) transactionally *before* calling the remote API, then finalize on success and reconcile on next start. At minimum, wrap the whole method in a retryable transaction with `session.begin_nested()`/savepoint and explicit crash-recovery reconciliation on startup (scan for stuck `PENDING` rows older than N minutes).

### MEDIUM — Scheduler has no cross-process/cross-replica locking; `run_credential_rotation_job` can double-rotate credentials under horizontal scaling
- **File/Function:** `app/scheduler.py::JobScheduler.start/_loop_job`; `app/services/lifecycle_job_service.py::run_credential_rotation_job` (lines 225–248) and `run_failed_provision_retry_job` (250–309).
- **Root cause:** `app/main.py` (`lifespan`) unconditionally instantiates and starts a `JobScheduler` in **every** process (line ~80: `scheduler = JobScheduler(AsyncSessionLocal); scheduler.start()`). There is no advisory lock (`pg_advisory_lock`), no `SELECT ... FOR UPDATE SKIP LOCKED` on the *discovery* queries, and no leader-election mechanism anywhere in the codebase (confirmed via repo-wide search — zero matches for advisory locks/leader election/`SKIP LOCKED`).
  - `run_credential_rotation_job` calls `self.provisioning_repo.get_all_active_or_suspended()` **without** `for_update=True`, then, for profiles past the 30-day cutoff, calls `self.provisioning_service.rotate_user_credentials(profile.account_id)`. That inner method *does* take `SELECT...FOR UPDATE` on the profile row, but it performs **no re-check of the cutoff/last_sync_at condition after acquiring the lock**. So if two replicas both list the same stale profile in the same tick, the second replica — after blocking on the row lock — will still unconditionally call `provider.reset_user_credentials()` again immediately after the first replica's rotation commits, silently invalidating credentials that were just issued.
  - `run_failed_provision_retry_job` calls `self.retry_repo.get_pending_retries(now)` also **without** `for_update=True`/`SKIP LOCKED`, so two replicas can pick up and process the same retry item concurrently (mitigated for `provision_subscription` by its internal conflict-fallback idempotency, but not zero-cost: duplicate Marzban API calls, duplicate log noise, and a race on which replica's `attempt_count`/`status` update wins).
- **Current deployment risk:** `Dockerfile` CMD uses `--workers 1`, and `docker-compose.prod.yml` defines a single `billing-api` service with no `deploy.replicas`. **Under the shipped configuration, this is not currently exploitable** because only one process runs. However, nothing in the code prevents scaling (`docker compose up --scale billing-api=N`, Kubernetes `replicas: N`, or bumping `--workers`) from immediately triggering this bug — a very plausible ops change for a "commercial VPN billing backend" needing HA.
- **Severity:** Medium (real bug, currently dormant due to deployment topology, but a landmine for the natural next scaling step).
- **Fix:** Add `SELECT ... FOR UPDATE SKIP LOCKED` (or a Postgres advisory lock keyed on job name) to all discovery queries in `LifecycleJobService`, and re-validate the state/condition (e.g., `last_sync_at <= cutoff`) *after* acquiring the per-row lock inside `rotate_user_credentials`/`provision_subscription`, not only in the caller's pre-lock snapshot.

### LOW — Duplicate retry-queue rows possible under concurrent provisioning failures
- **File/Function:** `app/services/provisioning/service.py::ProvisioningService._maybe_enqueue_retry` (65–101); `app/models/provisioning_retry.py::ProvisioningRetryItem` (no unique constraint on `account_id`).
- **Root cause:** The dedup check reads current pending items and inserts a new row if none match `account_id` + `PENDING`. Two concurrent failing calls for the same account (e.g., two browser tabs retrying "subscribe") can both pass the check before either inserts, creating two retry rows for the same account. No DB unique constraint (`account_id`, `status`) backs this up (confirmed in the migration: only non-unique indexes on `provisioning_retry_queue`).
- **Impact:** Redundant processing (two `provision_subscription` calls in the same job run for one account) — self-healing due to idempotent create/update fallback, but wastes API calls and produces confusing duplicate audit-log entries.
- **Fix:** Add a partial unique index `UNIQUE (account_id) WHERE status = 'PENDING'`, or use `INSERT ... ON CONFLICT DO NOTHING` semantics.

### LOW — Raw internal exception text can reach API responses
- **File/Function:** `app/routers/admin_billing.py::_handle_error` (54–59); `app/services/credential_service.py::regenerate_credentials`/`revoke_credentials`/`restore_credentials` (wrap `str(exc)` into `CredentialRotationFailedError`/`CredentialServiceError`); consumed by `app/routers/credentials.py` which returns `detail=str(exc)` verbatim.
- **Root cause:** When a race causes a `sqlalchemy.exc.IntegrityError` (e.g., the account_id/remote_user_id unique-constraint race in `provision_subscription`), the exception isn't caught specifically — it falls into the generic `except Exception as exc` branch, gets wrapped by `_translate_exception` using `str(exc)`, and that raw string (which can include Postgres constraint names and, depending on driver, parameter values) is propagated up through `CredentialServiceError`/`ProvisioningServiceError` to an HTTP `detail` field.
- **Impact:** Minor internal schema/detail disclosure to authenticated end users or admins (not VPN secrets — the VLESS/UUID zero-logging discipline is otherwise solid, see Safe section).
- **Fix:** Catch `IntegrityError`/`SQLAlchemyError` explicitly in `provision_subscription` and translate to a generic, non-leaking `ProvisioningConflictError("Provisioning already in progress or completed")`, treating it as an idempotent-success/retry path rather than a raw 400.

---

## Safe / Verified Behaviors

- **Duplicate remote Marzban user creation (main race) — mitigated, not exploitable to create two live remote users for one account.**
  Verified in `provisioning_profiles` migration (`20260704_1200_...`): both `account_id` and `remote_user_id` have **unique indexes** at the DB layer, and `accounts.marzban_username` is also unique. Combined with `provision_subscription`'s explicit `ProvisioningConflictError` → `update_user` fallback (`app/services/provisioning/service.py` lines 152–159) and the deterministic username (`user_{account_id.lower()}`), a concurrent double-create at the remote provider degrades to one create + one update, and the DB unique constraint prevents two local rows from ever coexisting. The "losing" concurrent request gets an error (see LOW finding above) but no duplicate remote user or duplicate DB row persists.

- **Local `ACTIVE`-but-remote-suspended divergence self-heals at read time.**
  `CredentialService.get_credentials` (`app/services/credential_service.py` line 171) checks `user_dto.status.lower() in ("disabled","suspended","inactive")` pulled live from Marzban via `get_provisioned_user` → `provider.get_user`, in addition to the local `profile.provisioning_state`. So if local state is stale `ACTIVE` while Marzban actually shows the user disabled, the live check still correctly blocks access. (Only the reverse direction — stale local `SUSPENDED` vs. live remote `ACTIVE` — fails to self-heal; see High finding.)

- **Retry queue has a real cap, exponential backoff, and terminal dead-letter state — no infinite retry loop.**
  `LifecycleJobService.run_failed_provision_retry_job` (`app/services/lifecycle_job_service.py` 250–309): backoff is `30 * 2**attempt_count`, and at `attempt_count >= 5` the item is marked `RetryItemStatus.FAILED` and permanently excluded from `get_pending_retries` (which filters `status == PENDING`). Verified no code path resets a `FAILED` item back to `PENDING`. This is a legitimate dead-letter terminal state — though there is no automated alerting on `FAILED` items today (operational gap, not a bug).

- **Zero-secret logging discipline is upheld everywhere reviewed.**
  Exhaustive regex search across `app/services/provisioning/*.py`, `app/services/credential_service.py`, `app/repositories/*.py`, `app/scheduler.py`, `app/services/lifecycle_job_service.py` for log statements referencing links/UUID/VLESS/password/token/secret/private_key/pbk found **no matches** that interpolate actual secret values. `marzban.py` logs only `username` (an identifier, not a secret) on every mutating call; `ProvisionedUserDTO.links` (which carries VLESS URIs) is never passed to any `logger.*` call in the reviewed files — confirmed by reading every log statement in `marzban.py` and `credential_service.py` line-by-line. The architectural docstring warning in `provider.py` (`ProvisionedUserDTO`) is actually honored in code.

- **Row-level locking is correctly applied for all *targeted* single-account mutations.**
  `ProvisioningRepository.get_by_account_id(..., for_update=True)` is used consistently in `suspend_subscription`, `reactivate_subscription`, `terminate_subscription`, `synchronize`, `rotate_user_credentials`, and `provision_subscription`. `SubscriptionRepository`-backed `expire_subscription`/`enter_grace_period`/`cancel_subscription` in `subscription_service.py` also lock via `get_by_id(..., for_update=True)` and have idempotency guards (e.g., `enter_grace_period` requires `status == ACTIVE`, so a second concurrent call after the first commits harmlessly raises `InvalidSubscriptionStateError` rather than double-transitioning). This makes the *expiration/grace* scheduler jobs safe under accidental double-invocation, unlike `run_credential_rotation_job` (Medium finding).

- **Crash mid-`create_user` does not orphan state indefinitely** — self-heals on next `provision_subscription` invocation (manual retry, retry-queue job, or user re-hitting the subscribe endpoint) because of the deterministic-username + conflict-fallback design described above. No permanently stuck `PENDING`-forever profile row was found: profiles are only ever created directly as `ACTIVE` inside `provision_subscription` (never left in `PENDING`), and there's no code path that writes a profile row without immediately setting a terminal-ish state (`ACTIVE`/`SUSPENDED`/`TERMINATED`) in the same transaction.

---

## Needs Verification

- **Actual Marzban API response codes for duplicate-username creation.** The code assumes Marzban returns `409` or `400` on duplicate `create_user` (`marzban.py` lines 92–109) and treats both as `ProvisioningConflictError`. This assumption is load-bearing for the "self-healing create" safety net above. I could not verify against a live Marzban instance/OpenAPI spec whether it might instead return `200`/`500` on duplicate-username creation in some versions — if it does, the fallback-to-`update_user` logic would not trigger and behavior would need re-testing against the real Marzban version in use.
- **Whether any other deployment target (Kubernetes manifests, Helm charts, CI/CD scale directives) outside this repo sets `--workers > 1` or `replicas > 1`.** Only `Dockerfile` and the two `docker-compose*.yml` files in this repo were checked; if orchestration config lives elsewhere (e.g., a separate infra repo), the Medium scheduler-duplication finding's likelihood could be understated.
- **Behavior of `session.refresh(profile)` / SQLAlchemy identity map across the `for_update` lock boundary when the row is created fresh in the same transaction** (`provision_subscription`, first-time provisioning branch, lines 162–182) — I traced the logic but did not execute it against a live Postgres instance to confirm no subtle async-session state leak occurs when `self.session.add(profile)` and `commit()` happen in the same call as the lock-attempt on a non-existent row. Recommend an integration test simulating two concurrent first-time `provision_subscription` calls for the same never-before-seen `account_id` to empirically confirm only one row lands and the loser receives a clean, non-crashing error (not just a logical trace).
- **Alerting/paging on `RetryItemStatus.FAILED` dead-letter items and on `SystemHealthRepository` "degraded" status** — I confirmed the states are recorded correctly in the DB but did not find (nor was asked to search) any notification/paging integration (email/Slack/PagerDuty) outside the reviewed files; this is an operational gap worth flagging to the team even if out of strict scope.

**Tool Call: Auditing DB concurrency & background jobs**
Status: Completed

# Security Audit Report — Concurrency & Database Correctness
## Scope: `billing-server/app/database.py`, `repositories/`, `models/`, `alembic/`, `scheduler.py`, `lifecycle_job_service.py`, `admin_billing_service.py`, `admin_account.py`, `performance/pooling.py`, `performance/cache.py`

---

## Findings

### CRITICAL — Duplicate ACTIVE subscriptions via check-then-insert race (no partial unique constraint)

**Files:** `app/models/subscription.py` (`Subscription` model), `app/services/subscription_service.py::SubscriptionService.create_subscription`, `app/services/payment/service.py::PaymentService.confirm_payment`, `app/repositories/subscription_repository.py::get_active_for_account`

**Root cause:** Business logic assumes "one active/trial/grace subscription per account," but this is enforced *only* by an application-layer read-then-write pattern:

```python
existing_active = await self.repository.get_active_for_account(account_id, now, for_update=True)
if existing_active:
    raise SubscriptionAlreadyActiveError(...)
subscription = await self.repository.create(...)   # plain INSERT
```

`SELECT ... FOR UPDATE` **cannot lock rows that don't exist**. If there is no pre-existing active subscription, the `FOR UPDATE` clause locks nothing, so it provides zero serialization guarantee against a concurrent INSERT. There is no unique or partial-unique index on `subscriptions(account_id)` filtered by status ∈ {TRIAL, ACTIVE, GRACE} — confirmed absent in both `app/models/subscription.py` and the migration `alembic/versions/20260704_0930_c3d4e5f6a7b8_add_subscriptions_table.py` (only non-unique indexes on `account_id`, `plan_id`, `status`, `expires_at`).

**Trigger scenario:** Two payment webhooks for the same account arrive within milliseconds (e.g., a user double-purchases, or Razorpay retries a webhook with a distinct `provider_payment_id`/order). Both go through `PaymentService.confirm_payment` → each uses a **separate DB session/transaction** (per-request `get_db()`), both call `get_active_for_account(..., for_update=True)`, both see zero rows (nothing to lock), both fall through to `subscription_service.create_subscription(...)`, and both commit successfully under default READ COMMITTED isolation. Result: **two ACTIVE subscription rows for one account**, double entitlement, and downstream double-provisioning via `ProvisioningService`.

**Fix:** Add a Postgres partial unique index:
```sql
CREATE UNIQUE INDEX uq_subscriptions_one_active_per_account
ON subscriptions (account_id)
WHERE status IN ('TRIAL','ACTIVE','GRACE');
```
Add this to the SQLAlchemy model as a `UniqueConstraint`/`Index` with `postgresql_where`, generate a migration, and catch the resulting `IntegrityError` in `create_subscription` to translate into `SubscriptionAlreadyActiveError` instead of letting it surface as a raw 500.

---

### HIGH — Lost-update race in `AdminAccountService.extend_subscription` / `suspend_account` / `activate_account` (no row lock)

**File:** `app/services/admin_account.py::AdminAccountService.extend_subscription` (and `suspend_account`, `activate_account`), backed by `app/repositories/account_repository.py::AccountRepository` (no `for_update` parameter exists anywhere in this repository) and `app/repositories/base.py::BaseRepository.update`.

**Root cause:** Classic TOCTOU: `account = await self._get_by_account_id(...)` (plain `SELECT`, no lock) → computes `new_expiry` from the in-Python `account.subscription_expires_at` → `account_repo.update(account, **updates)` (blind `SET`). There is no `SELECT ... FOR UPDATE`, no optimistic version column, and `AccountRepository` doesn't even expose a `for_update` flag (unlike every other repository in the codebase, e.g. `SubscriptionRepository`, `PaymentRepository`).

**Trigger scenario:** Two admin operators (or one operator double-clicking, or an automated billing script retried after a timeout) call `extend_subscription(account_id, 30)` concurrently. Both read the same `current_expiry`, both compute `base + 30 days` off the *same stale base*, both write. The second commit silently overwrites the first — the account gets **only one 30-day extension instead of two**, with no error, no conflict detection, and no audit trail showing data was lost.

**Fix:** Add `for_update: bool = False` to `AccountRepository.get_by_id`/`get_by_account_id` (mirroring the pattern already used in `SubscriptionRepository`, `PaymentRepository`, `DeviceRepository`), and have `extend_subscription`/`suspend_account`/`activate_account` acquire the lock before mutating, keeping the read+write in one transaction the same way `SubscriptionService.renew_subscription` already correctly does.

---

### MEDIUM — TOCTOU race in `PaymentService.create_payment` causes duplicate external gateway order creation

**File:** `app/services/payment/service.py::PaymentService.create_payment`

```python
existing = await self.payment_repo.get_by_idempotency_key(idempotency_key, for_update=True)
if existing:
    return existing
order_dto = await self.provider.create_order(...)   # external Razorpay call
payment = await self.payment_repo.create(...)        # unique(idempotency_key) at DB level
```

Same "lock a row that doesn't exist yet" limitation as Finding #1. Two concurrent requests with the same `idempotency_key` (e.g. client retry due to a slow/timed-out first response) both see `existing is None`, and **both call the Razorpay `create_order` API** before either has inserted a DB row. The DB-level `unique=True` constraint on `payments.idempotency_key` (confirmed in `app/models/payment.py`) prevents a duplicate *database* record (the second `create()` raises `IntegrityError` → `DuplicateEntityError` via `BaseRepository.create`), but the duplicate order was already created gateway-side — a real external side effect that isn't idempotent, and the losing request receives a `DuplicateEntityError` exception instead of the actual payment object the caller expected.

**Fix:** Serialize per-idempotency-key using a Postgres advisory lock (`pg_advisory_xact_lock(hashtext(idempotency_key))`) taken before the existence check, or pre-insert a `PENDING`/placeholder row within the same transaction as the existence check to claim the key before calling the external provider.

---

### MEDIUM — Scheduler has no distributed lock; latent duplicate-execution risk if scaled beyond one worker

**File:** `app/scheduler.py::JobScheduler.start` / `_execute_job` / `_loop_job`

All seven periodic jobs (`failed_provision_retry`, `subscription_expiration`, `grace_period_expiration`, `stale_pending_payment_cleanup`, `orphan_provisioning_cleanup`, `credential_rotation`, `system_health_monitoring`) are started unconditionally in every process that imports `app.main` via `lifespan()`. There is no Postgres advisory lock (`pg_try_advisory_lock`) or `SKIP LOCKED` pattern gating job execution to a single leader process.

**Current mitigation (verified safe today):** `Dockerfile` CMD uses `--workers 1`, and `docker-compose.prod.yml` defines a single `billing-api` service with no `deploy.replicas` scaling. With exactly one process running, there's no real duplicate-execution today.

**Latent risk:** If ops later scale horizontally (`--workers N>1`, or multiple container replicas — a very natural scaling step for this kind of service), every process runs every job on its own interval, independently. Row-level `FOR UPDATE` locks inside `SubscriptionService`/`PaymentService` methods prevent double-processing of the *same* row (the loser blocks, then finds the row already transitioned and raises a benign `InvalidSubscriptionStateError`, caught and logged), but:
- `run_failed_provision_retry_job` (`app/services/lifecycle_job_service.py`) fetches `get_pending_retries(now)` **without** `for_update=True`, then calls `provisioning_service.provision_subscription(...)` (an external Marzban API call) *before* taking any row lock. Two concurrent scheduler processes can both fetch the same pending item and both fire the external provisioning call concurrently — real duplicate external side effects, not just wasted DB work.
- All jobs cause N× redundant read traffic and N× redundant external health/API checks (Marzban, Razorpay) per interval.

**Fix:** Wrap `_execute_job` in a `pg_try_advisory_lock(job_name_hash)` acquired at the start of each job and released at the end (or held for the transaction via `pg_advisory_xact_lock`); skip execution if the lock isn't obtained. Additionally, change `get_pending_retries` calls in `run_failed_provision_retry_job` to use `for_update=True` (or `for_update_skip_locked`) before calling out to the provisioning service.

---

### LOW — `MemoryCache` unbounded growth is a latent risk, currently mitigated by key-space design

**File:** `app/performance/cache.py::MemoryCache`

`_store` is a plain dict guarded correctly by `asyncio.Lock()` for every mutating/reading operation — this part is **thread/coroutine-safe and correct**. However, expiration is lazy (only evaluated on `get()`); entries that are `set()` but never subsequently `get()` are never purged until process restart, and there's no `maxsize`/LRU eviction. This is currently low-risk because `validate_cache_key` restricts all keys to `ALLOWED_CACHE_PREFIXES = ("plan:", "config:", "flag:", "health:")`, which is a small, bounded key space in this domain. If the whitelist is ever expanded to include higher-cardinality keys (e.g., per-account or per-payment data — which is explicitly blocked today by `FORBIDDEN_KEYWORDS`), this would become an unbounded memory leak.

**Fix (optional hardening):** Add a periodic sweep (or `maxsize` + eviction) as defense-in-depth before the whitelist is ever widened.

---

## Safe / Verified Behaviors

- **`app/database.py`** — `expire_on_commit=False` is correctly set, appropriate for returning ORM objects to callers after commit without triggering lazy-reload. `get_db()` yields one `AsyncSession` per request via `async with AsyncSessionLocal() as session`; on any exception the context manager's `__aexit__` calls `session.close()`, which internally rolls back any open transaction before returning the connection to the pool — verified this does not leak a "broken" transaction across requests. Rollback/failure counters are wired via SQLAlchemy `rollback` event listener.
- **`app/repositories/base.py`** — `create`, `update`, `delete` consistently wrap DB operations in try/except, translating `IntegrityError`→`DuplicateEntityError` and `SQLAlchemyError`→`DatabaseOperationError`, and **always call `await self.session.rollback()`** in the except branch before re-raising. This is the correct pattern that prevents "This session's transaction has been rolled back" errors from leaking to subsequent queries on the same session.
- **`app/repositories/*.py` (read paths)** — All list/count/get methods wrap `session.execute` in try/except and raise `DatabaseOperationError`; none of them leave the session in an unrolled-back broken state on a raised `SQLAlchemyError` from a pure read (reads don't open a broken write transaction in Postgres the same way, so this is acceptable).
- **`app/services/payment/service.py::confirm_payment`** — Correctly locks the `Payment` row (`for_update=True`) by `provider_order_id`/`provider_payment_id` before mutating, checks `status == PAID` for idempotent early-return (protects against duplicate webhook delivery for the *same* payment), and wraps the full multi-step entitlement update (payment update + subscription renew/activate/create + commit) in a single try/except with `await self.session.rollback()` on any failure. This is a solid, atomic transaction boundary for the *single-payment* case.
- **`app/models/provisioning.py`** — `ProvisioningProfile.account_id` has `unique=True`, correctly enforcing "one provisioning profile per account" at the DB level (unlike the subscriptions case).
- **`app/models/device.py`** — `device_guid` has `unique=True`, correctly enforcing global uniqueness.
- **`app/models/payment.py`** — `idempotency_key` has `unique=True`, correctly providing a DB-level backstop against duplicate payment rows (even though the pre-check race in Finding #3 still causes duplicate *external* gateway calls).
- **FK cascade behavior** — `accounts.id → devices/refresh_tokens/subscriptions` all use `ondelete="CASCADE"` with `passive_deletes=True` on the ORM relationships (`app/models/account.py`), consistent between model and migrations. `payments.subscription_id → subscriptions.id` uses `ondelete="SET NULL"`, appropriate since payment history should survive subscription deletion.
- **`app/scheduler.py::JobScheduler.stop`** — Cancels all tracked tasks and `await asyncio.gather(*self._tasks, return_exceptions=True)`, correctly draining cancellation without leaking tasks. `_loop_job` explicitly catches and re-raises `asyncio.CancelledError` to permit clean shutdown while catching all other `Exception`s so a single bad iteration cannot permanently kill the loop — verified this is NOT a case of "unhandled exception kills scheduler forever."
- **`asyncio.create_task` usage** — Only two call sites in `app/`: `app/scheduler.py::JobScheduler.start` (tasks stored in `self._tasks`, always awaited/cancelled in `stop()` — correctly tracked, no orphaned tasks) and `app/performance/benchmarks.py` (load-testing tool, tasks immediately gathered via `asyncio.gather`). No fire-and-forget tasks with swallowed exceptions were found anywhere in `app/`.
- **`app/performance/cache.py::MemoryCache`** — Every dict access (`get`/`set`/`delete`/`clear`/`get_stats`) is guarded by the same `asyncio.Lock()`, so there is no read/write race between concurrent coroutines on the shared `_store` dict.
- **Alembic migration chain** — Verified linear, single-head history from `de60c540a56e` → ... → `f3e6ac6cd9bb`, no branch points, no missing `down_revision` links — no schema drift/multiple-heads risk.
- **`app/repositories/refresh_token_repository.py`** — `revoke`/`revoke_all_for_account` use bulk `UPDATE ... WHERE is_revoked == False` (not a read-then-write on ORM objects), which is race-safe by construction (atomic at the SQL level) and correctly rolls back on `SQLAlchemyError`.

---

## Needs Verification

- **`app/services/credential_service.py` and `app/services/provisioning/*.py`** were not fully read in this pass (only referenced indirectly via `lifecycle_job_service.py` and `dependencies.py`). Given `provision_subscription`/`rotate_user_credentials` make external Marzban calls interleaved with DB writes, they deserve a dedicated pass to confirm the same "external call before commit/lock" race pattern flagged in Finding #4 doesn't also exist there in isolation (not just under scheduler concurrency).
- **`app/routers/*.py`** were not audited for whether any router bypasses services/repositories to touch `session` directly, or holds a session across an `await` to an external HTTP call without a timeout (could exhaust the pool under load). Given `pool_size`/`max_overflow` in `app/performance/pooling.py` are reasonably sized for production, this is a lower-priority follow-up but not confirmed safe.
- **`connection_signal_repository.py` and `system_health_repository.py`** were listed but not read in detail; based on the consistent pattern in every other repository file, they are very likely safe, but this wasn't line-verified.
- **Isolation level**: The engine uses Postgres/asyncpg defaults (READ COMMITTED) — not explicitly configured anywhere. This wasn't flagged as a bug on its own, but it is the mechanism that makes Findings #1 and #3 possible (SERIALIZABLE isolation would turn these into serialization failures/retries rather than silent duplicate rows — but retrofitting SERIALIZABLE broadly would require app-wide retry logic, so the targeted unique-constraint fixes above are the more surgical solution).

**Tool Call: Auditing Docker, CI/CD, secrets & hardening**
Status: Completed

# Security Audit Report — RealityTunnel Billing/Auth Server

Scope: `OverREALITY/billing-server`. All findings below were verified by reading the actual source referenced — no assumptions were made about unread code.

---

## Findings — Critical

### C1. Central "SecretRegistry" validation logic is defined but never executed
**File:** `app/core/secret_registry.py` (L38–52, L141–224) vs `app/core/startup_validator.py` (L75–251)

Every secret (`postgres_password`, `secret_key`, `cookie_signing_key`, `encryption_key`, `razorpay_key_secret`, etc.) is registered with a `validation_function` (e.g. `_validate_strong_secret`, `_validate_pem_key`) intended to reject weak/placeholder/short secrets in production. **`def_obj.validation_function(...)` is never called anywhere in the codebase** (confirmed via project-wide grep — the only occurrences of `validation_function` are its declaration and assignment). `startup_validator.py` instead re-implements a handful of ad-hoc inline checks for only `secret_key` and Razorpay keys, completely bypassing the registry's own enforcement layer for `postgres_password`, `cookie_signing_key`, `encryption_key`, etc.

**Impact:** A large portion of the intended secret-strength enforcement never runs. Weak/placeholder database passwords or "secret"/"test"/"default"-containing values for secrets not explicitly checked inline can pass startup validation silently.

**Fix:** In `validate_startup_configuration`, iterate `secret_registry.get_all_definitions()` and, for every `required_in_production` secret, call `definition.validation_function(definition.value)`; fail fast if it returns `False`.

### C2. "Secure Key Permissions" startup check is a no-op stub that always reports success
**File:** `app/core/startup_validator.py` L222–233

```python
if os.name == "posix":
    try:
        for key_name in ("jwt_private_key", "admin_jwt_private_key"):
            def_obj = secret_registry.get_definition(key_name)
            if def_obj and def_obj.value:
                # We verify if file permissions are secure if file exists
                pass
        prod_checks["Secure Key Permissions"] = True
    except Exception:
        ...
```

The loop body is a bare `pass` — no `os.stat()`/`stat.S_IMODE` check is performed. The Configuration Report will print `✓ Secure Key Permissions` unconditionally (there's no code path that can make this `False`), even if the Ed25519 private key PEM files are world-readable (`0644`/`0666`).

**Impact:** Operators get a false assurance from the startup report that private key file permissions were audited. A misconfigured deployment (e.g., a bind-mounted key with `0644`) is silently accepted.

**Fix:** Actually implement the check: `os.stat(path).st_mode & 0o077` should be `0`, and fail the guard if not.

### C3. `AuditService.record_event()` — the security audit trail — is never invoked in production code
**File:** `app/security_hardening/audit.py` (whole file), cross-checked via project-wide grep for `.record_event(`

`AuditService` is a well-built, redaction-aware, "immutable" audit log intended to record `admin_login`, `admin_action`, `payment_event`, `credential_regeneration`, `device_registration/deletion`. It is instantiated as a singleton (`audit_service`), imported into `app/main.py`, and attached to `app.state.audit` — but **no router or service anywhere in `app/` ever calls `audit_service.record_event(...)`**. The only usage found is a read of `get_queue_status()` in `app/routers/health.py` for the admin health payload, which will always report `total_events_recorded: 0`.

**Impact:** There is effectively **no security audit trail** for admin logins, admin actions, credential regenerations, or payment events, despite the code, docstrings, and health payload strongly implying one exists ("Immutable security audit logging service... Records security-critical events"). In an incident response scenario, there will be nothing to review.

**Fix:** Wire `audit_service.record_event(...)` into `admin_auth.py` (login success/failure), `admin.py` (admin actions), `credentials.py` (credential regeneration), `billing.py`/`webhooks.py` (payment events), and `devices.py` (device lifecycle). Also persist events to durable storage (see H3) rather than an in-process list.

### C4. `deployment/production/deploy.sh` secret-presence guard is broken and silently passes regardless of input
**File:** `deployment/production/deploy.sh` L8

```bash
if [ -z "$POSTGRES_PASSWORD" ] or [ -z "$JWT_SECRET" ]; then
```

`or` is not valid Bash syntax inside/between `[ ]` tests (Bash has no `or` keyword; the correct forms are `||` between commands or `-o` inside a single `[ ]`). Verified experimentally:

```
$ unset POSTGRES_PASSWORD JWT_SECRET
$ if [ -z "$POSTGRES_PASSWORD" ] or [ -z "$JWT_SECRET" ]; then echo BAD; else echo OK; fi
bash: line 1: [: too many arguments
OK
```

The `[` command receives too many arguments (everything through the second `]` becomes one long argument list), returns exit status 2, and — because 2 is still "non-zero"/falsy for the `if` — **the script takes the `else` branch and prints "OK" instead of erroring, no matter what the two variables are set to.** The documented pre-deployment safety gate ("ERROR: Required production environment variables... are not set!") **never fires**.

**Impact:** This specific safety net is dead. The only remaining backstop is `docker-compose.prod.yml`'s `${POSTGRES_PASSWORD:?...}`/`${JWT_SECRET:?...}` required-variable syntax, so a total secretless-boot is still prevented today — but this is incidental, not because the deploy script's own guard works. Any future change that removes the compose-level `:?` guard (e.g., a refactor) would remove the only actual protection, because the script-level check gives false confidence that it's protecting anything.

**Fix:**
```bash
if [ -z "$POSTGRES_PASSWORD" ] || [ -z "$JWT_SECRET" ]; then
```
(Note: also see H1 below — `JWT_SECRET` isn't even consumed by the app, so this check protects a variable that has no effect.)

---

## Findings — High

### H1. `JWT_SECRET`, `MASTER_TOKEN_HASH`, and `API_KEY` are required by `docker-compose.prod.yml` but are **not read by the application at all**
**Files:** `docker-compose.prod.yml` L62–64, `app/config.py` (entire `Settings` class, L21–162)

`docker-compose.prod.yml` marks `JWT_SECRET` as a hard-required env var (`${JWT_SECRET:?JWT_SECRET is required for production}`) and passes `MASTER_TOKEN_HASH`/`API_KEY` through. However, `app/config.py`'s `Settings` model has **no fields named `jwt_secret`, `master_token_hash`, or `api_key`**, and `SettingsConfigDict(extra="ignore")` means pydantic-settings silently discards unknown environment variables. Actual JWT signing uses **Ed25519 keypairs loaded from PEM files on disk** (`app/security/jwt_service.py` L86–107, `app/security/admin_jwt.py` L103–124), sourced from `dev_keys/ed25519_private.pem` / `dev_keys/admin/admin_ed25519_private.pem` — a filesystem path, not an env var.

**Impact:** Operators following the checklist/compose file reasonably believe that setting a strong `JWT_SECRET` env var secures JWT issuance. It does nothing. The actual signing key material (the Ed25519 PEM files) has **no env-var-based provisioning path at all** — it must be manually placed on disk/volume, and there is no documented secure provisioning flow for this in the reviewed deployment scripts. This is a serious "looks secured, isn't" gap: a strong `JWT_SECRET` in your secrets manager gives zero actual protection.

**Fix:** Either (a) remove `JWT_SECRET`/`MASTER_TOKEN_HASH`/`API_KEY` from `docker-compose.prod.yml` since they're dead config, or (b) actually wire a `jwt_secret`-equivalent into key provisioning and document how the Ed25519 keys are meant to be securely delivered to the production container (e.g., Docker secrets, mounted volume, KMS-backed init container) — the current setup gives no such guidance for the one production instance's private key material.

### H2. `X-Forwarded-For`/`X-Real-IP` trust logic takes the leftmost (client-controlled) value, enabling rate-limit and IP-ban bypass
**File:** `app/rate_limit/middleware.py` L38–50

```python
if getattr(settings, "trust_proxy", False):
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        client_ip = x_forwarded_for.split(",")[0].strip()   # <-- leftmost = attacker controlled
```

When `trust_proxy=True` (which operators MUST enable if running behind nginx/Cloudflare/any LB, per the standard architecture implied by `CHECKLIST.md`), the code takes the **first (leftmost)** entry of `X-Forwarded-For`. Per RFC 7239 / standard reverse-proxy convention, the leftmost entry is the *original client-supplied* value (if the proxy appends rather than replaces), and only the **rightmost, proxy-appended hop** can be trusted. An external client can simply send `X-Forwarded-For: 1.2.3.4` (a different value on every request) and this code will treat every request as coming from a different IP.

**Impact:** Trivial per-IP rate-limit bypass (`rate_limit_login`, `rate_limit_admin_login`, `rate_limit_register`, etc. all key off this same extracted IP — see `app/rate_limit/limiter.py` L85–100), enabling credential-stuffing/brute-force against `/api/auth/login` and `/api/admin/login` at unlimited rate, and defeating any future IP-based blocklisting.

**Fix:** Only trust `X-Forwarded-For` if the immediate peer (`request.client.host`) is itself an allow-listed trusted proxy IP/CIDR, and then take the **rightmost untrusted-boundary hop**, not the leftmost. Frameworks like `starlette-proxy-headers` or manual trusted-hop-counting logic exist for this.

### H3. Rate limiting is in-memory only — resets on restart and does not work across horizontally scaled replicas
**File:** `app/rate_limit/storage.py` (entire file), `app/rate_limit/backend.py` L52–169

```python
@lru_cache
def get_rate_limit_backend() -> RateLimitBackend:
    """... In future phases, this factory will inspect settings to initialize RedisRateLimitBackend."""
    return MemoryRateLimitBackend()
```

The only backend implementation is `MemoryRateLimitBackend`, an in-process `dict`/`deque`. There is no Redis (or other shared) backend, despite the abstract interface being explicitly designed for one ("designed for Redis compatibility").

**Impact:**
- Every container restart/redeploy resets all counters (a scripted attacker can force-trigger redeploys or simply wait, or exploit rolling deploys).
- If the service is scaled to N replicas behind a load balancer (the natural next step for a "commercial VPN billing backend"), an attacker distributing requests round-robin across replicas gets **N× the intended rate limit** for login/register/refresh endpoints, since each replica tracks its own independent counters.

**Fix:** Implement a Redis-backed `RateLimitBackend` (the abstraction already supports this) and use it whenever `cache_backend != "memory"` or a dedicated `RATE_LIMIT_BACKEND=redis` flag is set, before running more than one replica.

### H4. No `.dockerignore` — full build context (potentially including `.env`, `dev_keys/*.pem`, `.git`) is sent to the Docker daemon and can be baked into image layers
**Files:** `Dockerfile` L54 (`COPY --chown=billing:billing . .`), confirmed absence via `find_path` for `**/.dockerignore` (no matches)

The Dockerfile's runtime stage does `COPY . .` from the full build context with **no `.dockerignore`** to exclude `.env`, `dev_keys/` (which routinely contains locally generated Ed25519 private keys once the app has booted once in dev mode — see `app/security/jwt_service.py` L115–131), `.git/`, `backups/`, or test artifacts. `.gitignore` prevents these from being *committed*, but `.gitignore` has **no effect on `docker build`** — only `.dockerignore` does.

**Impact:** If a developer/CI runner builds the image from a working directory where `.env` exists or `dev_keys/` has been populated (which happens automatically the first time the app runs in dev mode), those secrets/private keys get copied into an image layer. They are then permanently extractable via `docker history`, `docker save | tar -x`, or simply `docker run --rm <image> cat /app/.env`, even after the file is later "deleted" in a subsequent layer (layers are immutable and cumulative).

**Fix:** Add a `.dockerignore` at the repo root excluding at minimum: `.env`, `.env.*`, `dev_keys/`, `.git/`, `backups/`, `__pycache__/`, `*.pem`, `tests/`.

---

## Findings — Medium

### M1. SAST and dependency-vulnerability scanning in CI are purely advisory (`|| true`) and can never fail the build
**File:** `.github/workflows/security.yml` L31–37

```yaml
- name: Run Bandit SAST
  run: |
    bandit -r app/ -ll -i || true
- name: Run pip-audit Dependency Scanner
  run: |
    pip-audit -r requirements.txt || true
```

Both commands are suffixed with `|| true`, forcing exit code 0 regardless of findings — including critical hardcoded-secret detections (Bandit) or known-CVE dependencies (pip-audit). Only the Trivy filesystem scan (same file, L39–53) actually gates the build (`exit-code: '1'`).

**Impact:** A critical dependency CVE or a Bandit-flagged hardcoded credential can merge to `main` and ship without any CI failure; these scans exist for appearances only.

**Fix:** Remove `|| true` from both steps, or explicitly set a severity threshold and only `continue-on-error` for low-severity findings (e.g., `pip-audit --strict` gated at `HIGH`/`CRITICAL`).

### M2. GitHub Actions are pinned to mutable tags, not immutable commit SHAs
**Files:** All of `.github/workflows/*.yml`, e.g. `actions/checkout@v4`, `docker/build-push-action@v5`, `sigstore/cosign-installer@v3.5.0`

Every third-party action is referenced by a mutable tag. Tags can be moved by a compromised or malicious maintainer to point at different code without changing the visible version string (this is the exact mechanism behind several real supply-chain incidents, e.g. `tj-actions/changed-files` 2025).

**Impact:** A compromised upstream action could silently execute arbitrary code in CI with access to `secrets.GITHUB_TOKEN` (write:packages, write:contents, id-token for OIDC signing in `release.yml`), potentially poisoning released images or signing malicious artifacts with the project's Cosign OIDC identity.

**Fix:** Pin all `uses:` references to a full commit SHA (`actions/checkout@<40-char-sha> # v4.x.x`) and use Dependabot/Renovate to keep SHAs current.

### M3. `/metrics` is unauthenticated by default in production
**Files:** `app/config.py` L102 (`metrics_auth_required: bool = False`), `app/routers/metrics.py` L39, `docker-compose.prod.yml` (no `METRICS_AUTH_REQUIRED` override)

`metrics_auth_required` defaults to `False`, and `docker-compose.prod.yml` never overrides it. The `/metrics` endpoint is also explicitly exempted from rate limiting (`app/rate_limit/limiter.py` L49, path in `("/", "/health", "/version", "/metrics")`).

**Impact:** Anyone can scrape internal operational metrics (request counters per endpoint, DB pool utilization, rate-limit denial counts, audit-queue size) unauthenticated and unlimited-rate. While no secrets are exposed (confirmed — `metrics_registry` only stores counters/gauges, not secret values), this aids reconnaissance (business volume, endpoint enumeration) and is itself an unthrottled endpoint that can be hit at any rate.

**Fix:** Default `metrics_auth_required=True` in production, or bind `/metrics` to an internal-only network path (reverse proxy rule restricting to monitoring infra IPs).

### M4. Interactive API docs (`/docs`, `/redoc`) are unconditionally enabled, including in production
**File:** `app/main.py` L96–103

```python
app = FastAPI(
    ...
    docs_url="/docs",
    redoc_url="/redoc",
    ...
)
```

There is no environment-based conditional (e.g., `docs_url=None if settings.environment == "production" else "/docs"`).

**Impact:** Full OpenAPI schema (every route, including `/api/admin/*`, request/response models, and their field names/types) is disclosed to unauthenticated internet clients in production. This is reconnaissance-grade information disclosure — low direct exploitability, but it removes the "security through relative obscurity" of the admin API surface and helps attackers target fuzzing/enumeration precisely.

**Fix:** Disable `/docs`/`/redoc`/`/openapi.json` when `settings.environment == "production"`, or gate them behind the same admin auth used for `/health` internals.

### M5. Production billing-api port is published directly to the host without a documented enforcement mechanism for TLS termination
**File:** `docker-compose.prod.yml` L68–69 (`ports: ["${PORT:-8080}:8080"]`), cross-checked with `deployment/production/CHECKLIST.md` L16

The Compose file binds `8080` on **all host interfaces** (no `127.0.0.1:` prefix), and relies entirely on operator discipline (a checklist checkbox: "TLS termination (Reverse Proxy/LB/Nginx/Cloudflare) is active") rather than any technical control in the repo. There is no bundled/reference nginx or Traefik reverse-proxy config in `deployment/` to actually enforce this.

**Impact:** If an operator deploys this compose file on a VPS with a public IP and skips (or misconfigures) the external reverse proxy step, the API is served in **plaintext HTTP directly to the internet** on port 8080 — credentials (`master_token`, refresh tokens), even though bodies are JSON over HTTPS-shaped headers (HSTS header is emitted per `SecurityHeadersMiddleware`, but HSTS is meaningless over a plain HTTP response and browsers ignore it on non-TLS connections).

**Fix:** Bind to `127.0.0.1:${PORT}:8080` in the prod compose file and ship a reference reverse-proxy (nginx/Caddy/Traefok) service in the same compose stack that terminates TLS and proxies to the internal Docker network, rather than relying purely on a manual checklist item.

### M6. No `cap_drop`/`no-new-privileges` hardening on the production container
**File:** `docker-compose.prod.yml` (billing-api service block, L35–94)

The container correctly runs non-root (Dockerfile `USER billing`), uses `read_only: true`, and has resource limits — good baseline hardening (see Safe section). However, there is no `cap_drop: ["ALL"]` or `security_opt: ["no-new-privileges:true"]`, so the container retains the full default Docker capability set (e.g., `NET_RAW`, `SETUID`, `SETGID`) even though the app needs none of them.

**Impact:** Defense-in-depth gap — in the event of an application-level RCE, the attacker's process retains more Linux capabilities than necessary, increasing container-escape/lateral-movement surface.

**Fix:**
```yaml
cap_drop: ["ALL"]
security_opt: ["no-new-privileges:true"]
```

---

## Findings — Low

### L1. Dev `docker-compose.yml` publishes PostgreSQL `5432` to the host by default
**File:** `docker-compose.yml` L13–14 — labeled "host access for Alembic migrations from dev machine." This is the *development* compose file, not `docker-compose.prod.yml` (which correctly keeps Postgres on an `internal: true` network with no published ports — see Safe section). Low risk since it's dev-only, but flag the risk that a developer might reuse/copy this file for a quick "production-ish" deployment. Recommend a comment warning against reuse in any internet-facing context.

### L2. CI/lint workflow steps are fully advisory
**File:** `.github/workflows/ci.yml` L29–36 — `ruff check ... || true`, `black --check ... || ruff format --check ... || true`, `mypy app ... || true`. Not a security vulnerability per se, but combined with M1 it shows a broader pattern: CI is largely decorative rather than a real quality/security gate.

### L3. Workflows lack explicit least-privilege `permissions:` blocks
**Files:** `.github/workflows/ci.yml`, `docker.yml`, `security.yml` — none declare a `permissions:` block, so the `GITHUB_TOKEN` gets whatever the repo/org default is (potentially `write-all` on older repos). `release.yml` does declare `permissions:` but grants `contents: write, packages: write, id-token: write` at the workflow level rather than scoping to the specific job that needs it (there's only one job, so this is minor here, but the pattern should be followed repo-wide).

**Fix:** Add `permissions: contents: read` (or narrower) to every workflow lacking one.

---

## Safe / Verified Behaviors

- **Non-root container user** — `Dockerfile` L48–56 creates a `billing` (uid 1001) user and `USER billing` is set before `ENTRYPOINT`. Verified: no root execution.
- **Read-only root filesystem in prod** — `docker-compose.prod.yml` L46–48 sets `read_only: true` with `tmpfs: [/tmp]`. Verified.
- **HEALTHCHECK present** in both `Dockerfile` (L62–63) and both compose files. Verified.
- **No secrets passed as Docker build ARGs** — the only `ARG`s (`BUILD_DATE`, `GIT_COMMIT`, `VERSION`) are non-secret metadata used solely for OCI labels (`Dockerfile` L23–34). Verified — no credentials in `ARG`/`docker history`.
- **PostgreSQL is never exposed to the public network in production** — `docker-compose.prod.yml` places `postgres` only on `internal_net` (`internal: true`, L12–13, L96–98) with **no `ports:` mapping at all**. Verified safe; matches the CHECKLIST.md requirement.
- **Resource limits present in production compose** — both `postgres` and `billing-api` have `deploy.resources.limits/reservations` for CPU/memory (`docker-compose.prod.yml` L25–32, L87–94). Verified — mitigates basic resource-exhaustion DoS from a single compromised/runaway process.
- **No CORS wildcard-with-credentials issue** — there is **no `CORSMiddleware` registered anywhere** in the app (`grep` for `CORSMiddleware|allow_origins|CORS` across `app/` returned zero matches). Absence of CORS headers means browsers enforce same-origin by default; there is no wildcard+credentials misconfiguration because there is no CORS configuration at all. Verified safe (though note: if a browser-based SPA client is planned, CORS will need to be added carefully later — do not default to `allow_origins=["*"]` with `allow_credentials=True`).
- **Redaction pipeline is correctly wired for both log format paths** — `app/logging_config.py` L26–34 selects `StructuredJsonFormatter` (json/prod/staging) or `RedactingFormatter` (dev console); **both** ultimately call `redact_string()` (`app/observability/logging.py` L114–116, `app/core/redaction.py` L108–110). Verified — not a bypass as initially hypothesized.
- **No raw secret interpolation into log calls found** — targeted greps across `app/` for `logger.*` calls referencing `token|password|secret|jwt|refresh|authorization|master_token|api_key` show only fixed, non-parameterized messages ("Refresh token issued", "JWT validation failed: Token expired", etc.) or properly hashed/truncated values (`ip_hash` in `app/rate_limit/limiter.py` L102–120). No instance of a raw secret value being passed as a log argument was found.
- **Webhook signature verification uses constant-time comparison** — `app/services/payment/razorpay.py` L174–191 uses `hmac.new(...).hexdigest()` + `hmac.compare_digest()`. Verified safe against timing attacks and signature forgery via naive `==`.
- **Master token / auth flow uses proper cryptographic primitives** — `app/security/tokens.py` (CSPRNG `secrets.token_hex`), `app/security/crypto.py` (`hmac.compare_digest` via `compare_secrets`), `app/services/authentication.py` L49–53 (dummy-hash constant-time comparison to prevent account-enumeration timing attacks). This is well-reasoned, documented, and correctly implemented. Verified safe.
- **CSRF middleware is correctly wired** — `CSRFMiddleware` is registered in `app/main.py` L117 and scoped only to `/api/admin/*` cookie-authenticated flows (`app/security_hardening/csrf.py` L43–48); Bearer-token-only clients are exempted appropriately since CSRF is a cookie-based-auth threat model concern. Verified — not dead code, and scoping is sound given the app's Bearer-token-first auth design.
- **Security headers middleware is wired and functioning** — `SecurityHeadersMiddleware` is registered in `main.py` L121 and unconditionally applies HSTS/CSP/X-Frame-Options/etc. per `app/security_hardening/headers.py`. Verified not dead code.
- **`dev_keys/` is empty in the working tree and excluded via `.gitignore`** (`dev_keys/`, `*.pem`) — verified directory listing is empty and pattern present in `.gitignore` L11–12. No private keys found committed to the working tree.
- **Extended `/health` internals require admin auth** — `app/routers/health.py` L139 (`if admin:`) correctly gates fingerprint/scheduler/backup/security-rotation details behind `get_current_admin_optional`; anonymous callers only get status/db-latency/version. Verified safe.
- **No `pull_request_target` usage anywhere**, and all workflows trigger on `pull_request` (not `_target`), meaning secrets are not exposed to code checked out from forked PRs by default GitHub Actions behavior. Verified safe.
- **`.env` is never committed** — only `.env.example` exists in the repo; `.env` is `.gitignore`d (L1). (Contents of `.env.example` could not be read due to a tool-level privacy restriction on `.env*` paths — see Needs Verification.)

---

## Needs Verification

1. **`.env.example` contents** — could not be read (blocked by the tool's `private_files` policy for `.env*` globs). Should be manually reviewed to confirm no real/reusable secret values were accidentally used as "example" defaults.
2. **Production Ed25519 key provisioning process** — given H1/H4, it's unclear from the reviewed files *how* operators are expected to securely deliver `dev_keys/ed25519_private.pem` and `dev_keys/admin/admin_ed25519_private.pem` to the production container (Docker secret? mounted volume? manually copied?). No script in `deployment/` addresses this. Ask the team directly what the real production key-provisioning runbook is.
3. **Postgres connection encryption in non-Docker-internal-network deployments** — `app/database.py` sets no `ssl`/`sslmode` connect args. This is likely acceptable given Postgres sits on an `internal: true` Docker network in the documented topology, but if this stack is ever pointed at a managed/external Postgres (e.g., RDS, Azure Flexible Server) over a real network, TLS is not enforced anywhere in code and should be verified/added.
4. **Actual behavior of `staging` deploy script's `DEBUG=true` export** — `deployment/staging/deploy_staging.sh` exports `DEBUG=true`, but `docker-compose.prod.yml` (which staging reuses) hardcodes `DEBUG: "false"` in the container `environment:` block, so the exported shell var has no effect on the container. This looks like a harmless inconsistency (staging can never actually get debug mode via this path), but it's worth confirming with the team whether staging *should* have debug logging and, if so, fixing the compose file to pass it through instead of silently ignoring it.

## Assistant

<thinking>
I've got detailed findings from all three sub-agents, so now I need to spot-check a few of the most critical issues before wrapping up the report—specifically the secret registry validation gap, the X-Forwarded-For header trust logic, and that bash operator bug in the deploy script.
</thinking>

Let me verify a few of the most critical sub-agent findings myself before finalizing, since these are severe claims that need direct confirmation.

**Tool Call: Search files for regex `validation_function`**
Status: Completed

file://D:\My projects\VPN\OverREALITY\billing-server\app\core\secret_registry.py#L25-30

```
    name: str
    description: str
    required_in_production: bool
    rotation_recommendation: str
    validation_function: Callable[[str | None], bool]
    value: str | None = None
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\core\secret_registry.py#L38-45

```
    def register(
        self,
        name: str,
        description: str,
        required_in_production: bool,
        rotation_recommendation: str,
        validation_function: Callable[[str | None], bool],
    ) -> None:
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\core\secret_registry.py#L46-52

```
        self._secrets[name] = SecretDefinition(
            name=name,
            description=description,
            required_in_production=required_in_production,
            rotation_recommendation=rotation_recommendation,
            validation_function=validation_function,
        )
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\core\secret_registry.py#L141-147

```
secret_registry.register(
    name="jwt_private_key",
    description="Ed25519 private signing key for customer JWT tokens.",
    required_in_production=True,
    rotation_recommendation="Annual rotation or immediately upon suspected compromise.",
    validation_function=_validate_pem_key,
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\core\secret_registry.py#L148-154

```
secret_registry.register(
    name="jwt_public_key",
    description="Ed25519 public verification key for customer JWT tokens.",
    required_in_production=True,
    rotation_recommendation="Synchronized with private key rotation.",
    validation_function=_validate_pem_key,
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\core\secret_registry.py#L155-161

```
secret_registry.register(
    name="admin_jwt_private_key",
    description="Ed25519 private signing key for administrator JWT tokens.",
    required_in_production=True,
    rotation_recommendation="Annual rotation or immediately upon suspected compromise.",
    validation_function=_validate_pem_key,
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\core\secret_registry.py#L162-168

```
secret_registry.register(
    name="admin_jwt_public_key",
    description="Ed25519 public verification key for administrator JWT tokens.",
    required_in_production=True,
    rotation_recommendation="Synchronized with private key rotation.",
    validation_function=_validate_pem_key,
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\core\secret_registry.py#L169-175

```
secret_registry.register(
    name="postgres_password",
    description="Database authentication secret for PostgreSQL.",
    required_in_production=True,
    rotation_recommendation="Quarterly rotation via automated credentials management.",
    validation_function=_validate_non_empty_secret,
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\core\secret_registry.py#L176-182

```
secret_registry.register(
    name="secret_key",
    description="Master secret key for general cryptographic HMAC and token operations.",
    required_in_production=True,
    rotation_recommendation="Annual rotation.",
    validation_function=_validate_strong_secret,
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\core\secret_registry.py#L183-189

```
secret_registry.register(
    name="cookie_signing_key",
    description="HMAC key used for signing session and state cookies.",
    required_in_production=True,
    rotation_recommendation="Annual rotation.",
    validation_function=_validate_strong_secret,
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\core\secret_registry.py#L190-196

```
secret_registry.register(
    name="encryption_key",
    description="Symmetric encryption key for sensitive data at rest.",
    required_in_production=True,
    rotation_recommendation="Annual rotation with key wrapping.",
    validation_function=_validate_strong_secret,
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\core\secret_registry.py#L197-203

```
secret_registry.register(
    name="marzban_api_token",
    description="Bearer access token for communicating with the Marzban VPN provisioning node.",
    required_in_production=False,  # Conditional on PROVISIONING_ENABLED
    rotation_recommendation="Quarterly rotation.",
    validation_function=_validate_non_empty_secret,
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\core\secret_registry.py#L204-210

```
secret_registry.register(
    name="razorpay_key_id",
    description="Public API key identifier for Razorpay payment gateway.",
    required_in_production=False,  # Conditional on PAYMENTS_ENABLED
    rotation_recommendation="Annual rotation.",
    validation_function=_validate_non_empty_secret,
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\core\secret_registry.py#L211-217

```
secret_registry.register(
    name="razorpay_key_secret",
    description="Secret API key for Razorpay payment gateway order signing.",
    required_in_production=False,  # Conditional on PAYMENTS_ENABLED
    rotation_recommendation="Annual rotation.",
    validation_function=_validate_strong_secret,
)
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\core\secret_registry.py#L218-224

```
secret_registry.register(
    name="razorpay_webhook_secret",
    description="HMAC secret for verifying Razorpay webhook payload signatures.",
    required_in_production=False,  # Conditional on PAYMENTS_ENABLED and WEBHOOKS_ENABLED
    rotation_recommendation="Annual rotation.",
    validation_function=_validate_strong_secret,
)
```


**Tool Call: Search files for regex `x_forwarded_for|X-Forwarded-For|trust_proxy`**
Status: Completed

file://D:\My projects\VPN\OverREALITY\billing-server\app\rate_limit\middleware.py#L20-27

```
    """
    Middleware responsible strictly for:
    1. Client IP extraction (with configurable proxy trust: X-Forwarded-For / X-Real-IP).
    2. Request identification binding.
    3. Injecting X-RateLimit-* and Retry-After headers onto HTTP responses.
    
    Do NOT perform authentication or rate limit evaluations here.
    """
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\rate_limit\middleware.py#L33-44

```
        """
        Extract real client IP address.
        Only trusts X-Forwarded-For and X-Real-IP headers if settings.trust_proxy is True.
        Otherwise directly uses socket connection client host.
        """
        if getattr(settings, "trust_proxy", False):
            x_forwarded_for = request.headers.get("x-forwarded-for")
            if x_forwarded_for:
                # X-Forwarded-For format: client, proxy1, proxy2
                client_ip = x_forwarded_for.split(",")[0].strip()
                if client_ip:
                    return client_ip
```


**Tool Call: Search files for regex `record_event`**
Status: Completed

file://D:\My projects\VPN\OverREALITY\billing-server\app\security_hardening\audit.py#L94-98

```
        self._total_recorded = 0

    def record_event(
        self,
        event_type: str,
```


## Assistant

<thinking>
I've verified all three critical findings: the validation function is indeed never called anywhere in the codebase, the X-Forwarded-For leftmost trust vulnerability is exactly as described, and record_event appears to only be defined without any call sites. Let me check if there's an indirect invocation pattern I might have missed, like through the audit service.
</thinking>

**Tool Call: Read file `billing-server\deployment\production\deploy.sh` (lines 1-20)**
Status: Completed

```OverREALITY/billing-server/deployment/production/deploy.sh
     1	#!/usr/bin/env bash
     2	# Production Deployment Script for RealityTunnel Billing Server
     3	set -eo pipefail
     4	
     5	echo "── Starting RealityTunnel Production Deployment ──"
     6	
     7	# 1. Verify environment variables
     8	if [ -z "$POSTGRES_PASSWORD" ] or [ -z "$JWT_SECRET" ]; then
     9	    echo "ERROR: Required production environment variables (POSTGRES_PASSWORD, JWT_SECRET) are not set!"
    10	    exit 1
    11	fi
    12	
    13	export ENVIRONMENT=production
    14	export DEBUG=false
    15	export APP_VERSION=${APP_VERSION:-1.0.0}
    16	
    17	echo "1. Creating pre-deployment database backup..."
    18	python3 -m app.recovery.backup --create --reason "pre_deploy_${APP_VERSION}" || echo "Warning: Backup command failed or no local DB access; ensure external snapshots are active."
    19	
    20	echo "2. Pulling latest production Docker images..."

```


**Tool Call: Read file `billing-server\app\core\startup_validator.py` (lines 1-60)**
Status: Completed

```OverREALITY/billing-server/app/core/startup_validator.py
     1	"""
     2	app/core/startup_validator.py — Startup configuration validation & reporting (Phases 3.1.3, 3.1.5, 3.1.9).
     3	
     4	Enforces fail-fast startup validation before FastAPI accepts HTTP requests:
     5	  - Validates keypairs, database configuration, external gateways, secret lengths, and writable directories.
     6	  - Enforces production guards (rejection of placeholders, debug mode, test keys, localhost callbacks).
     7	  - Generates a structured startup Configuration Report with zero leaked secrets.
     8	"""
     9	from __future__ import annotations
    10	
    11	import logging
    12	import os
    13	import stat
    14	from dataclasses import dataclass, field
    15	from pathlib import Path
    16	from typing import Any
    17	
    18	from app.config import Settings, get_settings
    19	from app.core.feature_flags import FeatureFlags
    20	from app.core.fingerprint import compute_configuration_fingerprint
    21	from app.core.profiles import EnvironmentProfile, parse_environment_profile
    22	from app.core.secret_registry import secret_registry
    23	
    24	logger = logging.getLogger(__name__)
    25	
    26	
    27	class ConfigurationError(RuntimeError):
    28	    """Raised when startup configuration validation fails. Halts application boot immediately."""
    29	    pass
    30	
    31	
    32	@dataclass
    33	class ConfigurationReport:
    34	    status: str
    35	    checks: dict[str, bool] = field(default_factory=dict)
    36	    warnings: list[str] = field(default_factory=list)
    37	    production_checks: dict[str, bool] = field(default_factory=dict)
    38	    fingerprint: dict[str, Any] = field(default_factory=dict)
    39	
    40	    def to_string(self) -> str:
    41	        lines = [
    42	            "\n══════════════════════════════════════════════════════════════",
    43	            "            RealityTunnel Configuration Report                ",
    44	            "══════════════════════════════════════════════════════════════",
    45	            f" Status: {self.status.upper()}",
    46	            "──────────────────────────────────────────────────────────────",
    47	            " Configuration Status:",
    48	        ]
    49	        for name, ok in self.checks.items():
    50	            mark = "✓" if ok else "✗"
    51	            lines.append(f"   {mark} {name}")
    52	
    53	        if self.production_checks:
    54	            lines.append("──────────────────────────────────────────────────────────────")
    55	            lines.append(" Production Guards:")
    56	            for name, ok in self.production_checks.items():
    57	                mark = "✓" if ok else "✗"
    58	                lines.append(f"   {mark} {name}")
    59	
    60	        if self.warnings:

```


## Assistant

Both confirmed exactly as reported. Now let me check `main.py` quickly to confirm CORS/docs/audit-registration status, and check the `PurchaseRequestDTO.amount` isn't validated anywhere I might have missed (e.g. a pydantic validator or service-side guard), then compile the final report.

**Tool Call: Search files for regex `CORSMiddleware|docs_url|redoc_url|environment ==|startup_validator|audit_service`**
Status: Completed

file://D:\My projects\VPN\OverREALITY\billing-server\app\main.py#L19-29

```
from app.security_hardening import (
    SecurityHeadersMiddleware,
    InputValidationMiddleware,
    CSRFMiddleware,
    secret_rotation_service,
    audit_service,
    SecurityHardeningError,
    TLSValidationError,
    CSRFValidationError,
    InputValidationError,
    SecretRotationError,
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\main.py#L75-85

```
    """Manage startup / shutdown lifecycle."""
    logger.info("Billing server starting up…")
    from app.core.startup_validator import validate_startup_configuration
    validate_startup_configuration(settings)
    logger.info("Database URL: %s", settings.database_url_safe)
    scheduler = JobScheduler(AsyncSessionLocal)
    scheduler.start()
    app.state.scheduler = scheduler
    app.state.secret_rotation = secret_rotation_service
    app.state.audit = audit_service
    from app.performance.cache import get_cache
```


file://D:\My projects\VPN\OverREALITY\billing-server\app\main.py#L96-103

```
app = FastAPI(
    title="RealityTunnel Billing/Auth API",
    description="Billing & authentication backend for RealityTunnel VPN.",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)
```


**Tool Call: Search files for regex `request\.amount|\.amount\b`**
Status: Completed

file://D:\My projects\VPN\OverREALITY\billing-server\app\services\billing_service.py#L139-149

```
        """
        Initiate an order for a subscription purchase via PaymentService.
        Does NOT activate the subscription; activation occurs exclusively via verified webhooks.
        """
        plan = self.plan_service.get_plan(request.plan_id)
        amount_minor_units = request.amount if request.amount is not None else plan.price_minor_units

        payment = await self.payment_service.create_payment(

            account_id=account_id,
            amount_minor_units=amount_minor_units,
```


## Assistant

All findings confirmed with direct evidence. I now have everything needed to write the final comprehensive audit report.

---

# RealityTunnel Backend Security Audit Report
### Production Readiness Review — `billing-server`

---

## Executive Summary

**Overall Production Readiness Score: 3.5 / 10**

This codebase demonstrates unusually strong *security engineering craftsmanship* in isolated primitives: Ed25519 JWTs with strict algorithm/issuer/audience pinning, constant-time credential comparisons, timing-attack-resistant authentication, refresh-token rotation with replay detection, HMAC webhook verification, and a genuinely well-designed layered architecture (Router → Service → Repository, with clean domain boundaries between Payment/Subscription/Provisioning/Credential ownership).

However, the audit surfaced a **critical payment-tampering vulnerability that lets any authenticated customer pay an arbitrary (including near-zero) amount for a full-price subscription**, a **duplicate-active-subscription race condition** with no database-level guard, a **rate-limiting bypass via spoofed `X-Forwarded-For`**, and **several pieces of security infrastructure that exist in code but are never actually wired up or invoked** (secret-strength validation, security audit logging, key-permission checks). Individually, some of these are moderate; together, they indicate the security "theater" (docstrings, architecture comments, defensive-sounding code) is meaningfully ahead of what is actually enforced at runtime.

This system must **not** go live processing real payments in its current state. The payment-amount tampering bug alone is a direct, trivially exploitable revenue-loss vector. Most other issues are fixable in days, not weeks — but they must be fixed and re-verified before launch.

---

## Critical Findings

### C-1. Customer-controlled payment amount bypasses plan pricing (Payment Tampering)
- **Severity:** Critical | **Likelihood:** High (trivial, no special access needed) | **Impact:** Direct, unbounded revenue loss; full subscription entitlement for near-zero payment.
- **Files:** `app/services/billing_dtos.py` (`PurchaseRequestDTO.amount`), `app/services/billing_service.py::BillingService.purchase_subscription` (line 144), `app/services/payment/service.py::PaymentService.confirm_payment`.
- **Root cause:**
  ```python
  # billing_service.py
  plan = self.plan_service.get_plan(request.plan_id)
  amount_minor_units = request.amount if request.amount is not None else plan.price_minor_units
  ```
  `PurchaseRequestDTO.amount` is an optional, client-supplied integer with no server-side validation against the plan's authoritative price (`billing_dtos.py` line 79: `amount: int | None = Field(default=None, description="Optional custom amount in minor units; defaults to plan price if omitted")`). Any authenticated customer can call `POST /api/billing/purchase` with `{"plan_id": "pro", "amount": 100, "idempotency_key": "..."}` and receive a real Razorpay order for ₹1 instead of the plan price (e.g. ₹499). Razorpay will happily create and capture an order for whatever amount the *server* requests — and the server requests whatever the *client* sent.
  Compounding this, `PaymentService.confirm_payment` (verified directly) never cross-checks `verification.amount_minor_units` (fetched live from Razorpay) against `payment.amount_minor_units` stored at order-creation time — it only checks `verification.is_valid` (captured/authorized). There is no defense-in-depth backstop at confirmation time either.
- **Attack scenario:** A customer registers, calls `/api/billing/purchase` with `plan_id=pro`, `amount=100`, completes real payment of ₹1 via the generated Razorpay checkout, Razorpay sends a legitimately signed webhook for the captured ₹1 payment, `confirm_payment` activates a full 30-day "pro" subscription and provisions real VPN credentials — indistinguishable from a legitimate full-price purchase in every downstream system.
- **Fix:** Delete the `amount` field from `PurchaseRequestDTO` entirely (or ignore it server-side). Always derive `amount_minor_units = plan.price_minor_units` in `BillingService.purchase_subscription`. As defense-in-depth, add an explicit check in `PaymentService.confirm_payment` comparing the Razorpay-reported captured amount against `payment.amount_minor_units` and reject/flag on mismatch.

### C-2. Duplicate ACTIVE subscriptions via TOCTOU race (no DB-level uniqueness)
- **Severity:** Critical | **Likelihood:** Medium (requires concurrent payment confirmation for one account — plausible under webhook retries/duplicate purchase clicks) | **Impact:** Double entitlement, double provisioning, billing/ledger corruption.
- **Files:** `app/services/subscription_service.py::SubscriptionService.create_subscription`, `app/services/payment/service.py::PaymentService.confirm_payment`, `app/repositories/subscription_repository.py::get_active_for_account`, `app/models/subscription.py`.
- **Root cause:** The invariant "one active/trial/grace subscription per account" is enforced *only* in application code via:
  ```python
  existing_active = await self.repository.get_active_for_account(account_id, now, for_update=True)
  if existing_active:
      raise SubscriptionAlreadyActiveError(...)
  subscription = await self.repository.create(...)
  ```
  `SELECT ... FOR UPDATE` cannot lock a row that doesn't exist. When no active subscription currently exists, two concurrent transactions (e.g., two Razorpay webhook deliveries for two different orders on the same account, arriving within milliseconds under READ COMMITTED isolation) will both see zero rows, both pass the check, and both `INSERT`. No unique/partial-unique index exists on `subscriptions(account_id)` filtered by active-like statuses (confirmed absent in `app/models/subscription.py` and the corresponding Alembic migration).
- **Fix:** Add a Postgres partial unique index: `CREATE UNIQUE INDEX uq_subscriptions_one_active_per_account ON subscriptions (account_id) WHERE status IN ('TRIAL','ACTIVE','GRACE');` Mirror this in the SQLAlchemy model, generate a migration, and catch the resulting `IntegrityError` in `create_subscription` to translate it into `SubscriptionAlreadyActiveError` instead of a raw 500.

### C-3. Secret-strength validation framework is fully defined but never executed
- **Severity:** Critical | **Likelihood:** Certain (this is dead code today, not a race) | **Impact:** Weak/placeholder secrets (DB password, `secret_key`, `cookie_signing_key`, `encryption_key`, Razorpay secrets) can pass startup validation silently in production.
- **Files:** `app/core/secret_registry.py` (lines 38–52, 141–224), `app/core/startup_validator.py`.
- **Root cause:** Verified via project-wide search — `validation_function` (registered per-secret, e.g. `_validate_strong_secret`, `_validate_pem_key`, `_validate_non_empty_secret`) is assigned to every `SecretDefinition` but **never called anywhere in the codebase**. `startup_validator.py` reimplements a handful of ad-hoc inline checks for only `secret_key` and Razorpay keys, completely bypassing the registry's own enforcement for `postgres_password`, `cookie_signing_key`, `encryption_key`, etc.
- **Fix:** In `validate_startup_configuration`, iterate `secret_registry.get_all_definitions()` and, for every `required_in_production` secret, call `definition.validation_function(definition.value)`; fail startup (`ConfigurationError`) if it returns `False`.

### C-4. Security audit trail (`AuditService.record_event`) is never invoked — no audit log exists in practice
- **Severity:** Critical | **Likelihood:** Certain | **Impact:** No forensic trail for admin logins, admin actions, credential regenerations, or payment events; incident response and compliance (e.g. PCI-adjacent obligations for a payment-processing VPN service) are impossible.
- **Files:** `app/security_hardening/audit.py` (whole file — well-built, redaction-aware, described as recording `admin_login`, `admin_action`, `payment_event`, `credential_regeneration`, `device_registration/deletion`).
- **Root cause:** Verified via project-wide grep for `record_event(` — the only occurrence in the entire `app/` tree is the method's own definition. It is instantiated as a singleton, attached to `app.state.audit` in `main.py`, and its queue status is surfaced in `/health` — but nothing ever calls it. `total_events_recorded` will always read `0`.
- **Fix:** Wire `audit_service.record_event(...)` into `admin_auth.py` (login success/failure), `admin.py`/`admin_billing.py` (every write action), `credentials.py` (regenerate/revoke/restore), `webhooks.py`/`billing.py` (payment lifecycle events), and `devices.py` (register/deactivate). Persist to durable storage (a dedicated append-only table or external SIEM), not just an in-process buffer that is lost on restart.

### C-5. `deploy.sh` production secret-presence guard is broken (bash syntax error) and silently passes
- **Severity:** Critical | **Likelihood:** Certain (verified directly) | **Impact:** The documented "refuse to deploy without `POSTGRES_PASSWORD`/`JWT_SECRET`" safety gate never fires.
- **File:** `deployment/production/deploy.sh`, line 8: `if [ -z "$POSTGRES_PASSWORD" ] or [ -z "$JWT_SECRET" ]; then`.
- **Root cause:** `or` is not valid Bash inside/between `[ ]` tests. `[ -z "$POSTGRES_PASSWORD" ] or [ -z "$JWT_SECRET" ]` is parsed as a single malformed `[` invocation ("too many arguments"), returns a non-zero-but-still-"else"-taken result, so the script prints "OK" and continues deploying **regardless of whether the variables are set**. Verified experimentally by direct reproduction of the exact test. The only remaining backstop today is `docker-compose.prod.yml`'s `${VAR:?...}` required-variable syntax — this is incidental protection, not because the deploy script's own gate works.
- **Fix:** `if [ -z "$POSTGRES_PASSWORD" ] || [ -z "$JWT_SECRET" ]; then`. Also see H-1 — `JWT_SECRET` isn't even consumed by the application, so fix that mapping too.

---

## High Findings

### H-1. `JWT_SECRET` (and `MASTER_TOKEN_HASH`, `API_KEY`) required by ops tooling but never read by the application
- **Files:** `docker-compose.prod.yml` (`${JWT_SECRET:?...}`), `app/config.py` (`Settings` — no such field), `app/security/jwt_service.py`/`admin_jwt.py` (keys loaded from PEM files on disk, not env vars).
- **Impact:** Operators reasonably believe setting a strong `JWT_SECRET` secures JWT issuance; it does nothing (`extra="ignore"` on `SettingsConfigDict` silently discards it). The actual Ed25519 private key material has **no env-var/secrets-manager provisioning path** documented anywhere in `deployment/`.
- **Fix:** Remove the dead env vars from compose, and document/implement a real secure delivery mechanism for the Ed25519 PEM files (Docker secret, mounted encrypted volume, KMS-backed init container).

### H-2. Rate limiting and IP-based defenses are bypassable via spoofed `X-Forwarded-For`
- **File:** `app/rate_limit/middleware.py::RateLimitMiddleware._extract_client_ip` (lines 38–44), verified directly.
- **Root cause:** When `trust_proxy=True` (required for any real deployment behind nginx/Cloudflare), the code takes the **leftmost** entry of `X-Forwarded-For` — which is the original, client-supplied value in the standard append convention, not the proxy-verified hop. An attacker can send `X-Forwarded-For: <random-ip>` on every request.
- **Attack scenario:** Unlimited-rate credential stuffing against `/api/auth/login` and `/api/admin/login`, since every request appears to originate from a different, attacker-chosen IP, defeating per-IP throttling entirely.
- **Fix:** Only trust `X-Forwarded-For`/`X-Real-IP` when the immediate TCP peer is an allow-listed reverse-proxy IP, and take the **rightmost** untrusted-boundary hop, not the leftmost.

### H-3. Rate limiting is in-memory only — resets on restart, ineffective across replicas
- **File:** `app/rate_limit/backend.py` (`get_rate_limit_backend` — only `MemoryRateLimitBackend` exists, despite the abstraction being explicitly designed for Redis).
- **Impact:** Every redeploy resets all counters; horizontal scaling (the natural next step for this service) multiplies the effective rate limit by the replica count.
- **Fix:** Implement and wire a Redis-backed `RateLimitBackend` before any multi-replica deployment.

### H-4. `AccountRepository` has no row-locking support — lost-update race in admin subscription extension
- **Files:** `app/services/admin_account.py::AdminAccountService.extend_subscription` (and `suspend_account`/`activate_account`), `app/repositories/account_repository.py` (no `for_update` parameter anywhere, unlike every other repository).
- **Attack/failure scenario:** Two concurrent `extend_subscription` calls (double-click, or a retried automated billing job) both read the same stale `subscription_expires_at`, both compute `base + N days` from that same stale base, and the second write silently overwrites the first — one of the two extensions is lost with no error and no audit trail (compounded by C-4).
- **Fix:** Add `for_update: bool = False` to `AccountRepository.get_by_id`/`get_by_account_id` (matching every other repository), and acquire the lock before mutating within a single transaction.

### H-5. No `.dockerignore` — build context can bake `.env`/private keys into image layers
- **File:** absence of `.dockerignore` confirmed via search; `Dockerfile` does `COPY . .` from the full build context.
- **Impact:** `.gitignore` prevents secrets from being *committed* but has zero effect on `docker build`. If `dev_keys/` has been populated locally (happens automatically on first dev boot) or a `.env` exists in the build directory, both get baked into an immutable image layer, permanently extractable via `docker history`/`docker save`.
- **Fix:** Add a `.dockerignore` excluding `.env*`, `dev_keys/`, `.git/`, `backups/`, `*.pem`, `__pycache__/`, `tests/`.

### H-6. "Secure Key Permissions" startup check is a no-op stub that always reports success
- **File:** `app/core/startup_validator.py` (lines ~222–233) — the loop body is a bare `pass`; `prod_checks["Secure Key Permissions"] = True` is set unconditionally.
- **Impact:** Operators are told private key file permissions were verified when no check ever ran — false assurance in the startup report.
- **Fix:** Implement `os.stat(path).st_mode & 0o077 == 0` and fail the guard otherwise.

### H-7. Device registration/limit is decorative — not enforced at login or credential retrieval
- **Files:** `app/routers/auth.py::login` (binds tokens to any client-supplied `device_guid` with no call to `DeviceService.register_device` or any limit check), `app/routers/credentials.py`/`app/services/credential_service.py` (VPN credentials are issued per-**account**, gated only by `get_current_account`, with zero reference to `DeviceRepository` or device counts).
- **Impact:** The "max_devices" plan limit (`SubscriptionPlanService.device_limit_reached`) is only enforced on the separate, optional `POST /api/devices` endpoint. A customer (or anyone who obtains the master token) can call `/api/auth/login` with unlimited distinct `device_guid` values, never touching the device registry, and each resulting session can freely pull the shared VLESS/sing-box config from `/api/credentials`. Concurrent-session capping is deferred entirely to Marzban-side IP limiting (per the code's own comments) — which was not in scope to verify — meaning the "device limit" billing feature is bypassable at the billing-server layer.
- **Fix:** Either require successful `register_device` (with limit enforcement) as a precondition of `login` issuing tokens for a given `device_guid`, or explicitly document that device count is cosmetic and concurrent-IP enforcement is the real technical control — and verify that control actually exists and is configured on the Marzban side (Needs verification — out of scope of this codebase).

---

## Medium Findings

### M-1. `PaymentService.create_payment` TOCTOU causes duplicate external Razorpay orders
- **File:** `app/services/payment/service.py::create_payment`. Same "lock a nonexistent row" pattern as C-2: two concurrent requests with the same `idempotency_key` (e.g., client retry after timeout) can both see no existing payment and both call `provider.create_order` before either commits. The DB-level `unique=True` on `idempotency_key` prevents a duplicate *row*, but a duplicate *external* Razorpay order has already been created, and the losing request receives a `DuplicateEntityError` instead of the payment it expected.
- **Fix:** Serialize per-idempotency-key with a Postgres advisory lock (`pg_advisory_xact_lock(hashtext(idempotency_key))`) before the existence check, or pre-insert a claim row inside the same transaction.

### M-2. Scheduler has no distributed lock — latent duplicate-execution risk if scaled
- **Files:** `app/scheduler.py`, `app/services/lifecycle_job_service.py::run_credential_rotation_job` / `run_failed_provision_retry_job`. Both discovery queries (`get_all_active_or_suspended`, `get_pending_retries`) run **without** `for_update`/`SKIP LOCKED`, and `rotate_user_credentials` does not re-validate the rotation cutoff after acquiring its row lock. **Currently dormant** because `Dockerfile` uses `--workers 1` and `docker-compose.prod.yml` runs a single replica — but nothing in the code prevents a natural HA scale-out from immediately triggering duplicate Marzban credential rotations (silently invalidating a customer's just-issued VLESS UUID a second time) or duplicate provisioning API calls.
- **Fix:** Add `pg_try_advisory_lock` (or `SELECT ... FOR UPDATE SKIP LOCKED`) gating every scheduled job, and re-check state after acquiring per-row locks.

### M-3. Remote Marzban mutation always precedes local durable commit — no compensation on crash
- **File:** `app/services/provisioning/service.py` (`provision_subscription`, `reactivate_subscription`, `rotate_user_credentials`, etc. all call the remote provider before committing locally). `reactivate_subscription` in particular: if the process crashes between the remote `unsuspend_user` succeeding and the local commit, the local `provisioning_state` stays `SUSPENDED` forever (no scheduled reconciliation job exists), and `CredentialService.get_credentials` short-circuits on the *stale local* state before ever consulting live Marzban status — permanently denying a paying, reactivated customer until manual admin intervention.
- **Fix:** For non-idempotent remote operations (especially credential rotation and reactivation), write a pending/intent record transactionally before the remote call, and either make the read path prefer live remote status on disagreement, or add a scheduled reconciliation sweep.

### M-4. SAST/dependency scanning in CI is purely advisory
- **File:** `.github/workflows/security.yml` — Bandit and pip-audit steps both end in `|| true`, forcing success regardless of findings. Only the Trivy scan actually gates the build.
- **Fix:** Remove `|| true`; gate on severity threshold (e.g., fail on HIGH/CRITICAL).

### M-5. GitHub Actions pinned to mutable tags, not commit SHAs
- **Files:** All `.github/workflows/*.yml` (`actions/checkout@v4`, etc.). A compromised/hijacked upstream tag could execute arbitrary code in CI with access to publish/release secrets.
- **Fix:** Pin to full commit SHAs; use Dependabot/Renovate to update.

### M-6. `/metrics` unauthenticated and unthrottled by default
- **Files:** `app/config.py` (`metrics_auth_required: bool = False`, never overridden in prod compose), `app/rate_limit/limiter.py` (metrics explicitly exempted from rate limiting).
- **Fix:** Default `True` in production, or restrict at the reverse-proxy layer to monitoring infra only.

### M-7. Interactive API docs enabled unconditionally, including production
- **File:** `app/main.py` (`docs_url="/docs"`, `redoc_url="/redoc"`, no environment gate). Discloses the full admin API surface/schema to the internet.
- **Fix:** `docs_url=None if settings.environment == "production" else "/docs"` (same for redoc/openapi.json), or gate behind admin auth.

### M-8. Production port published to all host interfaces with only a checklist (not a technical control) requiring TLS termination
- **File:** `docker-compose.prod.yml` (`ports: ["${PORT:-8080}:8080"]`, no `127.0.0.1:` binding, no bundled reverse proxy). A misconfigured/incomplete deployment serves the API — including `master_token` and refresh tokens in JSON bodies — in plaintext HTTP directly to the internet.
- **Fix:** Bind to loopback and ship a reference TLS-terminating reverse proxy in the same compose stack.

### M-9. No `cap_drop`/`no-new-privileges` on production container
- **File:** `docker-compose.prod.yml`. Good baseline (`read_only: true`, non-root, resource limits) but retains full default Linux capabilities.
- **Fix:** Add `cap_drop: ["ALL"]` and `security_opt: ["no-new-privileges:true"]`.

### M-10. Duplicate retry-queue rows possible under concurrent provisioning failures
- **File:** `app/services/provisioning/service.py::_maybe_enqueue_retry`, `app/models/provisioning_retry.py` (no unique constraint on `account_id`+`PENDING`). Self-healing due to idempotent downstream fallback, but produces redundant API calls and log noise.
- **Fix:** Partial unique index `UNIQUE (account_id) WHERE status = 'PENDING'`.

---

## Low Findings

- **L-1.** Internal exception text (`str(exc)`) can propagate into HTTP `detail` fields from `admin_billing.py`/`credentials.py` error translation paths, risking minor schema/constraint-name disclosure (not secrets). *Files:* `app/services/credential_service.py`, `app/routers/credentials.py`.
- **L-2.** `MemoryCache` (`app/performance/cache.py`) has lazy-only expiration and no `maxsize`/eviction; currently safe because the cache key whitelist is small and bounded, but a future widening of `ALLOWED_CACHE_PREFIXES` to per-account data would create unbounded memory growth.
- **L-3.** Dev `docker-compose.yml` publishes Postgres `5432` to the host for migration convenience — fine for dev, but risks copy-paste reuse into a production-adjacent context.
- **L-4.** CI lint steps (`ruff`, `black`, `mypy`) are all `|| true` — advisory only, reinforcing the pattern that CI is decorative rather than a real gate (see M-4).
- **L-5.** GitHub Actions workflows lack explicit least-privilege `permissions:` blocks (only `release.yml` declares one, and it's workflow-scoped rather than job-scoped).
- **L-6.** `logger.info("Retrieving VPN credentials for account_id=%s", account.id)` (`app/routers/credentials.py`) logs the internal database UUID. This is not the human-readable Account ID or a secret, but it deviates from the router's own stated "never log account identifiers" invariant — needs verification on whether internal UUIDs are considered in-scope for that invariant.

---

## Architecture Review

The layered design (Router → Service → Repository, with Payment/Subscription/Provisioning/Credential ownership strictly separated, and no router or payment provider ever touching Marzban directly) is genuinely well-conceived and is largely honored in practice — this is a real strength, not just documentation. Dependency injection via FastAPI `Depends()` chains correctly wires singletons for stateless services (JWT engines) and per-request instances for session-bound services.

The architecture's weakness is that several of its own stated invariants are **aspirational rather than enforced**: the docstring-level promises ("zero-secret logging," "immutable audit logging," "production guards reject weak secrets") are implemented as real, well-written code — but critical wiring steps were skipped (C-3, C-4), so the architecture *looks* like defense-in-depth without *being* defense-in-depth in three separate subsystems. This is a pattern, not an isolated oversight, and warrants a full "is this code actually called?" pass across the rest of `security_hardening/` and `core/` before launch.

The "device" domain model is also architecturally incomplete: `DeviceService`/`DeviceRepository` implement real ownership and limit-enforcement logic, but the `login`/`credentials` code paths that actually grant access don't consult it (H-7), so a whole subsystem exists without being load-bearing for security or billing enforcement.

---

## Concurrency Review

Row-level locking (`SELECT ... FOR UPDATE`) is used consistently and correctly for **mutations targeting an existing, identifiable row** (refresh token rotation, single-payment confirmation, single-subscription state transitions, single-device operations) — this is a real strength and was verified across `refresh_tokens.py`, `payment/service.py`, `subscription_service.py`, and `device.py`.

The systemic weakness is the **"SELECT FOR UPDATE on a query that may return zero rows" anti-pattern**, which appears in at least three independent places (C-2 subscription creation, M-1 payment idempotency-key creation, M-10 retry-queue enqueue) — `FOR UPDATE` provides no serialization guarantee when there's nothing to lock yet, and none of these paths are backed by a DB-level unique constraint that would convert the race into a safe, catchable `IntegrityError`. This is the single most important class of bug to fix before launch, because it directly enables both revenue-affecting duplicate subscriptions and duplicate external payment-gateway orders.

The scheduler (`app/scheduler.py`) itself is correctly implemented for graceful shutdown (tracked tasks, proper `CancelledError` handling, exceptions in one iteration don't kill the loop) and is safe under the *current* single-worker deployment, but has no distributed-lock primitive, making it a landmine for the first horizontal-scaling change (M-2).

Async correctness is otherwise solid: no fire-and-forget `asyncio.create_task` calls with swallowed exceptions were found, session lifecycle (`expire_on_commit=False`, rollback-on-error in `BaseRepository`) is consistent, and the Alembic migration chain is linear with no drift.

---

## Authentication Review

This is the strongest part of the codebase. Verified directly:
- Ed25519 (EdDSA)-only algorithm allowlist on both customer and admin JWT verification (no algorithm-confusion risk; `jwt.decode(..., algorithms=["EdDSA"])` explicit).
- Fully separate signing keys, issuers, and audiences for customer vs. admin tokens — a customer token cannot pass admin verification and vice versa (verified in `jwt_service.py` and `admin_jwt.py`).
- Zero clock-skew leeway, explicit `require` list for all claims, clean exception translation with no information leakage between failure modes exposed to the client (all collapse to a generic 401).
- Account-enumeration/timing-attack defense in `AuthenticationService.authenticate` via a dummy-hash constant-time comparison when the account doesn't exist — correctly implemented and reasoned about.
- Refresh Token Rotation is textbook-correct: `SELECT ... FOR UPDATE` on the *existing* token row before rotation (this one is safe because the row being locked already exists), atomic revoke-old+insert-new in one transaction, and genuine replay detection that mass-revokes all sessions when a revoked token is reused — with the important, deliberate distinction that an *unknown* token does not trigger mass revocation (preventing a DoS where an attacker logs out victims by guessing random strings).
- Master tokens and refresh tokens are 256-bit CSPRNG values, correctly hashed with SHA-256 (justified — high-entropy machine secrets, not passwords) and compared with `hmac.compare_digest`.

The one real gap (H-7) is that `device_guid` binding at login time is not validated against the device registry at all, making the "device limit" feature non-load-bearing for actual access control.

---

## Authorization Review

Verified across every admin router (`admin.py`, `admin_billing.py`, `admin_auth.py`, `admin_recovery.py`): every single endpoint declares either `Depends(get_current_admin)` (read) or `Depends(require_super_admin)` (write), consistently matching the documented invariant in the file headers. No endpoint was found using a customer dependency where an admin one was required, or vice versa. `require_super_admin` correctly checks `admin.is_super_admin` and raises 403.

Customer-side IDOR protection (`billing.py::get_payment`) is implemented at the service layer via account-scoped lookups, and the billing router's own comment ("Anti-IDOR: Account A cannot read Account B's resources") was verified to hold in `PaymentService.get_account_payment`. Device endpoints (`devices.py`) correctly verify per-device ownership against `current_account.id` before any read/write (`DeviceService._get_and_verify_ownership`).

No horizontal or vertical privilege escalation path was found in the routers reviewed. The main authorization-adjacent gap is architectural, not a bypass: the device-limit business rule (H-7) is enforced at one endpoint but not at the endpoints that actually matter for access.

---

## Payment Review

The webhook signature verification (`RazorpayProvider.verify_webhook`) is correctly implemented with HMAC-SHA256 and `hmac.compare_digest` — no timing attack, no signature bypass. `PaymentService.confirm_payment` correctly locks the payment row and treats an already-`PAID` payment as an idempotent no-op, which defends against duplicate webhook delivery **for the same order** (Razorpay's documented at-least-once webhook retry behavior is handled correctly for this specific case). It also re-verifies payment status via a live `fetch_payment` API call rather than trusting the webhook payload alone — good defense-in-depth.

However, the payment domain has the most severe issue in this entire audit (C-1: client-controlled amount) and the systemic TOCTOU pattern described above (C-2, M-1) that can produce duplicate subscriptions/orders under concurrent confirmation. There is also no amount cross-check between the order-creation-time amount and the confirmed-capture amount, which would have been an independent mitigation for C-1 even if the DTO issue weren't present.

---

## Provisioning Review

The provisioning subsystem is well-designed for the common cases: deterministic Marzban usernames plus an explicit `ProvisioningConflictError` → fallback-to-update path make concurrent first-time provisioning self-healing, and DB-level unique constraints on `account_id`/`remote_user_id`/`marzban_username` prevent duplicate rows even when the remote call races. The retry queue has a genuine bounded-retry-with-backoff-and-dead-letter design (5 attempts, exponential backoff, terminal `FAILED` state) — there is no infinite retry loop.

The residual risk is the "remote-mutation-before-local-commit" ordering used throughout (M-3), which is a real but narrow-window (crash-only) risk for most operations because they're idempotent on retry — except for **credential rotation and reactivation**, which are not idempotent and can produce a permanently stuck denial-of-service against a paying customer if the crash window is hit. There is no automated reconciliation job to self-heal this divergence; it currently requires manual admin action via the sync endpoint.

Zero-secret-logging discipline was verified line-by-line across the provisioning and credential code paths — no VLESS URIs, REALITY keys, or Marzban credentials were found interpolated into any log statement.

---

## Docker Review

Baseline container hardening is genuinely good and was verified directly: non-root user (`USER billing`, uid 1001), `read_only: true` root filesystem with `tmpfs` for `/tmp`, `HEALTHCHECK` present, no secrets in build `ARG`s, resource limits on both services, and Postgres correctly isolated on an `internal: true` Docker network with no published ports in the production compose file. These are not trivial to get right and the team clearly put effort in.

The gaps are: no `.dockerignore` (H-5, real risk of baking secrets into image layers), no `cap_drop`/`no-new-privileges` (M-9, defense-in-depth gap), the production port bound to all interfaces with TLS termination enforced only by a checklist rather than a technical control (M-8), and the broken deploy-script safety gate (C-5). None of these are exotic — they're the kind of thing a pre-launch checklist should catch.

---

## CI/CD Review

The pipeline has the right *shape* (lint, type-check, SAST, dependency audit, container scan, SBOM, cosign signing) but several of the gates that matter most for a payment-processing service are non-functional: SAST and dependency scanning are `|| true` (M-4), meaning a hardcoded credential or a critical CVE in a dependency would not block a merge. Actions are pinned to mutable tags rather than SHAs (M-5), which is a live supply-chain risk given recent real-world GitHub Actions compromises. No `pull_request_target` misuse was found, and secrets are not exposed to fork PRs by default — that part is safe.

---

## Production Readiness

**Answer: NO.**

This system should not be deployed to process real payments today. The combination of C-1 (arbitrary customer-controlled payment amount), C-2 (duplicate subscription race), and C-5 (broken deploy-time secret guard) represents direct, exploitable financial and operational risk with no compensating control anywhere else in the stack. C-3 and C-4 mean that if something does go wrong, there will be materially less audit trail and secret-strength assurance than the codebase's own documentation claims — which will slow down incident response precisely when it matters most.

None of these are architecturally hard to fix. The underlying design is sound, and most fixes are localized (one field removal, one index, one bash operator, a handful of missing function calls). A realistic path is: fix all Critical and High findings, add the recommended DB constraints, re-run the full test suite plus new tests explicitly covering the price-tampering and race-condition scenarios, and re-audit before considering launch.

---

## Prioritized Fix List

1. **C-1** — Remove client-controlled `amount` from purchase flow; always price from plan server-side; add amount cross-check in `confirm_payment`.
2. **C-5** — Fix `deploy.sh` bash syntax (`||` not `or`); remove/rewire dead `JWT_SECRET` env var (H-1).
3. **C-2** — Add partial unique index for one-active-subscription-per-account; same pattern for M-1 (payment idempotency) and M-10 (retry queue).
4. **H-2** — Fix `X-Forwarded-For` trust logic (rightmost trusted hop only).
5. **C-3** — Wire `validation_function` calls into `startup_validator`.
6. **C-4** — Wire `AuditService.record_event` into every admin/payment/credential mutation path; persist durably.
7. **H-4** — Add row-locking to `AccountRepository`; fix lost-update race in admin subscription extension.
8. **H-3** — Implement Redis-backed rate-limit storage before any horizontal scaling.
9. **H-5 / M-9** — Add `.dockerignore`; add `cap_drop`/`no-new-privileges` to prod compose.
10. **H-6** — Implement the actual key-permission check (currently a no-op stub).
11. **H-7** — Decide and enforce: either gate login/credential issuance on device registration, or explicitly document and verify Marzban-side concurrent-IP enforcement as the real control.
12. **M-2 / M-3** — Add distributed locking to scheduler jobs before any scale-out; add reconciliation for non-idempotent provisioning operations (credential rotation, reactivation).
13. **M-4 / M-5** — Make CI security gates actually fail the build; pin Actions to SHAs.
14. **M-6 / M-7 / M-8** — Auth-gate `/metrics`, disable `/docs` in production, bind the API to loopback behind a real reverse proxy.
15. **Low findings** — address opportunistically; none block launch on their own.
