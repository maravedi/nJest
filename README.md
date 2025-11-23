# Syslog Sizing Tool

Cross-platform asyncio-based utility that ingests live syslog streams, estimates sustained ingest rates, and surfaces talker/noise insights for SIEM capacity planning. The toolkit ships with a CLI, FastAPI service, and structured JSON reporting so it can plug into automation pipelines or on-host diagnostics.

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
| `--max-tcp-clients` | `max_tcp_clients` | `64` | Drives semaphore controlling `_handle_tcp_client`; increase when expecting many TCP senders. |
| `--inactivity-grace-seconds` | `inactivity_grace_seconds` | `3` | Idle timeout for TCP clients to prevent descriptor leaks. |
| `--output-format` | n/a | `console` | Choose `console` (rich tables) or `json`. |
| `--json-path` | n/a | unset | Persist JSON to disk for later analysis. |
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

During execution the tool binds UDP/TCP listeners, queues payloads (65K bounded queue), and streams real-time stats. When the window ends it prints a Rich summary and optional JSON artifact.

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

## Binding to Syslog Ports

Many environments prefer the canonical syslog ports (`UDP 514`, `TCP/TLS 6514`). Binding below 1024 typically requires elevated privileges:

1. **setcap** (recommended):
   ```bash
   sudo setcap 'cap_net_bind_service=+ep' $(command -v python3.11)
   ```
   This allows low-port binding without running the entire process as root. Repeat after Python upgrades.
2. **authbind/systemd socket activation**: Use when capabilities are disallowed. Configure `authbind` or a systemd `.socket` unit that hands off accepted connections to the tool.
3. **Port conflicts**: Verify availability with `sudo ss -lpn | grep 514`. Stop existing syslog daemons or front them with a load balancer that forwards traffic to your non-privileged listeners.
4. **SELinux/AppArmor**: Enforce policies permitting the Python binary to bind the desired ports (`semanage port -a -t syslogd_port_t -p udp 5514`, etc.).

If binding fails you will see `OSError: [Errno 13] Permission denied` or `Errno 98 Address already in use`; adjust as above or change to higher ports.

## Troubleshooting & Verification

- `pytest` runs the fast unit suite; integrate with CI to guard regressions.
- Enable verbose logging via `--log-level DEBUG` for packet-level diagnostics.
- Use `tcpdump -ni <iface> port 5514` or `socat - UDP-LISTEN:5514,fork` to simulate traffic.
- When testing remote sources over TLS, terminate TLS with a proxy (stunnel, HAProxy) and forward plaintext syslog to the tool until native TLS is implemented.

With the above steps you can install, build, configure, and operate the syslog sizing tool confidently across lab and production environments. 