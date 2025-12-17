# -*- coding: utf-8 -*-
""" """

import argparse
import logging
import multiprocessing
import os
import signal
import sys
import textwrap
import tomllib

from latency_monitor.core import *
from latency_monitor.publisher import __publishers__

log = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Lightweight TCP and UDP latency monitoring tool",
        epilog=textwrap.dedent(
            """
            Examples:
              Run with defaults:
                latency-monitor -c latency.toml

              Run 10 times with 1s interval:
                latency-monitor -i 1 -t 2 -r 10

              Enable debug logging:
                latency-monitor -l DEBUG
        """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-c",
        "--config-path",
        type=str,
        default=os.path.join(os.getcwd(), "latency.toml"),
        help="Path to configuration file",
    )

    logging_args = parser.add_argument_group("Logging options")
    logging_args.add_argument(
        "-l",
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    logging_args.add_argument(
        "-f",
        "--log-file",
        type=str,
        help="Path to log file (if omitted, logs to stdout)",
    )

    network_args = parser.add_argument_group("Network options")
    network_args.add_argument(
        "-t", "--tcp-port", type=int, default=8000, help="TCP port number to listen on"
    )

    network_args.add_argument(
        "-u", "--udp-port", type=int, default=8001, help="UDP port number to listen on"
    )

    runtime_args = parser.add_argument_group("Runtime options")
    runtime_args.add_argument(
        "-T", "--timeout", type=float, default=1.0, help="Timeout in seconds"
    )

    runtime_args.add_argument(
        "-r", "--runs", type=int, default=30, help="Number of runs to execute"
    )

    runtime_args.add_argument(
        "-i",
        "--interval",
        type=float,
        metavar="SECONDS",
        default=1.0,
        help="Interval between runs in seconds",
    )

    return parser.parse_args()


def _start_proc(fun, *args, **opts):
    """
    Helper function to effectively start the TCP / UDP server session. This
    function only exists because due to DRY as these few lines are required in
    a couple of different places.
    """
    log.info("Starting the process (%s)", fun)
    server = multiprocessing.Process(target=fun, args=args, kwargs=opts)
    server.daemon = True
    server.start()
    return server


def _sigkill(signal, frame):
    log.warning("Got terminated. Buh-bye now")
    sys.exit(0)


def start(cli=True, args=None, pub_q=None):
    """
    Starts one subprocess for each TCP and UDP servers that'll be listening for
    incoming connections, and another subprocess for a multi-threaded dispatcher
    for the targets.
    For Datadog, we have a separate subprocess that picks the metrics from the
    queue and ships them when we have sufficient data points.
    """
    if cli:
        args = parse_args()
    signal.signal(signal.SIGTERM, _sigkill)
    cfg_path = args.config_path or os.path.join(os.getcwd(), "latency.toml")
    if not os.path.exists(cfg_path):
        log.critical("Unable to read the config file from %s", cfg_path)
        sys.exit(1)
    try:
        with open(cfg_path, "rb") as f:
            opts = tomllib.load(f)
    except tomllib.TOMLDecodeError as tde:
        log.critical("Unable to read the TOML file %s", cfg_path, exc_info=True)
        sys.exit(1)
    log_level = opts.get("log_level") or args.log_level
    if hasattr(logging, log_level):
        logging.basicConfig(level=getattr(logging, log_level))
    pub_name = opts.get("metrics", {}).get("backend")
    if pub_name and pub_name not in __publishers__:
        log.critical("You must select a valid publisher, exiting.")
        sys.exit(1)
    log.debug("Merging file configuration with CLI args")
    for opt in ("tcp_port", "udp_port", "runs", "timeout", "interval"):
        if opt not in opts:
            opts[opt] = getattr(args, opt)
    log.debug("These is the config we're gonna run: %s", opts)
    if not pub_q:
        pub_q = multiprocessing.Queue()
    if pub_name:
        publisher = __publishers__[pub_name](**opts)
    else:
        log.warning(
            "No Publisher configured, will skip assuming you're using the API. Otherwise, make sure you have a metrics backend configured."
        )
    pub_proc = poller = tcp_server = udp_server = owd_udp_ps = owd_tcp_ps = None
    while True:
        if pub_name and (not pub_proc or not pub_proc.is_alive()):
            log.info("Looks like the Publisher process got terminated for some reason")
            pub_proc = _start_proc(publisher.start, pub_q, **opts)
        if not udp_server or not udp_server.is_alive():
            log.info("Looks like the UDP server got terminated for some reason")
            udp_server = _start_proc(start_udp_server, pub_q, **opts)
        if not tcp_server or not tcp_server.is_alive():
            log.info("Looks like the TCP server got terminated for some reason")
            tcp_server = _start_proc(start_tcp_server, pub_q, **opts)
        if not poller or not poller.is_alive():
            log.info("Looks like the TCP latency process got terminated")
            poller = _start_proc(start_tcp_latency_pollers, pub_q, **opts)
        if not owd_udp_ps or not owd_udp_ps.is_alive():
            log.info("Looks like the UDP OWD process for the clients got terminated")
            owd_udp_ps = _start_proc(start_owd_udp_clients, pub_q, **opts)
        if not owd_tcp_ps or not owd_tcp_ps.is_alive():
            log.info("Looks like the TCP OWD process for the clients got terminated")
            owd_tcp_ps = _start_proc(start_owd_tcp_clients, pub_q, **opts)
        time.sleep(0.1)
