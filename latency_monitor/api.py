# -*- coding: utf-8 -*-
"""
Latency Monitor API
===================

Allows you to start the workers, and you can pick yourself the metrics from the
queue and do whatever you want with them.
"""

import multiprocessing

from latency_monitor.defaults import LOG_LEVEL, TCP_PORT, UDP_PORT
from latency_monitor.main import start


class Args:
    """
    Mocks the behaviour of the CLI args, so we can pass in an object that
    provides the initial options such as config file path, without changing the
    way we're handling that into the core code.
    """

    config_file = None
    log_level = LOG_LEVEL
    tcp_port = TCP_PORT
    udp_port = UDP_PORT
    log_file = None  # but hopefully you'll write the logs somewhere

    def __init__(self, **args):
        """
        Applies any value as a CLI-like argument.
        """
        for arg, val in args.items():
            setattr(self, arg, val)


class LatencyMonitor:
    """
    This is the main API class that we can use to instantiate the latency
    monitor, without running from the command line.
    """

    def __init__(self, **args):
        self.args = Args(**args)
        self.opts = {}  # TODO: need to find a way to inject the opts here
        self.metrics_q = multiprocessing.Queue()

    def add_target(self, addr, **target_cfg):
        """
        Adds a target to the list of probes.
        """
        target_cfg["host"] = addr
        self.opts["targets"].append(target_cfg)

    def add_tcp_target(self, addr, **target_cfg):
        """
        Adds a TCP target to the list of probes.
        """
        target_cfg["type"] = "tcp"
        if "port" in target_cfg:
            target_cfg["tcp_port"] = target_cfg["port"]
        self.add_target(addr, **target_cfg)

    def add_udp_target(self, addr, **target_cfg):
        """
        Adds an UDP target to the list of probes.
        """
        target_cfg["type"] = "udp"
        if "port" in target_cfg:
            target_cfg["udp_port"] = target_cfg["port"]
        self.add_target(addr, **target_cfg)

    def start(self):
        """
        Start it up when you're feeling ready!
        """
        start(cli=False, args=self.args, metrics_q=self.metrics_q)
