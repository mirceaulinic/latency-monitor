# Metrics Backend: Log

This backend picks the metrics and emits a log entry, in JSON format, at the logging level you desire (default 
= WARNING).

Configuration example:

``/path/to/latency.toml`` (excerpt)

```toml
log_file = "/path/to/latency.log"
log_level = "INFO"

[metrics]
backend = "log"
level = "WARNING"
```

Then execute, referencing the configuration file:

```bash
$ latency-monitor -l /path/to/latency.toml
```

In the log file, you'll find the metrics in JSON format:

```bash
$ tail -f /path/to/latency.log

[2026-01-12 12:15:04,380] [WARNING] {"metric": "udp.wan.owd", "points": [[1768220104379245050, 373714]], "tags": ["source:lh-5000", "target:lh-8000", "isp:local", "location:laptop"]}
[2026-01-12 12:15:05,378] [WARNING] {"metric": "udp.wan.owd", "points": [[1768220105378620314, 284317]], "tags": ["source:lh-5000", "target:lh-8000", "isp:local", "location:laptop"]}
[2026-01-12 12:15:06,379] [WARNING] {"metric": "udp.wan.owd", "points": [[1768220106379405485, 457267]], "tags": ["source:lh-5000", "target:lh-8000", "isp:local", "location:laptop"]}
[2026-01-12 12:15:07,379] [WARNING] {"metric": "udp.wan.owd", "points": [[1768220107379402682, 377774]], "tags": ["source:lh-5000", "target:lh-8000", "isp:local", "location:laptop"]}
[2026-01-12 12:15:08,380] [WARNING] {"metric": "udp.wan.owd", "points": [[1768220108379715979, 392782]], "tags": ["source:lh-5000", "target:lh-8000", "isp:local", "location:laptop"]}
```

This can be useful for systems that parse logs, which is why the JSON format may be handy to extract / map the data.
