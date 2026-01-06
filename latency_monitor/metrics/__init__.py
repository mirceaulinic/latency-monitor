# -*- coding: utf-8 -*-
"""
Metrics backends
================
"""

from latency_monitor.metrics.cli import Cli
from latency_monitor.metrics.datadog import Datadog
from latency_monitor.metrics.log import Log
from latency_monitor.metrics.prometheus import Prometheus
from latency_monitor.metrics.zeromq import ZeroMQ

__metrics__ = {
    "cli": Cli,
    "log": Log,
    "zeromq": ZeroMQ,
    "datadog": Datadog,
    "prometheus": Prometheus,
}
