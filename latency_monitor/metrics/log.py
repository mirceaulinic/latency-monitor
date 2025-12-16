# -*- coding: utf-8 -*-
"""
Log publisher
=============

Receives the metrics objects and logs them at the desired logging level
(Warning, by default).
"""

import logging

from latency_monitor.defaults import FMT_MAP

log = logging.getLogger(__name__)


class Log:
    def __init__(self, **opts):
        """ """
        log_level = opts["metrics"].get("level", "warning")
        if log_level and hasattr(log, log_level):
            self.fun = getattr(log, log_level)
        else:
            self.fun = log.warning
        fmt = opts["metrics"].get("format", "json")
        self.fmt = FMT_MAP.get(fmt)

    def start(self, pub_q, **opts):
        """ """
        log.debug("Starting Log publisher")
        while True:
            log.debug("[Log Publisher] Waiting for a new metric")
            m = pub_q.get()
            log.debug("[Log Publisher] Picked metric from the queue: %s", m)
            fmt_m = self.fmt(m)
            self.fun(fmt_m)
