# Concurrent-IP Enforcement Research Plan & Experimental Design

**Document Status:** Research Plan Only (No Implementation)
**Date:** 2026-07-03
**Target Execution Phase:** Phase 1.4 / POC Validation
**Context:** RealityTunnel VPN Infrastructure (Server 2 — Marzban/Xray)

---

## 1. Executive Summary & Purpose

A core requirement of the RealityTunnel business model is preventing unauthorized account sharing without degrading the experience of legitimate multi-device users. Unlike traditional web applications where session sharing can be mitigated via token limits, VPN protocols (VLESS + REALITY over TCP/UDP/gRPC) operate at the transport layer. 

Enforcing concurrent IP limits requires monitoring active socket connections in real time within the Xray core or its control plane (Marzban). This research plan evaluates the two primary architectural approaches available in the Marzban/Xray ecosystem—**V2IpLimit** and **luIP**—and establishes a rigorous experimental design to validate their behavior under real-world networking conditions (mobile handoffs, CGNAT, IPv6, rapid reconnections) before production rollout.

---

## 2. Comparative Analysis: V2IpLimit vs. luIP

### 2.1 V2IpLimit (Log-Parsing & API Enforcement Engine)

#### How it integrates with Marzban/Xray
V2IpLimit runs as an external service or companion container alongside Marzban. It monitors Xray's access logs (or connects to Marzban's real-time log stream/webhook) to track incoming connection IPs mapped to specific email/UUID tags. When an account exceeds its configured IP threshold, V2IpLimit communicates back to Marzban via the Marzban REST API or Xray gRPC API to dynamically disable the user or apply traffic blocks.

#### Enforcement Mechanism
- **Reactive / Asynchronous:** Detects concurrent IPs by aggregating recent access logs over a sliding window (e.g., 30–60 seconds).
- When distinct IPs for a single user ID exceed `N` within the window, it triggers an enforcement action (e.g., setting user status to `disabled` in Marzban or injecting a temporary firewall/routing drop rule).

#### Expected Latency
- **High (1,000ms – 10,000ms):** Enforcement is strictly reactive. An unauthorized second IP can establish a connection and transmit data for several seconds before the log aggregator processes the event and issues a ban/disable command to Marzban.

#### Resource Usage
- **Moderate CPU / Memory:** Requires parsing high-volume text log streams or continuous gRPC polling. In high-throughput environments (thousands of connections/sec), log parsing can consume significant CPU and disk I/O if logs are written to disk before reading.

#### Docker Deployment
- Deployed as a separate Docker container in `docker-compose.yml` on Server 2, sharing a Docker volume for logs or sharing the Docker network to access Marzban's internal API (`http://marzban:8000`).
- Requires generating and injecting a Marzban admin token or shared socket for API access.

#### Failure Modes
- **Fail-Open by default:** If the V2IpLimit container crashes, logs rotate too quickly, or disk I/O stalls, Xray continues serving traffic without IP enforcement.
- **API Race Conditions:** If Marzban restarts while V2IpLimit is issuing a disable command, state synchronization may fail.

#### False Positives
- **High:** Sliding window aggregation cannot easily distinguish between a legitimate user switching Wi-Fi to cellular (where the old Wi-Fi socket takes a few seconds to time out) and two genuine concurrent users. This frequently results in legitimate users being temporarily banned during cellular handoffs.

#### Logging
- Generates its own application logs recording detection events, IP lists, and API calls made to Marzban. Easy to audit externally.

#### Maintenance Status
- Community-maintained third-party tool. Update frequency depends on community interest and compatibility breaks in Xray log formats or Marzban API changes.

#### Advantages
- Non-invasive: Does not require custom Xray core builds or complex internal Xray routing modifications.
- Decoupled: Can be restarted, upgraded, or disabled without restarting the Xray VPN core.
- Highly configurable penalty actions (e.g., temporary ban for 5 minutes vs. permanent disable).

#### Disadvantages
- Reactive enforcement allows burst abuse before disconnect.
- Prone to false positives during mobile network handoffs due to log window lag.
- Overhead of continuous text log parsing under heavy load.

---

### 2.2 luIP (In-Core / Xray Engine Integration)

#### How it integrates with Marzban/Xray
luIP (and related internal routing/policy extensions) integrates directly into the Xray core (often compiled as a custom Xray core or utilizing specialized Xray routing/stats modules managed by advanced Marzban configurations). It inspects incoming connection metadata at the socket/inbound handler level before proxying traffic.

#### Enforcement Mechanism
- **Inline / Synchronous:** As a client handshake arrives at the VLESS/REALITY inbound handler, the core checks an in-memory connection tracker mapping `UserUUID -> Set[ActiveIPs]`.
- If `len(ActiveIPs) >= Limit` and `NewIP not in ActiveIPs`, the incoming TCP/UDP handshake is rejected immediately (or closed post-TLS handshake) before data transfer begins.

#### Expected Latency
- **Ultra-Low (< 5ms):** Enforcement occurs in memory during socket establishment. There is zero delay between threshold breach and traffic rejection.

#### Resource Usage
- **Very Low:** Operates on in-memory hash tables (`map[string]map[string]time.Time`) managed within Xray's Go runtime. Negligible CPU overhead; zero disk I/O for detection.

#### Docker Deployment
- Requires utilizing a custom Docker image for Marzban that includes the modified Xray core or enabling specific experimental flags in the Marzban core configuration.
- No secondary containers or shared volume dependencies.

#### Failure Modes
- **Fail-Closed or Core Crash:** A bug or memory leak in the inline IP tracking map could crash the entire Xray core process, disconnecting all active VPN users on Server 2.
- Memory exhaustion if dead connections are not properly garbage collected from the active IP table after abrupt client disconnects (e.g., UDP timeouts).

#### False Positives
- **Low to Moderate:** Because it checks *currently active sockets* rather than historical log windows, a mobile handoff only fails if the old socket is still held open by the OS kernel or TCP keepalive. Once the old socket drops, the new IP is admitted instantly.

#### Logging
- Minimal internal debug logs emitted via Xray standard output. Harder to parse for detailed billing/audit reconciliation unless exported via gRPC stats.

#### Maintenance Status
- Highly dependent on specific Xray-core forks or specialized Marzban releases. Upgrading Xray to upstream versions may break inline patches if not officially merged.

#### Advantages
- Instantaneous, zero-leak enforcement.
- Ultra-low CPU and memory footprint.
- Eliminates log-parsing race conditions and disk I/O bottlenecks.

#### Disadvantages
- Requires custom core binaries or non-standard configurations.
- Higher operational risk: a bug in inline tracking affects all VPN traffic.
- Less flexible penalty mechanisms (typically just connection drop, rather than temporary account lockout).

---

### 2.3 Summary Comparison Table

| Metric | V2IpLimit (Log / API Based) | luIP (Inline Core Based) |
|---|---|---|
| **Enforcement Point** | Reactive (External Log Parsing) | Synchronous (Inline Socket Handler) |
| **Enforcement Latency** | 1,000ms – 10,000ms (Windowed) | < 5ms (Instantaneous) |
| **CPU / RAM Overhead** | Moderate (Log parsing + REST calls) | Negligible (In-memory Go map) |
| **Docker Complexity** | 2 containers, shared volumes/network | 1 container (Custom Xray core/config) |
| **Failure Mode** | Fail-Open (VPN works if monitor dies) | Fail-Closed (Core crash drops all users) |
| **Mobile Handoff Risk** | High false-positive rate (Log lag) | Moderate (Dependent on TCP timeout) |
| **Auditability** | Excellent (Clear REST API/audit logs) | Poor (Requires stats scraping) |
| **Upstream Stability** | Immune to Xray core internal changes | Vulnerable to Xray core updates/forks |

---

## 3. Experimental Design & Validation Plan

To determine which enforcement mechanism meets RealityTunnel's reliability and user-experience standards, the following 8 standardized experiments MUST be executed during Phase 1.4 POC testing.

**IMPORTANT:** Do NOT execute these tests during Phase 1.3. This is the specification for future laboratory validation.

---

### Experiment 1: Same Account from Two Public IPs (Baseline Enforcement)

- **Goal:** Verify that the system successfully blocks or terminates traffic when a single Account ID connects simultaneously from two distinct public IPv4 addresses exceeding a limit of 1.
- **Procedure:**
  1. Configure Account A with `max_ips = 1` in Marzban/enforcement engine.
  2. Connect Device 1 (e.g., Home Fiber, IP `203.0.113.10`) using Account A's REALITY profile. Start continuous ping / data transfer.
  3. While Device 1 is streaming data, connect Device 2 (e.g., Cloud VPS or Cellular, IP `198.51.100.25`) using the exact same profile.
  4. Observe connection state, traffic flow, and Marzban user status over 60 seconds.
- **Expected Behaviour:** Device 1 connects normally. When Device 2 connects, the enforcement engine detects 2 active IPs (> 1 limit) and intervenes.
- **What constitutes PASS:**
  - *For luIP:* Device 2 handshake is rejected immediately (TLS/TCP reset), OR Device 1 is dropped instantly while Device 2 is admitted. Total overlapping concurrent data transfer is 0 seconds.
  - *For V2IpLimit:* Within <= 15 seconds of Device 2 connecting, Marzban disables Account A or drops one/both sockets.
- **What constitutes FAIL:** Both Device 1 and Device 2 successfully stream traffic simultaneously for > 30 seconds without intervention.

---

### Experiment 2: Rapid Reconnects (Flapping Link Simulation)

- **Goal:** Ensure that rapid disconnections and immediate reconnections from the *same* public IP do not trigger false-positive concurrent IP lockouts.
- **Procedure:**
  1. Configure Account A with `max_ips = 1`.
  2. Connect Device 1 from IP `203.0.113.10`.
  3. Execute a automated script that abruptly kills the VPN connection (simulating Wi-Fi drop or SIGKILL) and immediately reconnects within 500ms. Repeat 10 times in 30 seconds.
  4. Check if the user account is locked, disabled, or rejected.
- **Expected Behaviour:** Because the source public IP (`203.0.113.10`) never changes, the system should recognize this as 1 unique IP, even if old TCP sockets are in `TIME_WAIT` or slowly timing out.
- **What constitutes PASS:** All 10 rapid reconnections succeed. Account remains ACTIVE in Marzban; zero temporary bans or lockouts occur.
- **What constitutes FAIL:** Account is disabled or blocked after rapid reconnects due to the engine counting stale sockets from the same IP as "multiple" connections.

---

### Experiment 3: Mobile Network Switching (Wi-Fi to Cellular Handoff)

- **Goal:** Evaluate system resilience during real-world smartphone network transitions where IP addresses change abruptly while background connections exist.
- **Procedure:**
  1. Configure Account A with `max_ips = 1`.
  2. Connect mobile device via Wi-Fi (IP `203.0.113.10`). Start a background download or continuous HTTP ping stream.
  3. Disable Wi-Fi on the mobile device, forcing an immediate OS handoff to Cellular 5G/4G (IP `172.56.21.89`).
  4. Observe how quickly the VPN reconnects on cellular and whether a false-positive ban occurs.
- **Expected Behaviour:** When switching to cellular, the client establishes a new tunnel from the cellular IP. The server's old Wi-Fi socket may remain open until TCP keepalive expires. The system must transition without permanently banning the user.
- **What constitutes PASS:** The mobile client successfully resumes VPN connectivity on the cellular IP within <= 10 seconds. If a temporary concurrent-IP conflict is detected due to the lingering Wi-Fi socket, it must auto-resolve within <= 30 seconds without permanent account disablement.
- **What constitutes FAIL:** The user is permanently disabled in Marzban, or locked out for > 2 minutes, requiring manual admin intervention or waiting for a long ban window to expire.

---

### Experiment 4: VPN Server Reconnect / Container Restart Resilience

- **Goal:** Verify enforcement engine recovery and state synchronization after the VPN proxy server (Xray/Marzban) is restarted while clients are actively connected.
- **Procedure:**
  1. Connect 5 distinct accounts from 5 distinct IPs.
  2. Perform a container restart: `docker compose restart marzban` on Server 2.
  3. Allow clients to automatically reconnect upon server recovery.
  4. Immediately attempt to connect an unauthorized second IP to one of the 5 accounts.
- **Expected Behaviour:** Upon restart, the enforcement engine cleanly clears its in-memory IP tables or synchronizes with new logs, allowing legitimate reconnects while instantly resuming concurrent-IP monitoring.
- **What constitutes PASS:** All 5 legitimate clients reconnect cleanly within 15 seconds. The subsequent unauthorized second IP attempt is detected and blocked according to baseline enforcement standards.
- **What constitutes FAIL:** Enforcement engine fails to initialize after restart (fail-open), OR restart causes race conditions where legitimate reconnecting clients are falsely flagged as concurrent users and banned.

---

### Experiment 5: IPv6 & Dual-Stack Privacy Extension Behavior

- **Goal:** Determine if IPv6 SLAAC (Stateless Address Autoconfiguration) privacy extensions (which rotate IPv6 suffix addresses rapidly) or dual-stack IPv4/IPv6 connections trigger false-positive IP limits.
- **Procedure:**
  1. Configure Account A with `max_ips = 1`.
  2. Connect Device 1 from an ISP supporting IPv6 dual-stack.
  3. Force client traffic over IPv6. Force OS to generate a new IPv6 privacy temporary address (or switch between `/64` subnet IPs assigned to the same subscriber).
  4. Simultaneously transmit traffic over IPv4 and IPv6 from the exact same physical machine.
- **Expected Behaviour:** A single physical device on dual-stack may appear to Xray as connecting from both `203.0.113.10` (IPv4) and `2001:db8:1234:5678::abcd` (IPv6). If `max_ips = 1`, strict IP counting will flag this as 2 IPs.
- **What constitutes PASS:** System correctly enforces subnet-level masking for IPv6 (e.g., treating an entire `/64` subnet as 1 IP), OR account policy is documented/configured to allow `max_ips = 2` for single-user plans to accommodate dual-stack devices without triggering false bans.
- **What constitutes FAIL:** A single dual-stack laptop or smartphone is banned within minutes of normal browsing because IPv4 and IPv6 sockets are counted as two separate unauthorized users.

---

### Experiment 6: CGNAT (Carrier-Grade NAT) Shared Public IP

- **Goal:** Verify that multiple *distinct* RealityTunnel accounts connecting from the exact same public IP (e.g., two users at the same office, university, or cellular CGNAT ISP) do not interfere with each other.
- **Procedure:**
  1. Configure Account A (`max_ips = 1`) and Account B (`max_ips = 1`).
  2. Place Device 1 (logged into Account A) and Device 2 (logged into Account B) behind the same NAT router (Public IP `203.0.113.99`).
  3. Both devices connect simultaneously to Server 2 and stream heavy traffic.
- **Expected Behaviour:** Concurrent IP limits are scoped strictly *per Account UUID*, never globally per IP. Two different accounts sharing a source IP is normal network behavior.
- **What constitutes PASS:** Both Account A and Account B operate at full speed indefinitely with zero errors, warnings, or lockouts.
- **What constitutes FAIL:** The enforcement engine rate-limits, blocks, or disables either account due to source IP collision across distinct user UUIDs.

---

### Experiment 7: High Concurrency & Socket Exhaustion Stress Test

- **Goal:** Measure CPU, memory, and latency degradation of the enforcement engine under heavy concurrent connection/disconnection churn.
- **Procedure:**
  1. Use a load-testing tool (e.g., custom Go gRPC/TCP client worker pool) to simulate 500 concurrent VPN users.
  2. Introduce 50 active "flapping" workers that connect, send 10KB, disconnect, and change simulated IP every 2 seconds.
  3. Monitor Server 2 CPU usage, RAM consumption, Xray core latency (ping jitter), and enforcement engine error logs for 15 minutes.
- **Expected Behaviour:** The enforcement engine scales linearly without memory leaks, deadlocks, or spiking Xray proxy latency.
- **What constitutes PASS:**
  - Xray proxy latency increases by <= 5ms compared to baseline (no enforcement engine).
  - Memory consumption of V2IpLimit / luIP remains stable (no continuous growth / OOM risk).
  - Zero crashes or restarts of `marzban` or `xray` containers.
- **What constitutes FAIL:** CPU usage pins at 100% due to log parsing churn, Xray connection handshakes stall (> 1000ms latency), or the enforcement process crashes/OOMs under churn.

---

### Experiment 8: graceful Degradation / Enforcement Failure Mode

- **Goal:** Determine system behavior when the enforcement mechanism encounters a fatal error or process crash.
- **Procedure:**
  1. Connect 10 active users cleanly.
  2. *If testing V2IpLimit:* `kill -9` the V2IpLimit container or block its REST API port via `iptables`.
  3. *If testing luIP:* Inject a simulated tracking table deadlock or unmap the IPC socket.
  4. While the engine is dead/unreachable, attempt to connect Account A from 3 distinct public IPs simultaneously (`max_ips = 1`).
- **Expected Behaviour:** Identify whether the architecture fails open (prioritizing VPN availability over business enforcement) or fails closed (dropping VPN connectivity to protect billing limits).
- **What constitutes PASS (Architectural Alignment):**
  - For RealityTunnel, **Fail-Open is the mandatory design requirement** for companion services. If an IP enforcement tool fails, VPN traffic MUST continue uninterrupted for legitimate users. Account A may temporarily succeed from 3 IPs, but an audit alert must be generated for operator intervention. Total VPN outage due to a billing/enforcement helper crash is unacceptable.
- **What constitutes FAIL:** A crash or unresponsiveness in the concurrent-IP enforcement module causes Xray to drop existing tunnels or reject new legitimate handshakes (Fail-Closed).

---

## 4. Architectural Recommendation & Next Steps

Based on theoretical analysis and architectural requirements:
1. **Primary Recommendation for POC:** Begin Phase 1.4 laboratory testing with **luIP (or Xray in-core socket tracking)** if available in the target Marzban build, due to its instantaneous (< 5ms) enforcement and immunity to log-parsing overhead under heavy load.
2. **Fallback Strategy:** If luIP proves unstable or requires unmaintainable custom Xray forks, deploy **V2IpLimit** with a tuned 30-second sliding window and an explicit policy setting `max_ips = 2` for standard single-user plans. Allowing 2 IPs absorbs Wi-Fi/Cellular handoffs and IPv4/IPv6 dual-stack behavior without customer support friction, while still stopping mass account sharing (3+ concurrent IPs).
3. **Execution Gate:** No concurrent-IP enforcement policy will be enabled on production servers until all 8 experiments above are executed in the RealityTunnel laboratory environment and documented in a formal test report.
