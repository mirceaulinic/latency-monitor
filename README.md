![Latency Monitor](docs/images/logo.png)

# latency-monitor

TCP and UDP latency monitoring tool, with pluggable interface for publishing metrics.

## Features

- **TCP Latency Monitoring**: Monitor TCP connection latency one-way and round-trip to specified endpoints.
- **UDP Latency Monitoring**: Measure UDP one-way and round-trip time to target hosts.
- **Pluggable Metrics**: Flexible interface for publishing metrics to various backends
- **Configurable**: Easy configuration for monitoring targets and intervals, 
- **Lightweight**: Minimal resource footprint for continuous monitoring, so it can be executed on any operating system 
  (where Python is available).

## Installation

> **Note**: Package is not yet published to PyPI. This section describes future installation once the package is available.

Install from PyPI:

```bash
pip install latency-monitor
```

For development installation:

```bash
git clone https://github.com/mirceaulinic/latency-monitor.git
cd latency-monitor
uv sync --dev
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
backend = "prometheus"
port = 9090
```

For every target you want to monitor, you can define a configuration block, with the following options:

```toml
[[targets]]
host = "<IP or hostname>"
label = "<label>"
type = "<TCP or UDP>"
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
* Size: 1470 (bytes)
* Interval: 1000 (milliseconds)
* Timeout: 1 (second)
* Type: by default both TCP and UDP, unless you only want one

While ``label`` is not mandatory, you might want to add it when the ``host`` is an IP address. This value will be set as
metric ``target`` tag (or label) when set, otherwise ``host`` will be used. Of course, when ``host`` is an actual 
hostname instead of an IP address, ``label`` may be superfluous -- but I'd probably advise always using IP addresses 
whenever possible to minimise the impact of other services, e.g., DNS.

## Metrics Publishing

The tool supports pluggable metrics backends:

- Datadog
- Prometheus
- Cli
- Log

The last two are probably more important for debugging purposes, than actual production use.

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

# Run code formatting
black .
isort .

# Run linters
pylama .
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Author

Mircea Ulinic ([@mirceaulinic](https://github.com/mirceaulinic))
