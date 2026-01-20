# -*- coding: utf-8 -*-
"""
Datadog metrics backend
=======================
"""

import logging
import os

from latency_monitor.metrics.accumulator import Accumulator

try:
    from datadog_api_client import ApiClient, Configuration
    from datadog_api_client.v2.api.metrics_api import MetricsApi
    from datadog_api_client.v2.model.metric_intake_type import MetricIntakeType
    from datadog_api_client.v2.model.metric_payload import MetricPayload
    from datadog_api_client.v2.model.metric_point import MetricPoint
    from datadog_api_client.v2.model.metric_series import MetricSeries

    HAS_DD = True
except ImportError:
    HAS_DD = False

log = logging.getLogger(__name__)


class Datadog(Accumulator):
    """
    Accumulate metrics and ship them at specific intervals.
    """

    def __init__(self, **opts):
        super().__init__(**opts)
        dd_site = os.environ.get("DD_SITE", self.opts["metrics"]["site"])
        api_key = os.environ.get("DD_API_KEY", self.opts["metrics"]["api_key"])
        self.cfg = Configuration()
        self.cfg.server_variables["site"] = dd_site
        if api_key:
            self.cfg.api_key["apiKeyAuth"] = api_key

    def _dd_ship(self, metrics):
        """
        Ships the metrics to Datadog.
        """
        with ApiClient(self.cfg) as api_client:
            api_instance = MetricsApi(api_client)
            for metric in metrics:
                if not metric:
                    continue
                response = api_instance.submit_metrics(body=metric)
                log.debug(response)

    def _push_metrics(self, metrics):
        """
        Build the Datadog metrics objects and send them.
        """
        ship_metrics = []
        for metric in metrics:
            dd_metric = MetricPayload(
                series=[
                    MetricSeries(
                        metric=metric["metric"],
                        type=MetricIntakeType.GAUGE,
                        points=[
                            # datapoints are by default in nanoseconds,
                            # and Datadog needs seconds, int values.
                            # TODO: the values are assumed ms by default,
                            # we may change that to us or something else.
                            MetricPoint(timestamp=int(p[0] / 1e9), value=p[1] / 1e6)
                            for p in metric["points"]
                        ],
                        tags=metric["tags"],
                    )
                ]
            )
            log.debug("[Datadog] Adding metric to be shipped: %s", dd_metric)
            ship_metrics.append(dd_metric)
        self._dd_ship(ship_metrics)
