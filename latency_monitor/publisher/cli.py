# -*- coding: utf-8 -*-
"""
CLI publisher
=============
"""

import json
import logging
import tomllib

log = logging.getLogger(__name__)

FMT_MAP = {
    "json": json.dumps,
}


class Cli:
    def __init__(self, **opts):
        """ """
        fmt = opts.get("cli_publisher", {}).get("format", "json")
        self.fun = FMT_MAP.get(fmt)

    def start(self, pub_q, **opts):
        """ """
        log.debug("Starting Cli publisher")
        while True:
            log.debug("[Cli Publisher] Waiting for a new metric")
            m = pub_q.get()
            log.debug("[Cli Publisher] Picked metric from the queue: %s", m)
            fmt_m = self.fun(m)
            print(fmt_m)
