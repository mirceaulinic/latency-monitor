# -*- coding: utf-8 -*-
""" """

import argparse
import textwrap
import logging
import multiprocessing
import signal
import tomllib


def parse_args():
    parser = argparse.ArgumentParser(
        description="",
        epilog=textwrap.dedent(
            """
            Examples:
              Run with defaults:
                app.py -c config.yaml

              Run 10 times with 1s interval:
                app.py -r 10 -i 1

              Enable debug logging and write to file:
                app.py -l DEBUG -f app.log
        """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-c", "--config-path", type=str, help="Path to configuration file"
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


def start():
    """
    Starts one subprocess for each TCP and UDP servers that'll be listening for
    incoming connections, and another subprocess for a multi-threaded dispatcher
    for the targets.
    For Datadog, we have a separate subprocess that picks the metrics from the
    queue and ships them when we have sufficient data points.
    """
    args = parse_args()
    cfg_path = os.path.join(os.getcwd(), "latency.toml")
    if not os.path.exists(cfg_path):
        log.critical("Unable to read the config file from %s", cfg_path)
        sys.exit(1)
    with open(cfg_path, "rb") as f:
        cfg = tomllib.load(f)
    targets = opts.pop("targets")
    pub_q = multiprocessing.Queue()
    log_level = opts.pop("log_level") or args.log_level
    if hasattr(logging, log_level):
        logging.basicConfig(level=getattr(logging, log_level))
    signal.signal(signal.SIGTERM, _sigkill)
    dd_server = _start_proc(start_datadog, pub_q, **opts)
    poller = _start_proc(start_tcp_latency_pollers, pub_q, targets, **opts)
    tcp_server = _start_proc(start_tcp_server, pub_q, targets, **opts)
    udp_server = _start_proc(start_udp_server, pub_q, targets, **opts)
    owd_udp_ps = _start_proc(start_owd_udp_clients, pub_q, targets, **opts)
    owd_tcp_ps = _start_proc(start_owd_tcp_clients, pub_q, targets, **opts)
    while True:
        if not udp_server.is_alive():
            log.info("Looks like the UDP server got terminated for some reason")
            udp_server = _start_proc(start_udp_server, pub_q, targets, **opts)
        if not tcp_server.is_alive():
            log.info("Looks like the TCP server got terminated for some reason")
            tcp_server = _start_proc(start_tcp_server, pub_q, targets, **opts)
        if not poller.is_alive():
            poller = _start_proc(start_tcp_latency_pollers, pub_q, targets, **opts)
        if not owd_udp_ps.is_alive():
            owd_udp_ps = _start_proc(start_owd_udp_clients, pub_q, targets, **opts)
            log.info("Looks like the UDP OWD process for the clients got terminated")
        if not owd_tcp_ps.is_alive():
            owd_tcp_ps = _start_proc(start_owd_tcp_clients, pub_q, targets, **opts)
            log.info("Looks like the TCP OWD process for the clients got terminated")
        if not dd_server.is_alive():
            log.info("Looks like the Datadog process got terminated for some reason")
            dd_server = _start_proc(start_datadog, pub_q, **opts)
        time.sleep(0.1)
