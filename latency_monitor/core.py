# -*- coding: utf-8 -*-
"""
This is a script meant to be running as a daemon, executing "ping"-like requests
to a target IP and port, and exports the data as Datadog metrics.

This program assumes that it can also be used as a target, in order to be polled
by other daemons like this one, deployed elsewhere.

There are three different metrics produced by running this daemon:

    - tcp.wan.latency, based on the measurements from the tcp-latency library
    - tcp.wan.owd and tcp.wan.rtt produced by a basic client-server setup that
      sends timestamps back and forth in order to measure the One Way Delay
      (OWD) and Round Trip Time (RTT) between the source and its targets.
    - udp.wan.owd and udp.wan.rtt with similar meaning and behaviour, except
      that the packets are more likely to get lost in case of poor connectivity
      between the source and destination(s).

This requires a .ini configuration file, named latency.ini located into the same
directory where this program is executed from. This file has the following
structure (example):

[config]
dc = LD
port = 8001
runs = 10
timeout = 1.5
interval = 0.5
dd_api_key = <Datadog API key>

[targets]
TY = 10.61.6.81
BD = 10.21.6.81
NY = 10.31.6.81

The targets are, of course, necessary, otherwise this program won't poll
anything. Similarly, the ``dc`` under the ``config`` section is required in
order to identify the source and apply it as a label to the metrics.
The ``dd_api_key`` is recommended when running on Windows, as it seems
tremendously difficult to set environment variables (or anything whatsoever).

This program has the following dependencies:

    - tcp-latency
    - datadog-api-client
"""
import logging
import os
import select
import signal
import socket
import sys
import threading
import time

import tcp_latency

log = logging.getLogger(__name__)


MAX_SEQ = 100
MAX_CONN = 40

MSG_FMT = "{seq}|{source}|{timestamp}|{tags}"


def _next_seq(seq):
    """
    Returns the next sequence number.
    """
    if seq >= MAX_SEQ or seq < 0:
        return 0
    return seq + 1


def _build_tags(source, target, target_cfg):
    return [
        f"source:{source}",
        "target:{}".format(target_cfg.get("label", target)),
    ] + target_cfg.get("tags", [])


def serve_owd_udp(pub_q, srv, ts, data, addr, seq_dict, **opts):
    """
    Receives the packet from the OWD client, extracts the timestamp and sends
    the metric to the Datadog queue.
    """
    log.info(
        "[UDP OWD server] Received connection from %s, you're welcome my friend", addr
    )
    if not data:
        return
    try:
        seq, src, send_ts, rtags = str(data, "utf-8").split("|")
        log.debug(
            "[UDP OWD client] Received timestamp %s (SEQ: %d) from source: %s, with tags: %s",
            send_ts,
            seq,
            src,
            rtags,
        )
        owd_ns = ts - send_ts
    except ValueError:
        log.error(
            "[UDP OWD client] Unable to unpack the timestamp from source: %s, with tags %s: %s",
            src,
            rtags,
            data,
        )
        owd_ns = 0
        seq = MAX_SEQ + 1
    log.debug("[UDP OWD client] Sending timestamp %s to client %s", ts, addr)
    srv.sendto(
        MSG_FMT.format(seq=seq, source=opts["name"], timestamp=ts, tags=rtags), addr
    )
    tags = [f"source:{src}", f"target:{opts['name']}"] + rtags
    prev_seq = seq_dict.get(addr, -1)
    expected_seq = _next_seq(prev_seq) if prev_seq > 0 else -1
    if owd_ns < 0 or (expected_seq > 0 and seq != expected_seq):
        owd_ns = 0
    owd_ms = owd_ns / 1e6
    metric = {
        "metric": "udp.wan.owd",
        "points": [(time.time_ns(), owd_ms)],
        "tags": tags,
    }
    log.debug("Adding UDP OWD metric to the Datadog queue: %s", metric)
    pub_q.put(metric)
    seq_dict[addr] = seq


def start_udp_server(pub_q, **opts):
    """
    Starts a server that listens to UDP connections on the port provided.
    """
    log.debug("Starting the UDP server, bring it on")

    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("0.0.0.0", opts["udp_port"]))

    client_seqs = {}

    while True:
        data, addr = srv.recvfrom(128)
        ts = time.time_ns()
        t = threading.Thread(
            target=serve_owd_udp,
            args=(
                pub_q,
                srv,
                ts,
                data,
                addr,
                client_seqs,
            ),
            kwargs=opts,
        )
        t.start()


def start_owd_udp_clients(pub_q, **opts):
    """
    Dispatch OWD clients into their own threads.
    This function sports a keep-alive loop, as the threads might die when the
    TCP connection is dropped.
    """
    threads = {}
    while True:
        for target, target_cfg in opts["targets"].items():
            ttype = target_cfg.get("type")
            if ttype and ttype != "udp":
                continue
            if not target in threads:
                log.info("Starting thread for UDP OWD target %s", target)
                t = threading.Thread(
                    target=owd_udp_client,
                    args=(
                        pub_q,
                        target,
                        target_cfg,
                    ),
                    kwargs=opts,
                )
                t.start()
                threads[target] = t
            else:
                # Thread exists but might not longer be active.
                t = threads[target]
                if not t.is_alive():
                    log.info(
                        "Thread for UDP OWD target %s got interrupted, respawning",
                        target,
                    )
                    threads.pop(target)
        time.sleep(0.1)


def owd_udp_client(pub_q, target, target_cfg, **opts):
    """
    Connects to a server and sends one single message containing the sequence
    number, the timestamp, the source DC as well as the ISP name.
    """
    tags = _build_tags(opts["name"], target, target_cfg)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as skt:
            seq = 0
            while True:
                ts = time.time_ns()
                log.debug("[UDP OWD client] sending timestamp %s to %s", ts, target)
                skt.sendto(
                    bytes(
                        MSG_FMT.format(
                            seq=seq,
                            source=opts["name"],
                            timestamp=ts,
                            tags=target_cfg.get("tags", []),
                        ),
                        "utf-8",
                    ),
                    (target, opts["udp_port"]),
                )
                incoming = select.select([skt], [], [], opts["timeout"])
                try:
                    data, srv = incoming[0][0].recvfrom(128)
                except IndexError as ierr:
                    log.debug(
                        "[UDP OWD client] didn't receive a response from the UDP server %s",
                        target,
                    )
                    data = b""
                    srv = None
                rtt_ns = time.time_ns() - ts
                rtt_ms = rtt_ns / 1e6
                try:
                    srv_seq, srv_srv, owd_ns, srv_tags = str(data, "utf-8").split("|")
                    log.debug(
                        "[UDP OWD client] received OWD timestamp %s (SEQ: %d) from %s",
                        owd_ns,
                        srv_seq,
                        srv,
                    )
                except ValueError:
                    log.error(
                        "[UDP OWD client] Unable to unpack the computed UDP OWD from the server %s. Received: %s",
                        target,
                        data,
                    )
                    owd_ns = 0
                    srv_seq = -1
                if seq != srv_seq:
                    log.info(
                        "[UDP OWD client] Ignoring timestamp as SEQ doesn't match: expected %d, got %d",
                        seq,
                        srv_seq,
                    )
                    rtt_ms = 0
                metric = {
                    "metric": "udp.wan.rtt",
                    "points": [(time.time_ns(), rtt_ms)],
                    "tags": tags,
                }
                log.debug("[UDP OWD client] Adding metric to the queue: %s", metric)
                pub_q.put(metric)
                seq = _next_seq(seq)
                pause = opts["interval"] - (time.time_ns() - ts) / 1e9
                if pause > 0:
                    log.debug(
                        "[UDP OWD client] Waiting %s seconds before sending the next probe to %s",
                        pause,
                        target,
                    )
                    time.sleep(pause)
    except (BrokenPipeError, ConnectionRefusedError, ConnectionResetError):
        log.info(
            "[UDP OWD client] Can't connect or connection lost with %s, will try again shortly...",
            target,
            exc_info=True,
        )
        time.sleep(0.1)
        owd_udp_client(pub_q, target, target_cfg, **opts)


def serve_owd_tcp(pub_q, conn, addr, **opts):
    """
    Receives the packet from the OWD client, extracts the timestamp and sends
    the metric to Datadog.
    """
    log.info(
        "[TCP OWD server] Received connection from %s, you're welcome my friend", addr
    )
    prev_seq = -1
    while True:
        try:
            data = conn.recv(128)
            ts = time.time_ns()
        except OSError:
            log.error(
                "[TCP OWD server] Looks like connection with %s was lost. "
                "Exiting gracefully, the client should try to reconnect.",
                addr,
            )
            return
        if not data:
            break
        try:
            seq, src, send_ts, rtags = str(data, "utf-8").split("|")
            log.debug(
                "[TCP OWD server] Received timestamp %s (SEQ: %d) from source %s, with tags %s",
                send_ts,
                seq,
                src,
                tags,
            )
            owd_ns = ts - send_ts
        except ValueError:
            log.error(
                "[TCP OWD server] Unable to unpack the OWD data received from source %s, with tags %s: %s",
                srv,
                tags,
                data,
            )
            continue
        conn.sendall(
            bytes(
                MSG_FMT.format(seq=seq, timestamp=ts, source=opts["name"], tags=rtags)
            )
        )
        expected_seq = _next_seq(prev_seq)
        if seq != expected_seq:
            log.warning(
                "[TCP OWD server] Ignoring OWD packet, it seems out of sequence (expected: %d, got: %d)",
                expected_seq,
                seq,
            )
            owd_ns = 0
        if owd_ns < 0:
            owd_ns = 0
        owd_ms = owd_ns / 1e6
        tags = [f"source:{src}", f"target:{opts['name']}"] + rtags
        metric = {
            "metric": "tcp.wan.owd",
            "points": [(time.time_ns(), owd_ms)],
            "tags": tags,
        }
        log.debug("[TCP OWD server] Adding metric to the queue %s", metric)
        pub_q.put(metric)
        prev_seq = seq


def start_tcp_server(pub_q, **opts):
    """
    Starts a server that listens to TCP connections on the port provided.
    """
    log.debug("Starting the TCP server, bring it on")

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("0.0.0.0", opts["tcp_port"]))
    srv.listen(MAX_CONN)

    while True:
        conn, addr = srv.accept()
        log.debug("[TCP server] Received connection from: %s", addr)
        t = threading.Thread(
            target=serve_owd_tcp, args=(pub_q, conn, addr), kwargs=opts
        )
        t.start()


def start_owd_tcp_clients(pub_q, **opts):
    """
    Dispatch OWD TCP clients into their own threads.
    This function sports a keep-alive loop, as the threads might die when the
    TCP connection is dropped.
    """
    threads = {}
    while True:
        for target, target_cfg in opts["targets"].items():
            ttype = target_cfg.get("type")
            if ttype and ttype != "tcp":
                continue
            if not target in threads:
                log.info("[TCP OWD client] Starting thread for OWD target %s", target)
                t = threading.Thread(
                    target=owd_tcp_client,
                    args=(
                        pub_q,
                        target,
                        target_cfg,
                    ),
                    kwargs=opts,
                )
                t.start()
                threads[target] = t
            else:
                # Thread exists but might not longer be active.
                t = threads[target]
                if not t.is_alive():
                    log.info(
                        "[TCP OWD client] Thread for target %s got interrupted, respawning",
                        target,
                    )
                    threads.pop(target)
        time.sleep(0.1)


def owd_tcp_client(pub_q, target, target_cfg, **opts):
    """
    Connects to a server and sends one single message containing the timestamp.
    """
    tags = _build_tags(opts["name"], target, target_cfg)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as skt:
            try:
                skt.connect((target, opts["tcp_port"]))
            except Exception as err:
                # log and fail loudly, forcing a process restart
                log.error(
                    "[TCP OWD client] Unable to connect to %s:%d",
                    target,
                    opts["tcp_port"],
                    exc_info=True,
                )
                raise err
            seq = 0
            while True:
                ts = time.time_ns()
                skt.sendall(
                    bytes(
                        MSG_FMT.format(
                            seq=seq, timestamp=ts, source=opts["name"], tags=tags
                        ),
                        "utf-8",
                    )
                )
                data = skt.recv(128)
                rtt_ns = time.time_ns() - ts
                rtt_ms = rtt_ns / 1e6
                try:
                    srv_seq, srv_src, srv_ts, rtags = str(data, "utf-8").split("|")
                    log.debug(
                        "[TCP OWD client] received RTT timestamp %s (SEQ: %d) from %s with tags: %",
                        srv_ts,
                        srv_seq,
                        srv_src,
                        rtags,
                    )
                except ValueError:
                    srv_seq = -1
                    log.error(
                        "[TCP OWD client] Unable to unpack the computed OWD from the server"
                    )
                if srv_seq != seq:
                    rtt_ms = 0
                    log.warning(
                        "[TCP OWD client] Ignoring RTT packet, the seq doesn't match (%d vs %d)",
                        seq,
                        srv_seq,
                    )
                rtt_metric = {
                    "metric": "tcp.wan.rtt",
                    "points": [(time.time_ns(), rtt_ms)],
                    "tags": tags,
                }
                log.debug(
                    "[TCP OWD client] Adding RTT metric to the Datadog queue: %s",
                    rtt_metric,
                )
                pub_q.put(rtt_metric)
                seq = _next_seq(seq)
                pause = opts["interval"] - (time.time_ns() - ts) / 1e9
                if pause > 0:
                    log.debug(
                        "[TCP OWD client] Waiting %s seconds before sending the next probe",
                        pause,
                    )
                    time.sleep(pause)
    except (BrokenPipeError, ConnectionRefusedError, ConnectionResetError):
        log.info(
            "[TCP OWD client] Can't connect or connection lost with %s, will try again shortly...",
            target,
            exc_info=True,
        )
        time.sleep(0.1)
        owd_tcp_client(pub_q, target, target_cfg, **opts)


def start_tcp_latency_pollers(pub_q, **opts):
    """
    Dispatch pollers into their own threads.
    """
    log.debug("Starting the poller subprocess")
    timeout = opts.get("timeout", 1.0)
    while True:
        threads = []
        for target, target_cfg in opts["targets"].items():
            ttype = target_cfg.get("type")
            if ttype and ttype != "tcp":
                continue
            t = threading.Thread(
                target=tcp_latency_poll,
                args=(
                    pub_q,
                    target,
                    target_cfg,
                ),
                kwargs=opts,
            )
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        time.sleep(0.1)


def tcp_latency_poll(pub_q, target, target_cfg, **opts):
    """
    Execute the TCP latency runs against the given ip and port, and send the
    metrics to the publisher worker.
    """
    log.debug(
        "Polling target %s (port %d), running %d times with a %f gap",
        target,
        opts["tcp_port"],
        opts["runs"],
        opts["timeout"],
    )
    tags = _build_tags(opts["name"], target, target_cfg)
    metric_points = []
    for _ in range(opts["runs"]):
        # tcp_latency's measure_latency function doesn't return the results for
        # the failed probes, e.g., if a batch of 10 runs has 2 failures, then
        # results is a list of 8 results.
        # Because of that, instead of using their runs, we execute our batch
        # and record the results, ensuring we have record 0 for failed probes
        # at the exact timestamp when it happened for accurate metrics.
        probe_time = time.time_ns()
        results = tcp_latency.measure_latency(
            host=target, runs=1, timeout=opts["timeout"]
        )
        if not results:
            log.error(
                "Polling %s (port %d) returned no results, the destination is likely unreachable",
                target,
                opts["tcp_port"],
            )
            results = [0]
        metric_points.append((probe_time, results[0]))

    metric = {
        "metric": "tcp.wan.latency",
        "points": metric_points,
        "tags": tags,
    }
    log.debug("Adding TCP latency metric to the publisher queue: %s", metric)
    pub_q.put(metric)
