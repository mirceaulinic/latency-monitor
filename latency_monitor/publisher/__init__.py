# -*- coding: utf-8 -*-
from latency_monitor.publisher.datadog import Datadog
from latency_monitor.publisher.prometheus import Prometheus


class Publisher:
    def start():
        pass


__publishers__ = {
    "datadog": Datadog,
    "prometheus": Prometheus,
}
