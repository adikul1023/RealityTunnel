# RealityTunnel — Privilege Boundary Design

Status: **Approved with modifications. Implementation may begin once the
remaining open items in §9 are settled during Phase 2 (they are
prototyping tasks, not blockers to starting Phase 1).**
No code changes are included in or implied by this document itself.

## Revision note (approval)

This revision incorporates five specific modifications requested at
approval time, in addition to the original draft:

1. Service account is no longer assumed to be `LocalSystem` — §3, §7
   (Phase 2), §8, and §9 now treat it as an empirical least-privilege
   prototyping task, with `LocalSystem` demoted to a documented fallback.
2. The named-pipe ACL + Windows security token/impersonation check is now
   explicit as the *primary, load-bearing* trust boundary — §4.1 and §4.4
   — with the image-path/code-signature check reframed as defense in
   depth that must never be the sole gate.
3. Configuration ownership is now total and one-directional — §4.6 —
   `config.template.json` moves entirely into the service's install
   payload and is removed from the UI project (§7 Phase 3); the UI never
   writes anything `sing-box` consumes.
4. Version negotiation (`Hello`) is now a hard, unconditional gate — §4.3
   — no other message type, including `Ping`, is accepted before it
   succeeds, and no privileged verb is reachable without it.
5. `IVpnBackend` is explicitly pinned to four members with no speculative
   additions — §8.

Additionally, per the reviewer's architectural suggestion, §5 now
describes the service's internal model as **desired-state reconciliation**
rather than one-shot imperative command execution (new §5.1), so the
service itself detects and recovers from a crashed `sing-box` process
without the UI having to re-issue `Connect`. This did not require adding
any wire message types, so it doesn't conflict with modification 5 above.

## 0. Why this document exists

Startup investigation (see prior debugging session, native stack traces
captured with WinDbg/`cdb.exe`) proved — not by correlation, but by a
controlled A/B comparison of symbol-resolved native stacks — that running
`RealityTunnel.exe` with `requireAdministrator` causes an unhandled
`E_FAIL` inside `Microsoft.UI.Xaml.dll`'s launch-activation path, which
WinUI3 escalates to `FailFastWithStowedExceptions` (`0xC000027B`). This
matches a previously filed, unresolved Microsoft issue
(`microsoft/microsoft-ui-xaml#3046`, labeled `product-winui3` +
`appModel-win32`).

**This is treated as a platform limitation. We are not going to keep
trying to make the elevated WinUI3 process start. Instead, `RealityTunnel.exe`
becomes a fully unelevated UI process, and a separate privileged component
performs the small set of operations that genuinely require Administrator
rights.**

## 1. Goals

- `RealityTunnel.exe` never requests elevation. `app.manifest` reverts to
  `asInvoker`.
- Only the following operations run elevated: starting/stopping
  `sing-box`, creating the TUN adapter, changing routes/DNS/firewall.
  Everything else — login, JWT, device management, config fetch, UI,
  settings, logs, notifications — stays in the unelevated UI process.
- Least privilege: the privileged component exposes a small, explicit,
  closed set of operations. It never executes arbitrary commands supplied
  by the UI.
- No change to backend APIs, authentication, provisioning, or subscription
  logic. Those are explicitly out of scope.

## 2. Current state (baseline for the migration plan)

For reference, here is exactly what exists today and which parts are
privileged:

| Component | File | Needs admin today? |
|---|---|---|
| `XrayController.Start/Stop` | `XrayController.cs` | **Yes** — launches `sing-box.exe`, which opens a TUN device (wintun) |
| `XrayController.SetupRoutes/TeardownRoutes` | `XrayController.cs` | **Yes** — `netsh interface ip set address/dns`, `route add/delete` |
| `VpnSessionManager` (connect/retry/disconnect orchestration) | `Services/VpnSessionManager.cs` | No — pure orchestration/state, delegates to `XrayController` |
| `ConfigurationProvider` (fetch/cache `VpnProfile`) | `Services/ConfigurationProvider.cs` | No — HTTP + local cache |
| `AuthenticationService`, `TokenService`, `LicenseService`, `DeviceHeartbeatService`, `OracleApiClient` | `Services/*.cs` | No — HTTP/JWT only |
| `SecureStorageService` | `Services/SecureStorageService.cs` | No — DPAPI `CurrentUser` scope, writes to `%LocalAppData%` |
| `TrayIcon`, `MainWindow`, `App` | root | No — pure Win32/WinUI UI |

The only genuinely privileged surface in the entire app is inside
`XrayController`: launching `sing-box.exe` and running `netsh`/`route`.
Everything else already runs fine unelevated. This materially shrinks the
scope of the redesign — we are not moving "the VPN logic," we are moving
one class's worth of OS-privileged calls.

## 3. Architecture options

### Option A — Dedicated Windows Service

A service (e.g. `RealityTunnelHelper`) installed once (by the installer),
running under a service account determined by the least-privilege
prototyping process in §9 (starting point: a virtual service account in
`Network Configuration Operators`, not `LocalSystem`), started
automatically at boot, exposing the named-pipe IPC described in §4.

### Option B — On-demand elevated helper executable

A small executable, launched only when a privileged operation is needed,
elevated via a single UAC prompt (or a scheduled task configured for
highest privileges, to avoid repeated prompts), exiting when idle.

### Comparison

| Dimension | Option A: Service | Option B: On-demand helper |
|---|---|---|
| **Security** | Runs continuously under a privileged service account — a larger standing attack surface than a transient process, but the account is scoped to the least privilege that works (§9, not automatically `LocalSystem`), and the IPC boundary is the *only* thing exposed to the UI regardless of account, tightly scoped (ACL'd pipe, explicit verbs). | Only exists transiently while a privileged op is running — smaller time-window of privilege, but each invocation is a fresh elevation path (UAC or scheduled task) that itself becomes an attack surface to get right every single time. |
| **Reliability** | Keeps running if `RealityTunnel.exe` crashes; can detect and clean up an orphaned TUN adapter/routes left behind by a UI crash. | If the helper is killed mid-operation (or the UI crashes at the wrong moment), routes/TUN adapters can be orphaned with nothing left running to clean them up. |
| **Startup time** | Service starts at boot (or on first use, `SERVICE_DEMAND_START`); connecting to it is just opening a pipe — fast, no elevation dialog on the connect path. | Every cold connect needs to spin up a new elevated process; if done via UAC, that's an interactive prompt the user sees every time unless a scheduled-task workaround is used (fragile, and itself a documented UAC-bypass pattern security tooling flags). |
| **Windows integration** | First-class SCM integration: auto-restart on failure (`sc failure` / `ServiceController`), starts before user logon if needed, no dependency on a signed-in interactive session. | No SCM integration; existence is tied to whatever launched it. Doesn't fit the Windows service model for "always-available background capability." |
| **Update process** | Installer stops the service, replaces the binary, restarts it — same pattern used for every other Windows service-based product. | Simpler in one sense (no service lifecycle to manage) but you still need to replace the exe safely; since it's launched per-operation there's less risk of a locked file during update. |
| **Crash recovery** | SCM can auto-restart the service (`SC_ACTION_RESTART`); the service can detect a UI crash (pipe disconnect) and tear down the tunnel/routes itself. | No equivalent — recovery logic would need to live in the UI, which is exactly the untrusted/lower-privilege side we're trying to keep thin. |
| **Maintainability** | One long-lived process with a clear lifecycle; state (is sing-box running? what routes did we add?) lives in one place, owned by the service itself, not reconstructed each time. | State must be persisted somewhere between invocations (what routes are currently active?) since the process doesn't stay alive — adds complexity right back in. |
| **IPC complexity** | Same either way — named pipes, same protocol. No difference. | Same. |
| **Deployment** | Installer registers the service (`sc create` / `InstallUtil`-equivalent via `ServiceInstaller` or the installer's native service support). One extra install step, well-understood. | No service registration, but needs a reliable elevation mechanism wired into the installer/first-run flow anyway (scheduled task creation, or repeated UAC). |
| **Code signing** | Same signing requirement as any other privileged binary; a service binary is signed once and doesn't change identity across invocations. | Same signing requirement, but signature/identity gets re-validated by UAC on every elevation, and a scheduled-task-based bypass is the kind of pattern security software (and some AV heuristics) specifically flags. |
| **User experience** | Zero prompts after install. Connect/disconnect feels instant and no different from any other "always ready" VPN client (NordVPN, ProtonVPN, etc. all use a service). | Either a UAC prompt on every connect (unacceptable for a commercial product) or a scheduled-task trick to avoid it (which is fragile, and is literally the kind of workaround we just discovered *doesn't even reliably work* — creating a task with `/RL HIGHEST` itself requires an already-elevated caller, as we proved directly during this investigation). |

### Recommendation: **Option A — dedicated Windows Service**

This isn't a default "services are best practice" answer — it's specifically
because of two things we already know about RealityTunnel:

1. **We already tried the on-demand-elevation path and hit a dead end.**
   During the crash investigation, creating a scheduled task with
   `/RL HIGHEST` (the standard technique to get elevation without a UAC
   prompt) failed with **Access Denied** precisely because the caller
   wasn't already elevated — the same chicken-and-egg problem an on-demand
   helper would face every time it needs to reappear after being closed.
   A service sidesteps this entirely: it's granted its privilege once,
   at install time (which already requires admin, same as any installer),
   and then simply *is* running when the UI needs it.

2. **VPN clients need cleanup guarantees a one-shot helper can't give.**
   If `RealityTunnel.exe` crashes while connected, something has to notice
   and tear down the TUN adapter and routes — otherwise the user is left
   with a broken network configuration and no VPN icon to fix it from. A
   service that outlives the UI is the only one of the two options that
   can own that responsibility. An on-demand helper that exits after each
   operation has nothing left running to do this.

Given RealityTunnel is a commercial product where "connect" needs to feel
instant and "my Wi-Fi broke after the app crashed" is not an acceptable
support ticket, Option A is the correct fit, not just the conventional one.

**Service account is a separate decision from service-vs-helper, and is
not settled by this recommendation.** Choosing a service only decides
*that* something long-lived and privileged exists — it says nothing about
how much privilege that thing needs to hold. See §9 for the account
selection process, which is deliberately treated as an empirical
prototyping task, not a default to `LocalSystem`.

## 4. IPC protocol design

**Threat model:** the UI process (`RealityTunnel.exe`) is treated as
untrusted input to the service. It runs at Medium integrity, may be
running arbitrary user-installed software alongside it, and could in
principle be compromised. The service must never execute anything the UI
asks for beyond a fixed, explicit set of verbs, and must independently
validate every request.

### 4.1 Transport

Named pipe: `\\.\pipe\RealityTunnelHelper`

- Pipe created by the service with an explicit security descriptor:
  - `GENERIC_READ | GENERIC_WRITE` granted only to the **interactively
    logged-on user's own SID** (obtained by the service by looking at the
    session's logon SID, not to `Everyone`/`Authenticated Users` broadly)
    and to `BUILTIN\Administrators`.
  - No access for `ANONYMOUS LOGON`, no access for remote connections
    (`PIPE_REJECT_REMOTE_CLIENTS` is set unconditionally — this pipe is
    local-machine-only).
- **Primary trust boundary — must hold on its own, with nothing else:**
  the pipe ACL above, combined with `ImpersonateNamedPipeClient` and an
  inspection of the caller's Windows security token (session ID, user SID,
  the fact that the token belongs to an interactive logon at all). If the
  ACL and token checks were the *only* checks the service ever performed,
  that must already be sufficient to safely accept the connection. Nothing
  described below is allowed to be the thing standing between an untrusted
  caller and a privileged operation.
- **Defense in depth — useful, but never load-bearing on its own:** the
  service additionally checks (via `QueryFullProcessImageName` off the
  client PID obtained through `GetNamedPipeClientProcessId`) that the
  connecting binary path is the installed `RealityTunnel.exe`, code-signed
  with the expected certificate (see §4.7). This check can be skipped,
  fail open on an edge case, or be defeated by a sufficiently privileged
  local attacker (who, by definition, could also just attack the pipe ACL
  layer directly) without changing the fact that the ACL + token check
  above is what actually protects the service. It exists to catch the
  case of a *different, unexpected, but still same-user* process
  connecting to the pipe — not as the authentication mechanism itself.

### 4.2 Framing and message format

Length-prefixed JSON (simple, debuggable, adequate at this message rate —
this is a control channel, not a data plane; sing-box's actual traffic
never goes through this pipe):

```
[4 bytes: little-endian UInt32 message length[
[N bytes: UTF-8 JSON payload]
```

Every message (both directions) carries a common envelope:

```json
{
  "protocolVersion": 1,
  "requestId": "b3f1...-uuid",
  "issuedAtUtc": "2026-07-20T18:32:00Z",
  "type": "Connect",
  "payload": { ... }
}
```

### 4.3 Protocol versioning

- **`Hello` is mandatory and version negotiation happens before anything
  else, with no exceptions.** The service's read loop, on a fresh
  connection, accepts exactly one message type: `Hello`. Any other
  message type received first is a protocol violation and the connection
  is closed immediately — there is no "skip the handshake" path, not even
  for `Ping`.
- `protocolVersion` is checked as part of that `Hello` exchange. If the
  service doesn't support the UI's version (or vice versa — an old service
  talking to a newer UI after a partial update), the connection is
  rejected with a typed `VersionMismatch` error and closed. **No session
  token is issued, and therefore no privileged verb in §4.6 can ever be
  reached, until `Hello` succeeds.** This makes version negotiation a hard
  gate rather than a soft check the implementation could accidentally
  bypass later.
- The service supports at most the current and immediately previous
  protocol version, to keep the surface small; anything older is rejected
  outright ("update RealityTunnel to continue").

### 4.4 Authentication & authorization

Two layers, both mandatory:

1. **Transport-level (who can even connect):** the pipe ACL + Windows
   security token/impersonation check from §4.1. This alone answers "is
   this our own interactive user, on this machine" and is the layer that
   must never be bypassed. The image-path/signature check from §4.1 rides
   along on top of this as defense in depth, not as a substitute for it.
2. **Session-level (is this connection allowed to ask for this verb):**
   after `Hello`, the service issues a short-lived **session token**
   (random 256-bit value, held only in memory, never persisted) bound to
   that specific pipe connection. Every subsequent request on that
   connection must be correlated to that session — this is not for
   cross-process security (the pipe already gives us that) but to make
   sure a stale/leaked `requestId` from a previous connection can't be
   replayed into a new one.

There is no notion of "logging in" to the helper beyond this — the helper
does not know about JWTs, accounts, or subscriptions. That stays entirely
in the UI (§6). The helper only cares "is this a legitimate, current
connection from our own UI," not "is this user entitled to a VPN plan."

### 4.5 Replay protection

- Every request carries a monotonically increasing `sequence` number per
  connection (not per protocol — resets to 0 on each new pipe connection).
  The service rejects any request whose `sequence` is not exactly
  `lastSeenSequence + 1` for that connection. This makes replaying a
  captured request (even from the same connection's traffic) impossible
  without also replaying everything after it in order, and a stale
  connection's messages can never be replayed into a new session because
  the session token (§4.4) differs.
- `issuedAtUtc` must be within a small clock-skew window (e.g. ±30s) of
  the service's own clock; anything outside that is rejected. This is a
  secondary defense, not the primary one — sequence numbers are the real
  protection; the timestamp check mainly guards against a very old,
  somehow-replayed message on a hypothetically hijacked connection.

### 4.6 Message types (the entire protocol surface)

No generic "execute" verb exists. The service understands exactly these
message types, each with a fixed, strongly-typed payload schema:

| Type | Direction | Purpose |
|---|---|---|
| `Hello` | UI → Service | First message on every connection. Carries `protocolVersion`, UI process ID (for the image-path check), and receives the session token in response. |
| `Connect` | UI → Service | Payload: the already-fetched `VpnProfile` (server host/port, UUID, SNI, public key, short ID) *and nothing else* — no file paths, no command strings, no template content, no config blob of any kind. Sets the service's **desired state** to `Connected(profile)`; see §5.1. |
| `Disconnect` | UI → Service | No payload. Sets desired state to `Disconnected`. Idempotent — safe to call even if nothing is connected. |
| `GetStatus` | UI → Service | No payload. Returns `{ desiredState, actualState, connectedSince, lastError }`. |
| `Ping` | UI → Service | Liveness/health check, also used to keep the session token fresh. |
| Responses (`Ack`, `Error`, `StatusChanged` push events) | Service → UI | `StatusChanged` is pushed proactively so the UI doesn't need to poll during retries/teardown/self-healing. |

**Configuration ownership is total and one-directional.** `config.template.json`
is removed from the UI project entirely (it currently ships alongside
`RealityTunnel.exe` only because nothing has separated the concerns yet —
see Phase 4). It becomes exclusively a Helper-owned, installer-deployed
file under the service's own directory. The UI never reads it, never
writes it, and never has filesystem permissions to the directory it lives
in. The *only* thing that ever crosses the pipe related to configuration
is the small set of validated `VpnProfile` scalar fields — never a file
path, never template content, never a rendered config, in either
direction. This means a fully compromised UI process cannot alter what
`sing-box` is actually told to do beyond the handful of fields
`VpnProfile` already exposes (all of which are validated server-side per
§4.7 regardless).

Everything the service does in response to `Connect` is fixed application
logic (§5) — validate the profile shape, render and write its own config
file inside its own service-owned directory, launch `sing-box.exe` from a
fixed, installer-controlled path, run a fixed set of `netsh`/`route`
invocations with parameters derived only from validated fields of
`VpnProfile`. There is no path where UI input becomes a shell command, a
file path, or file content chosen by the UI.

### 4.7 Request validation

- Every field of `VpnProfile` received in `Connect` is validated against a
  strict schema before use: `ServerHost` must be a syntactically valid
  hostname/IP, `ServerPort` in `1–65535`, `Uuid` must parse as a GUID,
  `Sni`/`PublicKey`/`ShortId` restricted to expected character sets/length
  — the same validation the config-template substitution implicitly
  assumes today, made explicit and enforced service-side instead of
  trusted blindly.
- The client image-path/signature check from §4.1 is re-verified (cheap
  check) on `Connect` specifically, since that's the highest-value verb.

### 4.8 Timeouts & cancellation

- Pipe reads use a bounded timeout (e.g. 10s) per message; a connection
  that goes silent longer than that is closed by the service.
- `Connect` is itself bounded (matches today's existing 4s
  "did sing-box exit immediately" check in `XrayController`, extended
  slightly to account for IPC overhead — e.g. 10s total) — if sing-box
  doesn't come up cleanly in that window, the service reports `Error` and
  guarantees it has already rolled back any partial route changes before
  responding (no "half-connected" state is ever left for the UI to
  discover later).
- Long-running verbs (just `Connect`, really — everything else is
  near-instant) support cancellation: the UI can send a `Cancel` control
  message correlated by `requestId`; the service treats this as "please
  disconnect if you were about to finish connecting," not as "kill
  whatever you're doing unsafely." Cancellation always resolves through
  the same rollback path as a failed connect, never leaves resources
  dangling.

### 4.9 Logging

- The service logs to its own file, independent from the UI's
  `ClientLogger`/`runtime_trace.log` — e.g.
  `%ProgramData%\RealityTunnel\Helper\helper.log`, since it runs under a
  system-level service account and does not have (and should not use) the
  interactive user's `%LocalAppData%`.
- Every request is logged with `requestId`, `type`, elapsed time, and
  outcome. Payloads are logged with secrets/keys redacted (the `Uuid` and
  `PublicKey` are logged truncated/hashed, matching the spirit of how
  `XrayController` already logs a SHA-256 of the sing-box binary rather
  than anything sensitive).
- The UI's `ClientLogger` can separately request the tail of the helper
  log via a dedicated (still explicit, still read-only) `GetHelperLog`
  verb for in-app diagnostics/support-bundle generation, rather than the
  UI ever reading the service's log file directly off disk (keeps the
  file ACL'd to `LocalSystem`/`Administrators` only).

## 5. Helper (service) responsibilities

### 5.1 Internal architecture: desired-state reconciliation, not imperative commands

The wire protocol (§4.6) still looks like simple verbs — `Connect`,
`Disconnect` — because that matches how the UI thinks about the world and
keeps `IVpnBackend` minimal (§8). But **internally, the service does not
treat `Connect`/`Disconnect` as one-shot imperative commands that run once
and are forgotten.** Instead:

- The service holds a single piece of mutable state: **desired state**,
  either `Disconnected` or `Connected(profile)`. `Connect` and `Disconnect`
  do nothing more than set this value and wake up the reconciliation loop.
- A background reconciliation loop continuously compares **desired
  state** against **actual state** (is `sing-box` running? are the
  expected routes present? is the TUN adapter up?) and drives actual
  state toward desired state — not just once on request, but for as long
  as the service runs.
- This means: if `sing-box` crashes while desired state is still
  `Connected(profile)`, the loop notices on its next tick and restarts it
  and re-applies routes/DNS *without the UI having to call `Connect`
  again* — the UI simply observes the transition via `StatusChanged`
  (down, then reconnecting, then up).
- `Connect`'s IPC response resolves once the loop has reached
  `Connected(profile)` (or hit the timeout in §4.8) — from the UI's
  perspective it still behaves like a simple request/response call. The
  reconciliation behavior is purely an internal robustness property, not
  a protocol change.
- On service startup (including after a crash-restart by the SCM),
  desired state initializes to `Disconnected` and the loop's first action
  is the orphan cleanup described below — the service never assumes a
  previous session's actual state matches whatever it currently observes
  on the machine.

This directly replaces the alternative of the *UI* orchestrating
privileged steps one at a time ("tell the service to start sing-box,
then tell it to add routes, then tell it to set DNS") with the UI stating
only the outcome it wants, and the privileged side owning every detail of
how to get there and stay there.

### 5.2 Concrete responsibilities

Moves out of `RealityTunnel.exe`, into the service, essentially 1:1 with
what `XrayController` does today — now executed *by* the reconciliation
loop in §5.1 rather than as one-shot calls:

- Launch `sing-box.exe` with a service-generated `config.json` (rendered
  from the service's own copy of `config.template.json`, substituting
  only validated `VpnProfile` fields — see §4.6 on configuration
  ownership).
- Stop `sing-box.exe` (graceful, then forceful kill-tree fallback — same
  as today).
- Own the TUN adapter's existence — it comes into being as a side effect
  of `sing-box` running with `"auto_route": true`; the service is
  responsible for confirming it came up and for confirming it's gone after
  stop.
- Routing table changes (`route add`/`route delete` for the split-tunnel
  bypass of the VPN server's own IP, and the two half-range default
  routes) — exactly the `SetupRoutes`/`TeardownRoutes` logic in
  `XrayController.cs` today.
- DNS configuration on the TUN interface (`netsh interface ip set/add
  dns`) — same as today.
- Firewall rules, if/when RealityTunnel adds a kill-switch or leak
  protection in the future — not present in the codebase today, but
  explicitly named per your prompt as an example of privilege-sensitive
  work that belongs here, not retrofitted into the UI later.
- Any filesystem writes that require elevated access (writing
  `config.json` next to a `sing-box.exe` installed under `Program Files`,
  for example) — the service owns its own working directory under
  `%ProgramData%\RealityTunnel\Helper`, so this never depends on where the
  UI happens to be installed or what rights the UI process has.
- Orphan cleanup: on service startup (including SCM-triggered restarts)
  and as an ongoing check inside the reconciliation loop, if `sing-box.exe`
  is running or routes are present that don't correspond to the current
  desired state, the service tears them down. This is new behavior beyond
  what `XrayController` does today, and is the concrete reliability payoff
  of both choosing a service over a one-shot helper (§3) and structuring
  it around desired-state reconciliation rather than imperative commands.

**Explicitly not moved:** everything in the "current state" table in §2
that already runs fine unelevated stays exactly where it is.

## 6. UI responsibilities (unchanged ownership)

`RealityTunnel.exe` keeps, unmodified in terms of *where the logic lives*:

- Login, JWT handling (`AuthenticationService`, `TokenService`)
- Account/device management, device heartbeat (`DeviceHeartbeatService`)
- Configuration/profile download and caching (`ConfigurationProvider`,
  `SecureStorageService`, `OracleApiClient`)
- Notifications, tray icon (`TrayIcon`)
- Settings, logs (UI-side `ClientLogger`)
- Update UI (whatever exists/will exist for update flow)
- Connection state display — driven by `StatusChanged` push events and
  `GetStatus` responses from the service, instead of directly polling
  `XrayController.IsRunning()` as `VpnSessionManager` does today.

`VpnSessionManager` keeps its retry/backoff/state-machine logic
(`ConnectInternalAsync`, `AutoRetryAsync`, the `OnStateChanged` /
`OnConnectedChanged` / `OnRetryUpdate` events consumed by `MainWindow` and
`TrayIcon`) — it is repointed to call an IPC client instead of
`XrayController` directly, but its public surface to the rest of the UI
does not need to change.

The UI never needs Administrator rights for any of the above — confirmed
in §2, none of it touches anything privileged today.

## 7. Migration plan

Each phase leaves the project in a fully functional, shippable state.
No phase is a rewrite; each is additive or a narrow swap.

### Phase 1 — Introduce the seam (no behavior change)

- Extract an `IVpnBackend` interface (`ConnectAsync(VpnProfile)`,
  `DisconnectAsync()`, `GetStatusAsync()`, plus the existing
  `OnStateChanged`/`OnConnectedChanged`/`OnRetryUpdate` events) that
  `VpnSessionManager` depends on instead of `XrayController` directly.
- Provide exactly one implementation for now: `InProcessVpnBackend`, a
  thin wrapper around the existing `XrayController` — behaviorally
  identical to today.
- `app.manifest` is **not** changed yet. The app still requires
  Administrator, still launches the same way it does today, still works.
- Risk: essentially none — this is a refactor behind an interface with no
  runtime behavior change. Verifiable by running the existing (elevated)
  build exactly as before.

### Phase 2 — Build the service, run it side by side (opt-in)

- New project, `RealityTunnel.Helper` (Windows Service, .NET, plain
  console/worker service — no WinUI/WindowsAppSDK dependency at all,
  which also means it is entirely unaffected by the WinUI3 elevation bug
  that started this investigation).
- Implements the IPC server from §4 and the responsibilities from §5,
  reusing the existing `XrayController` code (moved into the helper
  project, or referenced from a small shared library — whichever keeps
  duplication lowest; this is an implementation detail decided during
  actual coding, not this design phase).
- Add `NamedPipeVpnBackend : IVpnBackend` in the UI, implementing the
  client side of §4, gated behind a local debug switch (e.g. an
  environment variable or settings flag), not the default yet.
- The service is installed manually by the developer for testing at this
  stage (no installer changes yet). `RealityTunnel.exe` still defaults to
  `InProcessVpnBackend` and still requires Administrator — production
  behavior is unaffected.
- **Service-account prototyping happens in this phase, empirically, before
  Phase 3 locks anything in (see §9):** install the service for local
  testing first as a dedicated virtual account (`NT SERVICE\RealityTunnelHelper`)
  added to the built-in `Network Configuration Operators` group, with no
  extra privileges granted. Run through connect/disconnect/reconnect and
  observe exactly which operation fails first, if any (adapter creation,
  route changes, or DNS changes are the candidates). Grant the specific
  missing privilege (e.g. `SeLoadDriverPrivilege` if first-time Wintun
  adapter instantiation needs it) one at a time via LSA policy rather than
  jumping straight to `LocalSystem`. Only fall back to `LocalSystem` if a
  specific operation is confirmed to require it and no narrower privilege
  grant resolves it. Record the outcome (which account + which privileges,
  or the confirmed `LocalSystem` justification) before Phase 3 begins.
- Risk: low. This phase is purely additive; nothing existing is removed
  or changed by default.

### Phase 3 — Flip the default

- Installer changes: register and start `RealityTunnelHelper` as a
  service (`SERVICE_AUTO_START`), running under the account determined by
  the Phase 2 prototyping above (least-privileged option that was proven
  sufficient, falling back to `LocalSystem` only if justified). Install
  the service binary under `Program Files` alongside (or instead of)
  where `sing-box.exe` lives today. `config.template.json` moves with it
  and is no longer part of the UI's install payload (§4.6).
- `app.manifest` changes from `requireAdministrator` to `asInvoker`.
- `RealityTunnel.exe` now defaults to `NamedPipeVpnBackend`.
- Add first-run/runtime detection: if the service isn't installed or
  isn't running, the UI surfaces a clear, actionable error (distinct from
  today's generic "No Config" state) rather than silently failing.
- `InProcessVpnBackend` and the `requireAdministrator` manifest are kept
  in the codebase but unused/dead at this point, specifically so this
  phase can be reverted quickly if something is wrong in production,
  without a second migration.
- Risk: this is the phase where user-visible behavior actually changes
  (no more UAC prompt on launch). Should ship to a small population
  first if a staged-rollout mechanism exists.

### Phase 4 — Cleanup

- Remove `InProcessVpnBackend`, the now-dead elevated code paths, and the
  unused `requireAdministrator` manifest option once Phase 3 has proven
  stable.
- Uninstaller updates: stop and delete the service, and explicitly tear
  down any leftover TUN adapter/routes as a final safety net.
- Confirm `XrayController`'s remaining home is exclusively inside
  `RealityTunnel.Helper` (no longer referenced from the UI project at
  all).

### Phase 5 — Hardening

- Code signing for the service binary (§4.1's image-path check depends on
  this being meaningful).
- Expand the orphan-cleanup-on-start logic in §5 with real-world testing
  (kill the UI mid-connect, kill the service mid-connect, pull network,
  etc.).
- Add the `GetHelperLog` diagnostic verb (§4.9) to support bundles.

## 8. Constraints honored

- No backend API changes.
- No authentication redesign — `AuthenticationService`/`TokenService`
  logic is untouched; the helper doesn't participate in auth at all.
- No provisioning changes.
- No subscription/plan logic changes.
- No new abstraction beyond the one seam needed to make the swap
  possible (`IVpnBackend`) — deliberately not building a generic
  plugin/command framework, a generic RPC layer, or anything speculative.
- `IVpnBackend` itself stays at exactly four members —
  `ConnectAsync(VpnProfile)`, `DisconnectAsync()`, `GetStatusAsync()`, and
  the existing state-change events. No "just in case" methods are added.
  If a future feature genuinely needs a new capability, that is a
  deliberate, reviewed addition to both the interface and the wire
  protocol together — never a generic passthrough that lets the UI ask
  the service to do something not already named in §4.6.
- Helper is kept to exactly the responsibilities in §5 — it is not a
  general-purpose privileged-operations service, and does not grow verbs
  beyond `Hello`/`Connect`/`Disconnect`/`GetStatus`/`Ping`/`GetHelperLog`
  without a deliberate future decision to do so.
- Helper runs under the least-privileged account empirically proven
  sufficient (§7 Phase 2, §9) — `LocalSystem` is a documented fallback,
  never the unexamined default.
- Version negotiation (§4.3) is a hard gate, not an advisory check — no
  privileged verb is reachable on any connection before `Hello` succeeds.

## 9. Open items for approval before implementation

- **Service account is resolved by prototyping, not by picking one now.**
  Default starting point for Phase 2 (§7): `NT SERVICE\RealityTunnelHelper`
  (a per-service virtual account) added to the built-in `Network
  Configuration Operators` local group, which is specifically designed to
  allow TCP/IP and DNS configuration changes without full Administrator
  rights — covering the `netsh`/`route` half of §5.2 directly. The
  remaining unknown is Wintun adapter instantiation: whether it needs
  `SeLoadDriverPrivilege`/`SeCreateGlobalPrivilege` granted individually to
  that account, or whether it works with no extra privileges once the
  Wintun driver itself is already installed (a one-time, admin-driven step
  at product install time, separate from per-connect adapter creation).
  This is determined empirically during Phase 2 by testing each candidate
  in order (no extra privileges → individually granted privileges →
  `LocalSystem` only if both prior options are confirmed insufficient) and
  the result is recorded before Phase 3 begins. `LocalSystem` remains
  available as the documented fallback, not the default.
- Confirm service name/pipe name (`RealityTunnelHelper` /
  `\\.\pipe\RealityTunnelHelper` used above are placeholders).
- Confirm whether Phase 3's rollout should be staged (feature flag /
  percentage rollout) or a single cutover, depending on whether such
  infrastructure already exists elsewhere in the product.

---

**Approved with modifications (see revision note above). Implementation
can begin with Phase 1 (§7), which is a behavior-preserving refactor with
no open questions blocking it. The service-account, pipe-naming, and
rollout-strategy items in §9 must be settled during Phase 2 before Phase
3 (the actual privilege cutover) starts, but do not block starting the
work.**
