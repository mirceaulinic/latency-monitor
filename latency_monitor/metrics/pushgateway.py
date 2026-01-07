# -*- coding: utf-8 -*-
"""
Prometheus metrics backend
==========================
"""
import copy
import logging

from latency_monitor.metrics.accumulator import Accumulator

try:
    from prometheus_client import CollectorRegistry, Gauge, Info, push_to_gateway

    HAS_PROM = True
except ImportError:
    HAS_PROM = False

log = logging.getLogger(__name__)


class Pushgateway(Accumulator):
    """
    Accumulate metrics and push them to the Prometheus gateway.
    """

    def __init__(self, **opts):
        super().__init__(**opts)
        self.gateway = self.opts["metrics"]["gateway"]
        self.job = self.opts["metrics"].get("job", "latency-monitor")

    def _push_metrics(self, metrics):
        """
        Build the metrics and push them to the Prometheus gateway.
        """
        registry = CollectorRegistry()
        extra_info = Info(self.job, "Latency monitoring metrics", registry=registry)
        extra_info.info({"instance": self.opts["name"]})
        for m in metrics:
            labels = dict(map(lambda t: t.split(":"), m["tags"]))
            g = Gauge(
                m["metric"].replace(".", "_"),
                m["metric"],
                list(labels.keys()) + ["instance", "timestamp"],
                registry=registry,
            )
            for p in m["points"]:
                l = copy.deepcopy(labels)
                l["timestamp"] = p[0]
                l["instance"] = self.opts["name"]
                g.labels(**l).set(p[1])

        push_to_gateway(self.gateway, job=self.job, registry=registry)
