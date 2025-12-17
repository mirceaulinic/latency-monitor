# -*- coding: utf-8 -*-
from latency_monitor.publisher.cli import Cli
from latency_monitor.publisher.datadog import Datadog
from latency_monitor.publisher.log import Log
from latency_monitor.publisher.prometheus import Prometheus
from latency_monitor.publisher.zeromq import ZeroMQ

__publishers__ = {
    "cli": Cli,
    "log": Log,
    "zeromq": ZeroMQ,
    "datadog": Datadog,
    "prometheus": Prometheus,
}
