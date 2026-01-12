# Usage and Configuration

As noted in a few different places, it is important to understand that ``latency-monitor`` is specifically designed to 
be running on both sides of every link / path / route you want to monitor. Please read [Architecture](arch.md) for more 
details.

There are three blocks of configuration:

1. General settings
2. Target-specific settings
3. Backend-specific

## General Settings

The following options can be configured at the top of the TOML configuration file. These are also available as command 
line arguments, which override the configuration file settings when provided.

### ``name``: ``<your machine name>``

A human-friendly name for the ``latency-monitor`` instance, that'll be used for the packet exchange and applied as the 
source tag / label on the metrics. By default, if not provided, it'll be the hostname of the local machine. On the CLI 
the argument is ``--name``.

Configuration example:

```toml
name = "this-host"
```

### ``address``: ``0.0.0.0``

This is the address the TCP and UDP servers will be listening on for connections.

Usage example:

```toml
address = "192.168.0.1"
```

### ``tcp_port``: 8000

The TCP port for incoming connections. The CLI argument is ``--tcp-port``.

Configuration example:

```toml
tcp_port = 1234
```

### ``udp_port``: 8001

The UDP port for incoming connections. The CLI argument is ``--udp-port``.

Configuration example:

```toml
udp_port = 1235
```

### ``max_size``: 1470 (bytes)

This is the maximum payload size in bytes. If the packet size is larger than this value, then the probe will fail to 
unpack the data, which will result in your TCP / UDP clients constantly re-spawning without producing any results. 
Normally, you don't need to adjust this value, unless you use the ``size`` under the target-specific settings.

If you have a custom packet size for some targets, then you need to configure the same value on *both* latency-monitor 
instances, as ``max_size``.

Configuration example:

```toml
max_size = 65535
```

### ``rtt``: ``true``

This flag tells whether we want RTT measurements, or only OWD. It is the CLI equivalent of the ``--rtt`` flag.

Configuration example:

```toml
rtt = false
```

## Target-specific settings

For every target, you can configure separate settings. Every target will require a ``[[targets]]`` block. Example:

```toml
[[targets]]
host = "10.0.0.1"
label = "some-host"

[[targets]]
host = "10.0.0.2"
label = "other-host"
```

### ``host``

This value always needs to be provided, it's the IP or resolvable hostname of the remote-end instance. It's always best 
to use the IP address, so you don't rely on DNS, but you do you.

### ``label``

Optional setting, provides a human-friendly name for target. When this value is not provided, then the metrics will have 
the host as the ``target`` tag / label.

### ``tcp_port``: 8000

The port of the remote-end ``latency-monitor`` TCP server. It defaults to the value of the local TCP server,
``tcp_port``, from the general settings, 8000.

Configuration example:

```toml
[[targets]]
host = "10.0.0.1"
tcp_port = 12345
```

### ``udp_port``: 8001

The port of the remote-end ``latency-monitor`` UDP server. It defaults to the value of the local UDP server, 
``udp_port``, from the general settings, 8001.

Configuration example:

```toml
[[targets]]
host = "10.0.0.1"
udp_port = 12346
```

### ``type``

The probe type, choose between ``tcp`` and ``udp``, if you only want one. If this value is not provided, then both TCP 
and UDP monitoring are enabled, by default.

Configuration example:

```toml
[[targets]]
host = "10.0.0.1"
type = "udp"
```

### ``tags``

A list of additional tags (or labels) applied to the metrics. Every tag needs to be in the format: ``<label>:<value>``.
By default, every metric, will have the ``source`` and ``target`` labels applied.

Configuration example:

```toml
[[targets]]
host = "10.0.0.1"
tags = ["isp:local", "location:home", "size:small"]
```

### ``size``

The probe payload size in bytes. By default, the packets only contain the information detailed in the 
[Architecture](arch.md) section, without the padding. Therefore the packets may be small (unless you apply a large 
number of tags). If you want to increase the size, you can use this value, and model the behaviour for larger payloads. 
This can be particularly useful for UDP.

Configuration example:

```toml
[[targets]]
host = "10.0.0.1"
size = 65500
```

IMPORTANT: if you adjust this size, you will also need to configure ``max_size`` on the remote-end accordingly.

### ``rtt``: ``true``

This is the probe-level equivalent of the general ``rtt`` configuration option. The value is inherited from the general 
one, if not provided.

Configuration example:

```toml
[[targets]]
host = "10.0.0.1"
rtt = false
```

## Backend-specific settings

These are documented individually for every metrics backend.
