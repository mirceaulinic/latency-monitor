# -*- coding: utf-8 -*-
""" """

import multiprocessing

from latency_monitor.main import start


class Args:
    config_path = None
    log_level = "INFO"
    tcp_port = 8000
    udp_port = 8001
    publisher = None

    def __init__(self, **args):
        for arg, val in args.items():
            setattr(self, arg, val)


class LatencyMonitor:
    def __init__(self, **args):
        self.args = Args(**args)
        self.pub_q = multiprocessing.Queue()

    def add_target(self, label, addr, tags=None):
        self.opts["targets"][addr] = {
            "label": label,
            "tags": tags,
        }

    def add_tcp_target(self, label, addr, tags=None):
        self.opts["targets"][addr] = {
            "label": label,
            "tags": tags,
            "type": "tcp",
        }

    def add_udp_target(self, label, addr, tags=None):
        self.opts["targets"][addr] = {
            "label": label,
            "tags": tags,
            "type": "udp",
        }

    def start(self):
        start(cli=False, args=self.args, pub_q=self.pub_q)
