# ZeroMQ

Using this backend, you are able to send your metrics over a ZeroMQ message bus, from where various programs or services 
can collect the metrics. Every metric is sent individually, as soon as it's produced.

This backend requires the ``pyzmq`` Python library, which can be installed separately, or using pip as an extra
dependency, e.g., ``pip install latency-monitor[zeromq]``.


Under the ``[metrics]`` block in the TOML configuration file, you can provide the following:

- ``address`` for the ZeroMQ socket. Default: ``0.0.0.0``.
- ``port`` of the ZeroMQ socket. Default: ``8002``.

Configuration example:

```toml
[metrics]
backend = "zeromq"
address = "192.168.0.1"
port = 5005
```
