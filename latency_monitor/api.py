# -*- coding: utf-8 -*-
""" """


class LatencyMonitor:
    def __init__(self, **opts):
        self.opts = opts

    def add_target(self, label, addr, tags=None):
        self.targets[label] = {
            "host": addr,
            "tags": tags,
        }

    def add_tcp_target(self, label, addr, tags=None):
        self.targets[label] = {
            "host": addr,
            "tags": tags,
            "type": "tcp",
        }

    def add_udp_target(self, label, addr, tags=None):
        self.targets[label] = {
            "host": addr,
            "tags": tags,
            "type": "udp",
        }

    def start(self, **opts):
        pass
