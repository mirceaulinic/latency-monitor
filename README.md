# latency-monitor

TCP and UDP latency monitoring tool, with pluggable interface for publishing metrics.

## Features

- **TCP Latency Monitoring**: Monitor TCP connection latency to specified endpoints
- **UDP Latency Monitoring**: Measure UDP round-trip time to target hosts
- **Pluggable Metrics**: Flexible interface for publishing metrics to various backends
- **Configurable**: Easy configuration for monitoring targets and intervals
- **Lightweight**: Minimal resource footprint for continuous monitoring

## Installation

Install from PyPI:

```bash
pip install latency-monitor
```

For development installation:

```bash
git clone https://github.com/mirceaulinic/latency-monitor.git
cd latency-monitor
pip install -e .
```

## Usage

Basic usage example:

```python
from latency_monitor import LatencyMonitor

# Create a monitor instance
monitor = LatencyMonitor()

# Add TCP endpoint
monitor.add_tcp_target("example.com", 80)

# Add UDP endpoint
monitor.add_udp_target("example.com", 53)

# Start monitoring
monitor.start()
```

## Configuration

Configuration options can be provided via:
- Configuration file (YAML/JSON)
- Environment variables
- Direct API calls

Example configuration:

```yaml
targets:
  - type: tcp
    host: example.com
    port: 80
    interval: 60
  - type: udp
    host: example.com
    port: 53
    interval: 30

metrics:
  backend: prometheus
  port: 9090
```

## Metrics Publishing

The tool supports pluggable metrics backends:
- Prometheus
- InfluxDB
- CloudWatch
- Custom backends via plugin interface

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
flake8 .

# Run tests
pytest
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Author

Mircea Ulinic ([@mirceaulinic](https://github.com/mirceaulinic))
