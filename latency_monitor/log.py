# -*- coding: utf-8 -*-
"""
Latency Monitoring Logging
==========================
"""
import logging

log = logging.getLogger(__name__)


class Log:
    def _msg(base, *args, **kwargs):
        msg = base.format(*args)
