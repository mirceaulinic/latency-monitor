# -*- coding: utf-8 -*-
"""
Base class for the metrics accumulator.
"""

import logging
import time

log = logging.getLogger(__name__)


class Accumulator:
    """
    Accumulate metrics and push them when needed.
    """

    def __init__(self, **opts):
        self.opts = opts
        self.name = self.__class__.__name__

    def _push_metrics(self, metrics):
        """
        Build the metrics and push them to the service of choice.
        """

    def start(self, pub_q):
        """
        Worker that constantly checks if there's a new metric into the queue, then
        invokes the _push_metrics private method, which is specific to each
        backend.
        """
        last_send = 0
        metrics = []
        send_interval = self.opts["metrics"].get("send_interval", 30)
        log.debug("Starting %s worker", self.name)
        while True:
            log.debug("[%s] Waiting for a new metric", self.name)
            m = pub_q.get()
            log.debug("[%s] Picked metric from the queue: %s", self.name, m)
            found = False
            for metric in metrics:
                if metric["metric"] == m["metric"] and set(metric["tags"]) == set(
                    m["tags"]
                ):
                    metric["points"].extend(m["points"])
                    log.debug("[%s] Known metric, adding the data points", self.name)
                    found = True
            if not found:
                log.debug(
                    "[%s] This is a new metric, adding it to the accumulator", self.name
                )
                metrics.append(m)
            if time.time() - last_send > send_interval:
                try:
                    self._push_metrics(metrics)
                    metrics = []
                    last_send = time.time()
                except Exception:  # pylint: disable=W0718
                    log.error(
                        "[%s] Unable to send metrics, will try again later",
                        self.name,
                        exc_info=True,
                    )
            time.sleep(0.01)
