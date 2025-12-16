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
import struct
import sys
import threading
import time

import tcp_latency

log = logging.getLogger(__name__)


MAX_SEQ = 100
MAX_CONN = 40


def _next_seq(seq):
    """
    Returns the next sequence number.
    """
    if seq >= MAX_SEQ or seq < 0:
        return 0
    return seq + 1


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
        seq, send_ts = struct.unpack("!2Q", data[:16])
        source_dc = data[16:21].decode("utf-8")
        isp = data[21:].decode("utf-8")
        log.debug(
            "[UDP OWD client] Received timestamp %s (SEQ: %d) from source DC: %s, over ISP %s",
            send_ts,
            seq,
            source_dc,
            isp,
        )
        owd_ns = ts - send_ts
    except struct.error:
        log.error(
            "[UDP OWD client] Unable to unpack the timestamp from source DC: %s, over ISP %s: %s",
            source_dc,
            isp,
            data,
        )
        owd_ns = 0
        seq = MAX_SEQ + 1
    log.debug("[UDP OWD client] Sending timestamp %s to client %s", ts, addr)
    srv.sendto(struct.pack("!2Q", seq, ts), addr)
    dc = opts.get("dc")
    tags = [f"source:{source_dc}", f"target:{dc}"]
    if isp:
        tags.append(f"isp:{isp}")
    prev_seq = seq_dict.get(addr, -1)
    expected_seq = _next_seq(prev_seq) if prev_seq > 0 else -1
    if owd_ns < 0 or (expected_seq > 0 and seq != expected_seq):
        owd_ns = 0
    owd_ms = owd_ns / 1e6
    metric = {
        "metric": "udp.wan.owd",
        "points": [(int(time.time()), owd_ms)],
        "tags": tags,
    }
    log.debug("Adding UDP OWD metric to the Datadog queue: %s", metric)
    pub_q.put(metric)
    seq_dict[addr] = seq


def start_udp_server(pub_q, targets, **opts):
    """
    Starts a server that listens to UDP connections on the port provided.
    """
    log.debug("Starting the UDP server, bring it on")

    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("0.0.0.0", opts["port"] + 1))

    client_seqs = {}

    while True:
        data, addr = srv.recvfrom(28)
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


def start_owd_udp_clients(pub_q, targets, **opts):
    """
    Dispatch OWD clients into their own threads.
    This function sports a keep-alive loop, as the threads might die when the
    TCP connection is dropped.
    """
    threads = {}
    while True:
        for target in targets:
            if not target in threads:
                log.info("Starting thread for UDP OWD target %s", target)
                t = threading.Thread(
                    target=owd_udp_client,
                    args=(
                        pub_q,
                        target,
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


def owd_udp_client(pub_q, target, **opts):
    """
    Connects to a server and sends one single message containing the sequence
    number, the timestamp, the source DC as well as the ISP name.
    """
    dc = opts.get("dc")
    tags = [f"source:{dc}"]
    if "-" in target[0]:
        tgt, isp = target[0].split("-")
    else:
        isp = ""
        tgt = target[0]
    tags.append(f"target:{tgt}")
    if isp:
        tags.append(f"isp:{isp}")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as skt:
            seq = 0
            while True:
                ts = time.time_ns()
                log.debug("[UDP OWD client] sending timestamp %s to %s", ts, target)
                skt.sendto(
                    struct.pack("!2Q", seq, ts) + bytes(dc + isp, "utf-8"),
                    (target[1], opts["port"] + 1),
                )
                incoming = select.select([skt], [], [], opts["timeout"])
                try:
                    data, srv = incoming[0][0].recvfrom(16)
                    # the OWD is exactly 16 bytes as a struct.
                    # For RTT we use difference between the timestamp when we
                    # received the packet and the timstamp when we sent it.
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
                    srv_seq, owd_ns = struct.unpack("!2Q", data)
                    log.debug(
                        "[UDP OWD client] received OWD timestamp %s (SEQ: %d) from %s",
                        owd_ns,
                        srv_seq,
                        srv,
                    )
                except struct.error:
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
                    "points": [(int(time.time()), rtt_ms)],
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
        owd_udp_client(pub_q, target, **opts)


def serve_owd_tcp(pub_q, conn, addr, **opts):
    """
    Receives the packet from the OWD client, extracts the timestamp and sends
    the metric to Datadog.
    """
    log.info(
        "[TCP OWD server] Received connection from %s, you're welcome my friend", addr
    )
    dc = opts.get("dc")
    prev_seq = -1
    while True:
        try:
            data = conn.recv(28)
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
            seq, send_ts = struct.unpack("!2Q", data[:16])
            source_dc = data[16:21].decode("utf-8")
            isp = data[21:].decode("utf-8")
            log.debug(
                "[TCP OWD server] Received timestamp %s (SEQ: %d) from source DC: %s, over ISP %s",
                send_ts,
                seq,
                source_dc,
                isp,
            )
            owd_ns = ts - send_ts
        except struct.error:
            log.error(
                "[TCP OWD server] Unable to unpack the OWD data received from source DC: %s, over ISP %s: %s",
                source_dc,
                isp,
                data,
            )
            continue
        conn.sendall(struct.pack("!2Q", seq, ts))
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
        tags = [f"source:{source_dc}", f"target:{dc}"]
        if isp:
            tags.append(f"isp:{isp}")
        metric = {
            "metric": "tcp.wan.owd",
            "points": [(int(time.time()), owd_ms)],
            "tags": tags,
        }
        log.debug("[TCP OWD server] Adding metric to the queue %s", metric)
        pub_q.put(metric)
        prev_seq = seq


def start_tcp_server(pub_q, targets, **opts):
    """
    Starts a server that listens to TCP connections on the port provided.
    """
    log.debug("Starting the TCP server, bring it on")

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("0.0.0.0", opts["port"]))
    srv.listen(MAX_CONN)

    while True:
        conn, addr = srv.accept()
        log.debug("[TCP server] Received connection from: %s", addr)
        t = threading.Thread(
            target=serve_owd_tcp, args=(pub_q, conn, addr), kwargs=opts
        )
        t.start()


def start_owd_tcp_clients(pub_q, targets, **opts):
    """
    Dispatch OWD TCP clients into their own threads.
    This function sports a keep-alive loop, as the threads might die when the
    TCP connection is dropped.
    """
    threads = {}
    while True:
        for target in targets:
            if not target in threads:
                log.info("[TCP OWD client] Starting thread for OWD target %s", target)
                t = threading.Thread(
                    target=owd_tcp_client,
                    args=(
                        pub_q,
                        target,
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


def owd_tcp_client(pub_q, target, **opts):
    """
    Connects to a server and sends one single message containing the timestamp.
    """
    dc = opts.get("dc")
    tags = [f"source:{dc}"]
    if "-" in target[0]:
        tgt, isp = target[0].split("-")
        tags.extend([f"target:{tgt}", f"isp:{isp}"])
    else:
        isp = ""
        tgt = target[0]
        tags.append(f"target:{tgt}")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as skt:
            try:
                skt.connect((target[1], opts["port"]))
            except Exception as err:
                # log and fail loudly, forcing a process restart
                log.error(
                    "[TCP OWD client] Unable to connect to %s:%d",
                    target,
                    opts["port"],
                    exc_info=True,
                )
                raise err
            seq = 0
            while True:
                ts = time.time_ns()
                skt.sendall(struct.pack("!2Q", seq, ts) + bytes(dc + isp, "utf-8"))
                data = skt.recv(16)  # the OWD is exactly 8 bytes as a struct.
                # For RTT we use difference between the timestamp when we
                # received the packet and the timstamp when we sent it, while
                # for OWD we simply take the value pong-ed back from the server.
                rtt_ns = time.time_ns() - ts
                rtt_ms = rtt_ns / 1e6
                try:
                    srv_seq, _ = struct.unpack("!2Q", data)
                    log.debug(
                        "[TCP OWD client] received RTT timestamp %s (SEQ: %d) from %s (ISP: %s)",
                        rtt_ns,
                        srv_seq,
                        tgt,
                        isp,
                    )
                except struct.error:
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
                    "points": [(int(time.time()), rtt_ms)],
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
        owd_tcp_client(pub_q, target, **opts)


def start_tcp_latency_pollers(pub_q, targets, **opts):
    """
    Dispatch pollers into their own threads.
    """
    log.debug("Starting the poller subprocess")
    timeout = opts.get("timeout", 1.0)
    while True:
        threads = []
        for target in targets:
            t = threading.Thread(
                target=tcp_latency_poll,
                args=(
                    pub_q,
                    target,
                ),
                kwargs=opts,
            )
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        time.sleep(0.1)


def tcp_latency_poll(pub_q, target, **opts):
    """
    Execute the TCP latency runs against the given ip and port, and ship the
    metrics to Datadog.
    target is a tuple of site name & IP.
    """
    log.debug(
        "Polling target %s (%s, %d), running %d times with a %f gap",
        target[0],
        target[1],
        opts["port"],
        opts["runs"],
        opts["timeout"],
    )
    dc = opts.pop("dc")
    runs = opts.pop("runs")
    tags = [f"source:{dc}", f"target:{target[0]}"]
    _ = opts.pop("dd_api_key", None)

    metric_points = []
    for _ in range(runs):
        # tcp_latency's measure_latency function doesn't return the results for
        # the failed probes, e.g., if a batch of 10 runs has 2 failures, then
        # results is a list of 8 results.
        # Because of that, instead of using their runs, we execute our batch
        # and record the results, ensuring we have record 0 for failed probes
        # at the exact timestamp when it happened for accurate metrics.
        probe_time = int(time.time())
        results = tcp_latency.measure_latency(host=target[1], runs=1, **opts)
        if not results:
            log.error(
                "Polling %s (%s, %d) returned no results, the destination is likely unreachable",
                target[0],
                target[1],
                opts["port"],
            )
            results = [0]
        metric_points.append((probe_time, results[0]))

    metric = {
        "metric": "tcp.wan.latency",
        "points": metric_points,
        "tags": tags,
    }
    log.debug("Adding TCP latency metric to the datadog queue: %s", metric)
    pub_q.put(metric)
