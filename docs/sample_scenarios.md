## Sample Capture Scenarios

The repository ships a handful of synthetic runs you can reference in documentation, demos, and onboarding decks. Rebuild every artifact with:

```
PYTHONPATH=src python docs/generate_sample_reports.py
```

That script rebuilds the structured JSON payloads, the console-friendly Rich summaries, and the self-contained HTML reports inside `docs/sample_reports/`.

PDF artifacts are also generated **if** the optional PDF renderer dependency is installed (see note below).

### Optional PDF generation (WeasyPrint)

`docs/generate_sample_reports.py` renders PDFs from the generated HTML using **WeasyPrint**. This is not required to use the core CLI/API, but is used to publish the sample PDFs committed under `docs/sample_reports/`.

- Python dependency: `weasyprint`
- System dependencies: WeasyPrint may require platform libraries (e.g., Cairo/Pango) depending on your distro.
- Licensing: WeasyPrint is a third-party project distributed under its own license; ensure redistribution of the PDFs and any bundled dependencies complies with applicable terms.

### Baseline Branch Burst

Small branch feed captured from the `tests/utils/flog_workload.py` dataset; represents a 2-second burst of mixed infra telemetry with a single talker.

- Config overrides

```
{
  "duration_seconds": 2,
  "flush_interval_seconds": 1,
  "high_value_keywords": ["denied", "error", "fail"],
  "noise_threshold_ratio": 0.7,
  "sample_size_limit": 1024
}
```

- Report artifacts
  - Console: `docs/sample_reports/baseline_branch_burst.console.txt`
  - JSON: `docs/sample_reports/baseline_branch_burst.json`
  - HTML: `docs/sample_reports/baseline_branch_burst.html`
  - PDF: `docs/sample_reports/baseline_branch_burst.pdf` (optional; requires WeasyPrint)
- Highlights: 12 EPS / 0.14 GB-day projection, all traffic from `127.0.0.1`, automatically flagged as a dominant talker that should be deduplicated.

### East DC Peak Hour

High-throughput data center scenario synthesized via `docs/generate_sample_reports.py` using `SyslogSizingConfig` overrides to emulate 15 seconds of saturated firewalls, SD-WAN nodes, and application gateways.

- Config overrides

```
{
  "listen_host": "10.23.0.15",
  "udp_port": 15514,
  "tcp_port": 16514,
  "duration_seconds": 15,
  "sample_size_limit": 4096,
  "high_value_keywords": ["dropped", "error", "timeout", "retry"],
  "noise_threshold_ratio": 0.5,
  "max_tcp_clients": 128
}
```

- Report artifacts
  - Console: `docs/sample_reports/east_dc_peak_hour.console.txt`
  - JSON: `docs/sample_reports/east_dc_peak_hour.json`
  - HTML: `docs/sample_reports/east_dc_peak_hour.html`
  - PDF: `docs/sample_reports/east_dc_peak_hour.pdf` (optional; requires WeasyPrint)
- Highlights: 39.6 MB in 15 seconds (212 GB/day equivalent) with evenly distributed talkers, triggering the “High daily ingest” insight without noise alarms.

### Noisy Lab Diagnostic

Lab test bench flooded by sensor heartbeats and limited telemetry signal, used to showcase queue drops and tuning recommendations.

- Config overrides

```
{
  "listen_host": "192.0.2.55",
  "udp_port": 25214,
  "tcp_port": 26214,
  "duration_seconds": 5,
  "sample_size_limit": 1024,
  "high_value_keywords": ["panic", "error", "fail"],
  "noise_threshold_ratio": 0.4,
  "max_tcp_clients": 32
}
```

- Report artifacts
  - Console: `docs/sample_reports/noisy_lab_diagnostic.console.txt`
  - JSON: `docs/sample_reports/noisy_lab_diagnostic.json`
  - HTML: `docs/sample_reports/noisy_lab_diagnostic.html`
  - PDF: `docs/sample_reports/noisy_lab_diagnostic.pdf` (optional; requires WeasyPrint)
- Highlights: 18% drop rate, 70% of volume from one talker, and zero keyword hits, resulting in “Potential sampling bias”, “Signal-to-noise imbalance”, and “Dominant noise source” insights. The tool also suggests `^sensor\s+heartbeat\s+ok$` as a regex pattern for the dominant talker.
