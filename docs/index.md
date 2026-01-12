# Latency Monitor

``latency-monitor`` is a lightweight tool for high precision and granularity monitoring over TCP and UDP, with 
pluggable interface for metrics publishing.

## Features

- **TCP Latency Monitoring**: Monitor TCP connection latency one-way and round-trip to specified endpoints.
- **UDP Latency Monitoring**: Measure UDP one-way and round-trip time to target hosts.
- **Pluggable Metrics**: Flexible interface for publishing metrics to various backends
- **Configurable**: Easy configuration for monitoring targets and intervals.
- **Precision**: Measurements are collected in nanoseconds, and probes can be executed every millisecond. This is ideal
  for capturing micro-bursts, or rapidly changing environments.
- **Stable**: TCP measurements takes place over established connections to reduce the impact of firewalls or other
  intermediary systems. Each probing pair is one flow, maintained while the link is being monitored.
- **Lightweight**: Minimal resource footprint for continuous monitoring, so it can be executed on any operating system 
  (where Python is available).

The tool is meant to be executed on both sides of a monitored link, see [Architecture](arch.md) to understand why and 
what's happening under the hood.

By default, the tool produces the following metrics, with nanosecond precision:

- ``tcp.wan.owd``: OWD (one-way delay) from A to B, over an established TCP connection.
- ``tcp.wan.rtt``: RTT (round-trip time) from A to B, and back to A, over an established TCP connection.
- ``udp.wan.owd``: OWD from A to B, over UDP.
- ``udp.wan.rtt``: RTT from A to B and back to A, over UDP.
- ``tcp.wan.latency``: TCP latency between A and B (round-trip), but a new TCP connection is created with every probe. 
  This is somewhat similar to ``tcp.wan.rtt`` but likely will have a lot more jitter.

There are configuration options to disable monitoring for some of these individually. The configuration options and the
default settings are detailed under the [Usage and Configuration](usage.md) section.

For installation details, see [Installation](install.md), or [Docker](docker.md) if you prefer a containerised environment.

The following backends are currently available for publishing metrics:

- [Cli](metrics/cli.md)
- [Log](metrics/log.md)
- [Clickhouse](metrics/clickhouse.md)
- [Datadog](metrics/datadog.md)
- [Pushgateway](metrics/pushgateway.md)
- [ZeroMQ](metrics/zeromq.md)
