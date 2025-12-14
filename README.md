# Syslog Sizing Tool

Cross-platform asyncio-based utility that ingests live syslog streams, estimates sustained ingest rates, and surfaces talker/noise insights for SIEM capacity planning. The toolkit ships with a CLI, a FastAPI service, and reporting outputs (console, JSON, and an interactive HTML report) so it can plug into automation pipelines or on-host diagnostics.

## Build & Test Status

[![Pytest](https://img.shields.io/badge/pytest-14%20passed-brightgreen?style=flat-square&logo=pytest)](tests/)
[![CI](https://img.shields.io/badge/ci-gh--actions%20pending-lightgrey?style=flat-square&logo=githubactions)](https://docs.github.com/en/actions)

Latest local run: `python3 -m pytest` on 2025-11-23 with Python 3.12.3 (Linux, 14 tests, strict asyncio). Wire the badges to your CI provider (e.g., GitHub Actions `pytest.yml`) once the workflow is published so they track automation results instead of manual updates.

## Prerequisites

- Python `3.11+` with `pip`/`venv` (Ubuntu 22.04+: `sudo apt install python3.11 python3.11-venv python3-pip`)
- Build tooling: `gcc`/`build-essential` (for transitive wheels), `openssl` headers if your environment lacks manylinux binaries
- Optional: `pipx` for isolated CLI installs, `make` for scripted workflows
- Network permissions to bind UDP/TCP sockets (non-privileged ports by default; privileged syslog ports require elevated capabilities—see below)

## Installation Options

| Scenario | Command |
| --- | --- |
| Stable CLI via `pipx` | `pipx install .` (run inside repo) or `pipx install git+https://example.com/syslog-sizing-tool` |
| Local venv | `python3.11 -m venv .venv && source .venv/bin/activate && pip install --upgrade pip && pip install -e .[dev]` |
| Ad-hoc run | `python3.11 -m pip install . && syslog-sizing-tool --help` |

The package exposes the `syslog-sizing-tool` entry point once installed.

## Building From Source

1. Clone the repository and enter the workspace.
2. Create/activate a virtual environment (`python3.11 -m venv .venv && source .venv/bin/activate`).
3. Install dependencies: `pip install -e .[dev]`.
4. Run tests/linting if desired (`pytest`).
5. Build distributables when ready to publish:
   ```bash
   python -m pip install build
   python -m build
   ```
   Artifacts appear under `dist/` (wheel + sdist) and are powered by Hatchling.

## Configuration & Runtime Controls

All entry points follow a Receive-an-Object/Return-an-Object (RORO) contract internally. The CLI and API accept the same schema defined by `SyslogSizingConfig`. Key parameters:

| Option | RORO Field | Default | Notes / Performance Impact |
| --- | --- | --- | --- |
| `--listen-host` | `listen_host` | `0.0.0.0` | Bind interface. Use a specific IP for multihomed hosts. |
| `--udp-port` | `udp_port` | `5514` | Non-privileged test port. Set to `514` for production, but see binding considerations. |
| `--tcp-port` | `tcp_port` | `5614` | TLS offload is out-of-scope; front with stunnel or a load balancer if needed. |
| `--duration-seconds` | `duration_seconds` | `300` | Total capture window (1s–24h). Longer windows increase memory usage for percentile samples. |
| `--sample-size-limit` | `sample_size_limit` | `4096` | Number of message sizes retained; raise for more accurate percentiles at the cost of RAM. |
| `--high-value-keywords` | `high_value_keywords` | `error fail panic critical` | Tracked for high-value counts; accepts space-separated tokens. |
| `--noise-threshold-ratio` | `noise_threshold_ratio` | `0.35` | Talkers above this ratio highlighted for tuning. |
| `--flush-interval-seconds` | `flush_interval_seconds` | `5` | Reserved for future intermediate reporting; does not change final sizing output today. |
| `--max-tcp-clients` | `max_tcp_clients` | `64` | Drives semaphore controlling `_handle_tcp_client`; increase when expecting many TCP senders. |
| `--inactivity-grace-seconds` | `inactivity_grace_seconds` | `3` | Idle timeout for TCP clients to prevent descriptor leaks. |
| `--output-format` | n/a | `console` | Choose `console` (Rich tables), `json`, or `html` (interactive report). |
| `--json-path` | n/a | unset | Persist JSON to disk for later analysis. |
| `--html-path` | n/a | unset | Persist HTML to disk for offline sharing/review. |
| `--log-level` | n/a | `INFO` | Standard library logging level. |

Pydantic validation enforces sane ranges and prevents UDP/TCP port collisions.

## Running the CLI

```bash
syslog-sizing-tool \
  --listen-host 0.0.0.0 \
  --udp-port 5514 \
  --tcp-port 5614 \
  --duration-seconds 900 \
  --output-format console
```

During execution the tool binds UDP/TCP listeners, queues payloads (65K bounded queue), and streams real-time stats. When the window ends it emits your chosen report format:

- **`console`**: Rich tables (best for terminals)
- **`json`**: Structured output (best for pipelines and storing artifacts)
- **`html`**: A self-contained interactive report with a scaling playground (best for sharing)

Example HTML run (write to disk):

```bash
syslog-sizing-tool --output-format html --html-path report.html
```

## Filtering recommendations (noise reduction)

The tool’s “noise” guidance is driven by `noise_threshold_ratio`:

- **Talker classification**: any source whose traffic share \( \ge \) `noise_threshold_ratio` is flagged as a likely noise contributor.
- **Suggested actions**: flagged sources are marked **“Deduplicate or downsample”**; others are **“Retain”**.
- **Suggested patterns (newer behavior)**: for flagged sources, the tool generates **candidate regex patterns** from sampled messages to help you implement:
  - **drop/suppress rules** (discard repeated low-value events),
  - **deduplication rules** (collapse repeats), or
  - **sampling rules** (keep 1/N after validation).

Pattern generation uses a log-template miner (see third-party disclosure below) with masking for common high-cardinality tokens (IPs, numbers, hex). Treat generated patterns as **starting points**: validate against representative traffic and your SIEM/collector’s regex engine before deploying.

## Running the FastAPI Service

Start the API with Uvicorn (inside your virtual environment):

```bash
uvicorn syslog_sizing_tool.reporting.api:app --host 0.0.0.0 --port 8080
```

Workflow:

1. `POST /capture/start` with the JSON payload matching `SyslogSizingConfig`. Response returns a `session_id`.
2. Poll `GET /capture/{session_id}` until the status transitions to `completed` (result attached) or `failed` (error string included).

Capture jobs run in background tasks so the HTTP request returns immediately while the ingest session continues.

## Performance & Scalability Considerations

- **Event queue**: A bounded `asyncio.Queue(maxsize=65536)` absorbs bursts. If you observe `ingest_queue_full` logs, increase host resources or scale out collectors.
- **CPU affinity**: Parsing uses pure Python; pin the process to dedicated cores or run multiple instances behind a load balancer for multi-GB/day sources.
- **TCP back-pressure**: `max_tcp_clients` + `inactivity_grace_seconds` guard descriptor exhaustion. Tighten grace windows on noisy but idle senders.
- **Percentile accuracy**: `sample_size_limit` feeds percentile estimates. Large deployments (100K+ EPS) should raise this limit and allocate more memory.
- **JSON logging**: Structured logs (see `utils/logging_helpers.py`) are SIEM-friendly; forward them to your platform for live monitoring.
- **API concurrency**: Uvicorn workers can be scaled with `--workers N`. The capture itself is single-process; run multiple pods/VMs for horizontal scale.

## Binding to low/privileged ports (e.g., 514)

Many environments prefer the canonical syslog ports (`UDP 514`, `TCP 514`, `TCP/TLS 6514`).

### Linux / macOS

Ports below 1024 typically require elevated privileges.

- **Recommended: Linux capabilities (`cap_net_bind_service`)** (bind low ports without running as root):

```bash
sudo setcap 'cap_net_bind_service=+ep' "$(command -v python3.11)"
```

Repeat after Python upgrades (the capability is set on the specific Python binary).

- **Alternatives** (when capabilities are disallowed): `authbind` or systemd socket activation (bind/accept as root, hand off to the tool).
- **Port conflicts**: verify availability with `sudo ss -lpun | grep ':514 '` (UDP) and `sudo ss -lptn | grep ':514 '` (TCP). Stop/relocate existing syslog daemons or forward traffic to a high port (e.g., 5514/5614).
- **MAC**: run the tool under `sudo` if you can’t use an equivalent capability mechanism.

If binding fails you will typically see `OSError: [Errno 13] Permission denied` (no privileges) or `Errno 98 Address already in use` (already bound).

### Windows

Windows does **not** treat ports \<1024 as “privileged” the way Linux/macOS does, so binding to **514 usually does not require Administrator** *just for the port number*.

Admin privileges are still commonly needed for:

- **Firewall rules** (allow inbound UDP/TCP 514)
- **Stopping/adjusting another service already bound to 514**

Useful commands (PowerShell):

```powershell
# Check what's using UDP/TCP 514
Get-NetUDPEndpoint -LocalPort 514
Get-NetTCPConnection -LocalPort 514 -State Listen

# Allow inbound syslog to this host (run PowerShell as Administrator)
New-NetFirewallRule -DisplayName "Syslog Sizing Tool UDP 514" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 514
New-NetFirewallRule -DisplayName "Syslog Sizing Tool TCP 514" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 514
```

If binding fails on Windows, it’s most often **port conflicts** (`Address already in use`) or **network policy/firewall** rather than “privileged port” restrictions.

## Troubleshooting & Verification

- `pytest` runs the fast unit suite; integrate with CI to guard regressions.
- Use `syslog-sizing-tool --integration-test` to generate a quick end-to-end result with simulated traffic (no sockets required).
- Enable verbose logging via `--log-level DEBUG` for packet-level diagnostics.
- Use `tcpdump -ni <iface> port 5514` or `socat - UDP-LISTEN:5514,fork` to simulate traffic.
- When testing remote sources over TLS, terminate TLS with a proxy (stunnel, HAProxy) and forward plaintext syslog to the tool until native TLS is implemented.

## Third-party components and license notices

This project relies on third-party open source components. If you redistribute this tool (source, wheels, containers, appliances), ensure you comply with each dependency’s license terms.

- **Runtime dependencies** (from `pyproject.toml`):
  - **FastAPI**: API surface for capture control
  - **Uvicorn**: ASGI server used to run the FastAPI app
  - **Pydantic**: input validation and model serialization
  - **Rich**: console report rendering
  - **Drain3**: template mining used to generate suggested filtering regexes for noisy talkers
- **Build tooling**:
  - **Hatchling**: packaging/build backend
- **Development/testing**:
  - **pytest**, **pytest-asyncio**
- **Documentation utilities (optional)**:
  - `docs/generate_sample_reports.py` uses **WeasyPrint** to render PDF copies of the HTML report (not required for the core CLI/API).

To audit exact versions and licenses in your environment, use your standard SBOM/license tooling (for example, `pip-licenses`, `pipdeptree`, or a CI license scanner) and/or inspect each installed package’s metadata and bundled LICENSE/NOTICE files.

## License

This project is licensed under the **MIT License**. See `LICENSE`.

With the above steps you can install, build, configure, and operate the syslog sizing tool confidently across lab and production environments. 