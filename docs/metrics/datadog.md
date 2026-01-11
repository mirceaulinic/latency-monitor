# Datadog

Pushes metrics to Datadog, via the API. This backend requires the ``datadog-api-client`` Python library, which can be 
installed separately, or using pip as an extra dependency, e.g., ``pip install latency-monitor[datadog]``.

In order to avoid DDoS-ing the Datadog API, the metrics are aggregated and sent every 30 seconds. The send interval can 
be adjusted using the ``send_interval`` setting under the ``[metrics]`` block.

This integration requires at minimum two bits of information:

- ``site``: this is the address of the Datadog site. Alternatively you can provide that as the ``DD_SITE`` environment 
  variable. See [https://docs.datadoghq.com/getting_started/site/](https://docs.datadoghq.com/getting_started/site/) for 
  the available choices.
- ``api_key``: the Datadog API key. You can also provide it as the ``DD_API_KEY`` environment variable.
  [https://docs.datadoghq.com/cloudcraft/getting-started/generate-api-key/](https://docs.datadoghq.com/cloudcraft/getting-started/generate-api-key/)
  explains how to create an API key.

Configuration example:

```toml
[metrics]
backend = "datadog"
site = "datadoghq.eu"
api_key = "<api key goes here>"
send_interval = 60  # seconds
```
