# -*- coding: utf-8 -*-
"""
Datadog metrics backend
=======================
"""
import logging
import os
import time

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


class Datadog:
    """
    Accumulate metrics and ship them at specific intervals.
    """

    def __init__(self, **opts):
        self.opts = opts
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

    def start(self, metrics_q):
        """
        Worker that constantly checks if there's a new metric into the queue, then
        adds it to the metrics list or ships to Datadog.
        """
        metrics = []
        last_send = 0
        ship_metrics = []
        log.debug("Starting Datadog worker")
        send_interval = self.opts["metrics"].get("send_interval", 30)
        while True:
            log.debug("[Datadog] Waiting for a new metric")
            m = metrics_q.get()
            log.debug("[Datadog] Picked metric from the queue: %s", m)
            found = False
            for metric in metrics:
                if metric["metric"] == m["metric"] and set(metric["tags"]) == set(
                    m["tags"]
                ):
                    metric["points"].extend(m["points"])
                    log.debug("[Datadog] Known metric, adding the data points")
                    found = True
            if not found:
                log.debug(
                    "[Datadog] This is a new metric, adding it to the accumulator"
                )
                metrics.append(m)
            if time.time() - last_send > send_interval:
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
                                    MetricPoint(
                                        timestamp=int(p[0] / 1e9), value=p[1] / 1e6
                                    )
                                    for p in metric["points"]
                                ],
                                tags=metric["tags"],
                            )
                        ]
                    )
                    log.debug("[Datadog] Adding metric to be shipped: %s", dd_metric)
                    ship_metrics.append(dd_metric)
                metrics = []
                try:
                    self._dd_ship(ship_metrics)
                    ship_metrics = []
                    last_send = time.time()
                except Exception:  # pylint: disable=W0718
                    # Catching generic exception, let's not crash the worker
                    # because of some random failure such as Datadog API down.
                    log.error(
                        "[Datadog] Unable to send metrics, will try again later",
                        exc_info=True,
                    )
