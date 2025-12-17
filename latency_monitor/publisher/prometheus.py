# -*- coding: utf-8 -*-
"""
Prometheus publisher
"""


class Prometheus:
    def __init__(self, **opts):
        """ """
        pass

    def start(sel, pub_q, **opts):
        """
        Worker that constantly checks if there's a new metric into the queue, then
        adds it to the metrics list or ships to Datadog.
        """
        metrics = []
        last_send = 0
        ship_metrics = []
        log.debug("Starting Datadog worker")
        wait_time = opts["runs"] * opts["interval"]
        while True:
            log.debug("[Datadog] Waiting for a new metric")
            m = pub_q.get()
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
            time.sleep(0.01)
