# Metrics Backend: CLI

This is the default metrics backend, that simply prints out the metrics on the command line, in JSON format.

It only picks the metrics from the internal queue and prints them out on the screen. It may be helpful for debugging 
purposes or ad-hoc execution.

Example:

```bash
$ latency-monitor

{"metric": "udp.wan.owd", "points": [[1768219134587069267, 282072]], "tags": ["source:lh-8000", "target:lh-5000", "isp:local", "location:laptop"]}
{"metric": "udp.wan.owd", "points": [[1768219135587848936, 475226]], "tags": ["source:lh-8000", "target:lh-5000", "isp:local", "location:laptop"]}
{"metric": "udp.wan.owd", "points": [[1768219136587738882, 311126]], "tags": ["source:lh-8000", "target:lh-5000", "isp:local", "location:laptop"]}
{"metric": "udp.wan.owd", "points": [[1768219137588174749, 431802]], "tags": ["source:lh-8000", "target:lh-5000", "isp:local", "location:laptop"]}
{"metric": "udp.wan.owd", "points": [[1768219141281240642, 275681]], "tags": ["source:lh-8000", "target:lh-5000", "isp:local", "location:laptop"]}
{"metric": "udp.wan.owd", "points": [[1768219142282076679, 504806]], "tags": ["source:lh-8000", "target:lh-5000", "isp:local", "location:laptop"]}
{"metric": "udp.wan.owd", "points": [[1768219143282230580, 353287]], "tags": ["source:lh-8000", "target:lh-5000", "isp:local", "location:laptop"]}
```

It may be helpful when used in conjunction with [``jq``](https://jqlang.org/).
