# -*- coding: utf-8 -*-
from latency_monitor.publisher.datadog import Datadog
from latency_monitor.publisher.prometheus import Prometheus

__publishers__ = {
    "datadog": Datadog,
    "prometheus": Prometheus,
}
