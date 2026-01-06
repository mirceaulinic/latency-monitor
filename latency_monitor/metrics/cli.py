# -*- coding: utf-8 -*-
"""
CLI publisher
=============
"""

import logging

from latency_monitor.defaults import FMT_MAP

log = logging.getLogger(__name__)


class Cli:
    """
    Print out the metrics on the command line, in real time, in the format of
    choice.
    """

    def __init__(self, **opts):
        """ """
        fmt = opts["metrics"].get("format", "json")
        self.fun = FMT_MAP.get(fmt)

    def start(self, pub_q):  # pylint: disable=C0116
        log.debug("Starting Cli publisher")
        while True:
            log.debug("[Cli Publisher] Waiting for a new metric")
            m = pub_q.get()
            log.debug("[Cli Publisher] Picked metric from the queue: %s", m)
            fmt_m = self.fun(m)
            print(fmt_m)
