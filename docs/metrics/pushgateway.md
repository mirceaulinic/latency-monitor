# Prometheus Pushgateway

Prometheus scraping wouldn't really work have super frequent scrapes (which defeats the purpose of Prometheus), or you 
have very rare probing (which somewhat defeats the purpose of ``latency-monitor``). But if you do need to use Prometheus 
for some reason, Pushgateway may be a better fit -- but with a major caveat: since the metrics can't be pushed at the 
same frequency as the probing, there'll be multiple metric samples in one push. Because of that, there'll be 
a ``timestamp`` label, which practically creates a separate metric family with every sample. That's not ideal, but if 
you have a constraint for whatever reason, there's not much else we can do.

Anyway, if that suits your needs, this backend requires the ``prometheus-client`` library, that you can install, for 
example using the extra dependency: ``pip install latency-monitor[pushgateway]``.

The following settings can be configured:

- ``gateway``: the address of the Prometheus Pushgateway endpoint.
- ``job``: the job name, not required; by default this value will be latency-monitor.
- ``send_interval``: the interval to push the metrics, in seconds. Default: 30.

Configuration example:

```toml
[metrics]
backend = "pushgateway"
gateway = "https://pushgw.example.com"
send_inteval = 60
```
