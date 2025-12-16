# -*- coding: utf-8 -*-
"""
Prometheus metrics backend
==========================
"""
import logging
import time

log = logging.getLogger(__name__)


class Prometheus:
    def __init__(self, **opts):
        """ """
        pass

    def start(self, pub_q, **opts):
        """
        Worker that constantly checks if there's a new metric into the queue, then
        adds it to the metrics accumulator for Prometheus to scrape it.
        """
        metrics = []
        # last_send = 0
        # ship_metrics = []
        log.debug("Starting Prometheus worker")
        # send_interval = opts["metrics"].get("send_interval", 30)
        while True:
            log.debug("[Prometheus] Waiting for a new metric")
            m = pub_q.get()
            log.debug("[Prometheus] Picked metric from the queue: %s", m)
            found = False
            for metric in metrics:
                if metric["metric"] == m["metric"] and set(metric["tags"]) == set(
                    m["tags"]
                ):
                    metric["points"].extend(m["points"])
                    log.debug("[Prometheus] Known metric, adding the data points")
                    found = True
            if not found:
                log.debug(
                    "[Prometheus] This is a new metric, adding it to the accumulator"
                )
                metrics.append(m)
            time.sleep(0.01)
