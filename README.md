![Latency Monitor](docs/images/logo.png)

# latency-monitor

TCP and UDP latency monitoring tool, with pluggable interface for publishing metrics.

[![Code Quality](https://github.com/mirceaulinic/latency-monitor/actions/workflows/code-quality.yml/badge.svg)](https://github.com/mirceaulinic/latency-monitor/actions/workflows/code-quality.yml)

## Features

- **TCP Latency Monitoring**: Monitor TCP connection latency one-way and round-trip to specified endpoints.
- **UDP Latency Monitoring**: Measure UDP one-way and round-trip time to target hosts.
- **Pluggable Metrics**: Flexible interface for publishing metrics to various backends
- **Configurable**: Easy configuration for monitoring targets and intervals, 
- **Precision**: Measurements are collected in nanoseconds, and probes can be executed every millisecond. This is ideal
  for capturing micro-bursts, or rapidly changing environments.
- **Stable**: TCP measurements takes place over established connections to reduce the impact of firewalls or other
  intermediary systems. Each probing pair is one flow, maintained while the link is being monitored.
- **Lightweight**: Minimal resource footprint for continuous monitoring, so it can be executed on any operating system 
  (where Python is available).

## Installation

Install from PyPI:

```bash
pip install latency-monitor
```

For development installation:

```bash
git clone https://github.com/mirceaulinic/latency-monitor.git
cd latency-monitor
uv sync --locked --dev --all-extras
```


> [!IMPORTANT]
> By default, the project doesn't have any third-party dependencies. However, depending on the metrics backend you want
to use, you'll have to install the additional package(s). Using ``pip``, you can install the additional requirements by 
running, e.g., ``pip install latency-monitor[datadog]`` if you want to use Datadog as the metrics backend, ``pip install
latency-monitor[zeromq]`` for ZeroMQ and so on. Similarly if you're using ``uv``: ``uv sync --extra datadog`` for 
Datadog, ``uv sync --extra zeromq`` for ZeroMQ, or both ``uv sync --extra datadog --extra zeromq``.

## Configuration

Configuration options can be provided using the ``latency.toml`` file (in TOML format). By default, the program will 
look for it in the current running directory, otherwise you can use the ``-c`` or ``--config-file`` CLI argument to 
provide the absolute path (including the file name).

Example configuration:

```toml
name = "this-host"
max_size = 65535
tcp_port = 17171
udp_port = 17172

[[targets]]
host = "127.0.0.1"
label = "foo"
tags = ["isp:local", "location:laptop"]

[[targets]]
host = "10.0.0.2"
label = "bar"
tcp_port = 1717
udp_port = 1718
size = 65535

[[targets]]
host = "10.0.0.3"
label = "baz"
type = "udp"
interval = 200

[[targets]]
host = "lm.example.com"
timeout = 2

[metrics]
backend = "clickhouse"
host = "click.example.com"
username = "super"
password = "secure"
```

For every target you want to monitor, you can define a configuration block, with the following options:

```toml
[[targets]]
host = "<IP or hostname>"
label = "<label>"
type = "<TCP or UDP>"
rtt = <true or false>
tcp_latency = <true or false>
tcp_port = <TCP port>
udp_port = <UDP port>
size = <packet size in bytes>
interval = <interval in milliseconds>
timeout = <timeout in seconds>
tags = [<a list of metric tags>]
```

Any of these settings are optional, except the IP, of course, and are pretty self-explanatory. Each of these can be 
defined at individual target level, as well as top-level (for all the targets); in other words, target-level options 
inherit the values from top-level when not configured explicitly.

The default values are:

* TCP port: 8000
* UDP port: 8001
* Interval: 1000 (milliseconds)
* Timeout: 1 (second)
* Type: by default both TCP and UDP, unless you only want one
* RTT: whether you want both OWD and RTT measurements, by default ``true``, i.e., RTT values will be provided.
* TCP Latency: whether you want TCP latency measurements, over non-persistent TCP connections. Enabled by default.

While ``label`` is not mandatory, you might want to add it when the ``host`` is an IP address. This value will be set as
metric ``target`` tag (or label) when set, otherwise ``host`` will be used. Of course, when ``host`` is an actual 
hostname instead of an IP address, ``label`` may be superfluous -- but I'd probably advise always using IP addresses 
whenever possible to minimise the impact of other services, e.g., DNS.

The global settings can also be set from the command line, see ``--help``:

```bash
$ latency-monitor --help
usage: latency-monitor [-h] [-c CONFIG_FILE] [-n NAME] [-m {cli,log,zeromq,datadog,pushgateway,clickhouse}] [-l 
{DEBUG,INFO,WARNING,ERROR,CRITICAL}] [-f LOG_FILE] [-r | --rtt | --no-rtt] [-t | --tcp | --no-tcp] [-u | --udp 
| --no-udp] [--tcp-latency | --no-tcp-latency] [--tcp-port TCP_PORT] [--udp-port UDP_PORT] [-s MAX_SIZE] [-x MAX_LOST] [-T TIMEOUT] [-i MSECONDS]

Lightweight TCP and UDP latency monitoring tool

options:
  -h, --help            show this help message and exit
  -c, --config-file CONFIG_FILE
                        Path to configuration file
  -n, --name NAME       The local system name or label. Default: your-machine-name
  -m, --metrics {cli,log,zeromq,datadog,pushgateway,clickhouse}
                        The metrics backend to use (default: CLI)

Logging options:
  -l, --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logging level (default: INFO)
  -f, --log-file LOG_FILE
                        Path to log file (if omitted, logs to stdout)

Network options:
  -r, --rtt, --no-rtt   Enable RTT (use --no-rtt to disable, i.e., only OWD measurements)
  -t, --tcp, --no-tcp   Enable TCP monitoring for all probes (use --no-tcp to disable)
  -u, --udp, --no-udp   Enable UDP monitoring for all probes (use --no-udp to disable)
  --tcp-latency, --no-tcp-latency
                        Enable TCP latency monitoring without persistent connection (use --no-tcp-latency to disable)
  --tcp-port TCP_PORT   TCP port number to listen on. Default: 8000
  --udp-port UDP_PORT   UDP port number to listen on. Default: 8001
  -s, --max-size MAX_SIZE
                        Packet max size (in bytes). Default: 1470 bytes
  -x, --max-lost MAX_LOST
                        Number of consecutive lost packets that trigger re-connection.Default: 10

Runtime options:
  -T, --timeout TIMEOUT
                        Timeout in seconds. Default: 1.0 seconds
  -i, --interval MSECONDS
                        Interval between probes (in milliseconds). Default: 1000 milliseconds

Examples:
  Start in server mode, i.e., only listen to probes:
    latency-monitor

  Enable debug logging:
    latency-monitor -l DEBUG

  Disable RTT and TCP latency probing:
    latency-monitor -c latency.toml --no-tcp-latency --no-rtt

  Rapid UDP probing (every millisecond) only OWD:
    latency-monitor -c latency.toml --no-tcp --no-rtt -i 1
```

## Metrics Publishing

The tool supports pluggable metrics backends. Currently the following are available:

- Datadog
- ZeroMQ
- Clickhouse
- Pushgateway
- Cli
- Log

The last two are probably more important for debugging purposes, than actual production use.

It's very easy to add a new integration, so if you'd like to send your data elsewhere, feel free to open a PR.

## Usage

Once you have the configuration file in place, you can start the daemon (in foreground, won't return the command line 
until you stop via Ctrl-C):

```bash
$ latency-monitor -c /path/to/config.toml
```

> [!WARNING]
> Unlike something like Smokeping, this program MUST run on both sides of a given link. This is necessary particularly
> for OWD (one-way delay) results.

> [!NOTE]
> You will typically need to configure the metrics backend on both sides of a given link, as each will 
> provide different metrics.

There's also a basic API you can use from your programs, should you wish to build on top of this library:

```python
from latency_monitor.api import LatencyMonitor

# Create a monitor instance
monitor = LatencyMonitor()

# Add TCP endpoint
monitor.add_tcp_target("10.0.0.1", port=8000, label="foo")

# Add UDP endpoint
monitor.add_udp_target("10.0.0.2", port=5001, label="bar")

# Start monitoring
monitor.start()

# Pick metrics from the queue yourself. You'll need to invoke this in a separate thread or process than .start()
metric = monitor.metrics_q.get()
```

Naturally, the latency-monitor process must be started up and listening on the target hosts.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and code quality checks
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Setup

```bash
# Install development dependencies
pip install -e ".[dev]"

# Or using uv
uv sync --locked --dev

# Run code formatting
black .
isort .

# Run linters
pylint .
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Author

Mircea Ulinic ([@mirceaulinic](https://github.com/mirceaulinic))
