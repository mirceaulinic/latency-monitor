# -*- coding: utf-8 -*-
"""
Latency Monitor
===============
"""

import argparse
import logging
import multiprocessing
import os
import signal
import sys
import textwrap
import time
import tomllib

import latency_monitor.defaults as defaults
from latency_monitor.core import (
    start_owd_tcp_clients,
    start_owd_udp_clients,
    start_tcp_latency_pollers,
    start_tcp_server,
    start_udp_server,
)
from latency_monitor.metrics import __metrics__

log = logging.getLogger(__name__)


def _start_proc(fun, *args, **opts):
    """
    Helper function to effectively start the TCP / UDP server session. This
    function only exists because due to DRY as these few lines are required in
    a couple of different places.
    """
    log.debug("Starting the process (%s)", fun)
    server = multiprocessing.Process(target=fun, args=args, kwargs=opts)
    server.daemon = True
    server.start()
    return server


def _sigkill(sig, frame):
    log.warning("Got terminated (signal: %s). Buh-bye now", sig)
    log.debug(frame)
    sys.exit(0)


def parse_args(opts):
    """
    Parse CLI arguments based on the config opts read from the config file.
    CLI overrides file.
    """
    parser = argparse.ArgumentParser(
        description="Lightweight TCP and UDP latency monitoring tool",
        epilog=textwrap.dedent(
            """
            Examples:
              Start in server mode, i.e., only listen to probes:
                latency-monitor

              Enable debug logging:
                latency-monitor -l DEBUG

              Disable RTT and TCP latency probing:
                latency-monitor -c latency.toml --no-tcp-latency --no-rtt

              Rapid UDP probing (every millisecond) only OWD:
                latency-monitor -c latency.toml --no-tcp --no-rtt -i 1
        """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-c",
        "--config-file",
        type=str,
        default=defaults.CFG_FILE,
        help="Path to configuration file",
    )
    parser.add_argument(
        "-n",
        "--name",
        type=str,
        default=opts["name"],
        help=f"The local system name or label. Default: {opts['name']}",
    )
    parser.add_argument(
        "-m",
        "--metrics",
        type=str,
        default="cli",
        choices=__metrics__.keys(),
        help="The metrics backend to use (default: CLI)",
    )

    logging_args = parser.add_argument_group("Logging options")
    logging_args.add_argument(
        "-l",
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=opts["log_level"],
        help=f"Logging level (default: {opts['log_level']})",
    )

    logging_args.add_argument(
        "-f",
        "--log-file",
        type=str,
        default=opts["log_file"],
        help="Path to log file (if omitted, logs to stdout)",
    )

    network_args = parser.add_argument_group("Network options")
    network_args.add_argument(
        "-r",
        "--rtt",
        action=argparse.BooleanOptionalAction,
        default=opts["rtt"],
        help="Enable RTT (use --no-rtt to disable, i.e., only OWD measurements)",
    )
    network_args.add_argument(
        "-t",
        "--tcp",
        action=argparse.BooleanOptionalAction,
        default=opts["tcp"],
        help="Enable TCP monitoring for all probes (use --no-tcp to disable)",
    )
    network_args.add_argument(
        "-u",
        "--udp",
        action=argparse.BooleanOptionalAction,
        default=opts["udp"],
        help="Enable UDP monitoring for all probes (use --no-udp to disable)",
    )
    network_args.add_argument(
        "--tcp-latency",
        action=argparse.BooleanOptionalAction,
        default=opts["tcp_latency"],
        help="Enable TCP latency monitoring without persistent connection "
        "(use --no-tcp-latency to disable)",
    )
    network_args.add_argument(
        "--tcp-port",
        type=int,
        default=opts["tcp_port"],
        help=f"TCP port number to listen on. Default: {opts['tcp_port']}",
    )
    network_args.add_argument(
        "--udp-port",
        type=int,
        default=opts["udp_port"],
        help=f"UDP port number to listen on. Default: {opts['udp_port']}",
    )
    network_args.add_argument(
        "-s",
        "--max-size",
        type=int,
        default=opts["max_size"],
        help=f"Packet max size (in bytes). Default: {opts['max_size']} bytes",
    )
    network_args.add_argument(
        "-x",
        "--max-lost",
        type=int,
        default=opts["max_lost"],
        help="Number of consecutive lost packets that trigger re-connection."
        f"Default: {opts['max_lost']}",
    )

    runtime_args = parser.add_argument_group("Runtime options")
    runtime_args.add_argument(
        "-T",
        "--timeout",
        type=float,
        default=opts["timeout"],
        help=f"Timeout in seconds. Default: {opts['timeout']} seconds",
    )
    runtime_args.add_argument(
        "-i",
        "--interval",
        type=float,
        metavar="MSECONDS",
        default=opts["interval"],
        help=f"Interval between probes (in milliseconds). Default: {opts['interval']} milliseconds",
    )

    return parser.parse_args()


def setup_logging(log_level, log_file=None):
    """
    Sets the appropriate logging level and creates the directories when logging
    to file.
    """
    handlers = [logging.StreamHandler()]
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    logging.basicConfig(
        level=numeric_level,
        format=defaults.LOG_FORMAT,
        handlers=handlers,
    )


def load_config(cfg_file, cfg):
    """
    Load the config from the TOML file and return the config opts, as a dict.
    """
    if not os.path.exists(cfg_file):
        log.critical("Unable to read the config file from %s", cfg_file)
        return cfg
    try:
        with open(cfg_file, "rb") as f:
            cfg.update(tomllib.load(f))
    except tomllib.TOMLDecodeError:
        log.critical("Unable to read the TOML file %s", cfg_file, exc_info=True)
    return cfg


def start(cli=True, args=None, metrics_q=None):
    """
    Starts one subprocess for each TCP and UDP servers that'll be listening for
    incoming connections, and another subprocess for a multi-threaded dispatcher
    for the targets.
    """
    opts = {
        "rtt": defaults.RTT,
        "tcp": defaults.TCP,
        "udp": defaults.UDP,
        "name": defaults.NAME,
        "timeout": defaults.TIMEOUT,
        "max_seq": defaults.MAX_SEQ,
        "interval": defaults.INTERVAL,
        "max_size": defaults.MAX_SIZE,
        "max_lost": defaults.MAX_LOST,
        "max_conn": defaults.MAX_CONN,
        "tcp_port": defaults.TCP_PORT,
        "udp_port": defaults.UDP_PORT,
        "log_level": defaults.LOG_LEVEL,
        "log_file": None,
        "tcp_latency": defaults.TCP_LATENCY,
    }
    signal.signal(signal.SIGTERM, _sigkill)
    signal.signal(signal.SIGINT, _sigkill)
    signal.signal(signal.SIGHUP, _sigkill)
    if cli:
        opts["metrics"] = {"backend": "cli"}
        initial_parser = argparse.ArgumentParser(add_help=False)
        initial_parser.add_argument(
            "-c",
            "--config-file",
            type=str,
            default=defaults.CFG_FILE,
            help="Path to the configuration file",
        )
        initial_args, _ = initial_parser.parse_known_args()
        if initial_args.config_file:
            opts = load_config(initial_args.config_file, opts)
        args = parse_args(opts)
    elif args.config_file:
        opts = load_config(args.config_file, opts)
    for key, _ in opts.items():
        if key != "metrics" and hasattr(args, key):
            opts[key] = getattr(args, key)
    setup_logging(args.log_level, log_file=args.log_file)
    bkend = opts.get("metrics", {}).get("backend")
    if bkend and bkend not in __metrics__:
        log.critical("You must select a valid metrics backend, exiting.")
        sys.exit(1)
    log.debug("This is the config we're gonna run: %s", opts)
    if not metrics_q:
        metrics_q = multiprocessing.Queue()
    if bkend:
        metrics = __metrics__[bkend](**opts)
    elif not cli:
        log.info(
            "No metrics backend configured, will skip assuming you're using the"
            "API. Otherwise, make sure you have a metrics backend configured."
        )
    metrics_w = poller = tcp_server = udp_server = owd_udp_ps = owd_tcp_ps = None
    while True:
        if bkend and (not metrics_w or not metrics_w.is_alive()):
            log.info("Starting the metrics worker")
            metrics_w = _start_proc(metrics.start, metrics_q)  # pylint: disable=E0606
        if opts["udp"] and (not udp_server or not udp_server.is_alive()):
            log.info("Starting the UDP server")
            udp_server = _start_proc(start_udp_server, metrics_q, **opts)
        if opts["tcp"] and (not tcp_server or not tcp_server.is_alive()):
            log.info("Starting the TCP server")
            tcp_server = _start_proc(start_tcp_server, metrics_q, **opts)
        if opts.get("targets"):
            if (
                opts["tcp"]
                and opts["tcp_latency"]
                and (not poller or not poller.is_alive())
            ):
                log.info("Starting the TCP latency process")
                poller = _start_proc(start_tcp_latency_pollers, metrics_q, **opts)
            if opts["udp"] and (not owd_udp_ps or not owd_udp_ps.is_alive()):
                log.info("Starting the UDP OWD process for the targets")
                owd_udp_ps = _start_proc(start_owd_udp_clients, metrics_q, **opts)
            if opts["tcp"] and (not owd_tcp_ps or not owd_tcp_ps.is_alive()):
                log.info("Starting the TCP OWD process for the targets")
                owd_tcp_ps = _start_proc(start_owd_tcp_clients, metrics_q, **opts)
        time.sleep(0.1)
