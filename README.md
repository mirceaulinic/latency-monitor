# latency-monitor

TCP and UDP latency monitoring tool, with pluggable interface for publishing metrics.

## Features

- **TCP Latency Monitoring**: Monitor TCP connection latency to specified endpoints
- **UDP Latency Monitoring**: Measure UDP round-trip time to target hosts
- **Pluggable Metrics**: Flexible interface for publishing metrics to various backends
- **Configurable**: Easy configuration for monitoring targets and intervals
- **Lightweight**: Minimal resource footprint for continuous monitoring

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
uv sync
```

## Configuration

Configuration options can be provided using the ``latency.toml`` file (in TOML format). By default, the program will 
look for it in the current running directory, otherwise you can use the ``-c`` or ``--config-file`` CLI argument to 
provide the absolute path (including the file name).

Example configuration:

```toml
name = "this-host"

[targets."10.0.0.1"]
label = "some-host"

[targets."10.0.0.2"]
label = "other-host"
port = 1717

[targets."10.0.0.3"]
label = "dummy-target"
interval = 10

[metrics]
backend = "prometheus"
port = 9090
```

For every target you want to monitor, you can define a configuration block, with the following options:

```toml
[targets."<IP>"]
label = "<label>"
port = <port>
interval = <interval>
type = <TCP or UDP>
```

Any of these settings are optional, except the IP, of course, and are pretty self-explanatory.
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

There's also a basic API you can use from your programs, should you wish to build on top of this library:

```python
from latency_monitor import LatencyMonitor

# Create a monitor instance
monitor = LatencyMonitor()

# Add TCP endpoint
monitor.add_tcp_target("10.0.0.1", port=8000)

# Add UDP endpoint
monitor.add_udp_target("10.0.0.2, port=5001)

# Start monitoring
monitor.start()

# Pick metrics from the queue yourself. You'll need to invoke this in a separate thread than .start()
metric = monitor.pub_q.get()
```

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
