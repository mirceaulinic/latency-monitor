# -*- coding: utf-8 -*-
"""
Latency Monitoring Core
=======================

This is where fun happens. This is a classless implementation of several
independent functions that are invoked when spawning the client and severs for
the UDP and TCP connections. They expect a publishing queue object being passed
on, where they add the resulting metrics. A separate worker picks up the
metrics from the queue and publishes them over the channel of choice.
"""
import logging
import os
import select
import signal
import socket
import sys
import threading
import time
import ast

import tcp_latency

log = logging.getLogger(__name__)


MAX_SEQ = 100
MAX_CONN = 40
MAX_SIZE = 1470

MSG_FMT = "{seq}|{source}|{timestamp}|{tags}|"


def _next_seq(seq):
    """
    Returns the next sequence number.
    """
    if seq >= MAX_SEQ or seq < 0:
        return 0
    return seq + 1


def _build_tags(source, target):
    """
    Return a list of tags given the source and the target.
    """
    return [
        f"source:{source}",
        "target:{}".format(target.get("label", target["host"])),
    ] + target.get("tags", [])


def serve_owd_udp(pub_q, srv, ts, data, addr, seq_dict, **opts):
    """
    Receives the packet from the OWD client, extracts the timestamp and sends
    the metric to the Datadog queue.
    """
    log.debug(
        "[UDP OWD server] Received connection from %s, you're welcome my friend", addr
    )
    if not data:
        return
    try:
        seq, src, send_ts, rtags, padding = str(data, "utf-8").split("|")
        log.debug(
            "[UDP OWD client] Received timestamp %s (SEQ: %d) from source: %s, with tags: %s",
            send_ts,
            seq,
            src,
            rtags,
        )
        owd_ns = ts - int(send_ts)
        seq = int(seq)
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
        bytes(
            MSG_FMT.format(seq=seq, source=opts["name"], timestamp=ts, tags=rtags)
            + padding,
            "utf-8",
        ),
        addr,
    )
    tags = [f"source:{src}", f"target:{opts['name']}"] + (
        ast.literal_eval(rtags) if rtags else []
    )
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

    addr = opts.get("address", "0.0.0.0")
    srv = socket.socket(
        socket.AF_INET6 if ":" in addr else socket.AF_INET, socket.SOCK_DGRAM
    )
    srv.bind((addr, opts["udp_port"]))

    client_seqs = {}

    while True:
        data, addr = srv.recvfrom(opts.get("max_size", MAX_SIZE))
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
        for tid, tgt in enumerate(opts["targets"]):
            ttype = tgt.get("type")
            if ttype and ttype != "udp":
                continue
            if not tid in threads:
                log.info("Starting thread for UDP OWD target %s", tgt)
                t = threading.Thread(
                    target=owd_udp_client,
                    args=(
                        pub_q,
                        tgt,
                    ),
                    kwargs=opts,
                )
                t.start()
                threads[tid] = t
            else:
                # Thread exists but might not longer be active.
                t = threads[tid]
                if not t.is_alive():
                    log.info(
                        "Thread for UDP OWD target %s got interrupted, respawning",
                        tgt,
                    )
                    threads.pop(tid)
        time.sleep(0.1)


def owd_udp_client(pub_q, target, **opts):
    """
    Connects to a server and sends one single message containing the sequence
    number, the timestamp, the source DC as well as the ISP name.
    """
    size = target.get("size", opts.get("size"))
    port = target.get("udp_port", opts["udp_port"])
    tout = target.get("timeout", opts.get("timeout", 1.0))
    ival = target.get("interval", opts.get("interval", 1.0))
    tags = _build_tags(opts["name"], target)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as skt:
            seq = 0
            while True:
                ts = time.time_ns()
                log.debug("[UDP OWD client] sending timestamp %s to %s", ts, target)
                msg = bytes(
                    MSG_FMT.format(
                        seq=seq,
                        source=opts["name"],
                        timestamp=ts,
                        tags=target.get("tags", []),
                    ),
                    "utf-8",
                )
                if size and len(msg) < size:
                    msg += b"0" * (size - len(msg))
                skt.sendto(
                    msg,
                    (target["host"], port),
                )
                incoming = select.select([skt], [], [], tout)
                try:
                    data, srv = incoming[0][0].recvfrom(opts.get("max_size", MAX_SIZE))
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
                    srv_seq, srv_srv, owd_ns, srv_tags, padding = str(
                        data, "utf-8"
                    ).split("|")
                    log.debug(
                        "[UDP OWD client] received OWD timestamp %s (SEQ: %d) from %s",
                        owd_ns,
                        srv_seq,
                        srv,
                    )
                    srv_seq = int(srv_seq)
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
                pause = ival - (time.time_ns() - ts) / 1e9
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
        time.sleep(0.01)
        owd_udp_client(pub_q, target, **opts)


def serve_owd_tcp(pub_q, conn, addr, **opts):
    """
    Receives the packet from the OWD client, extracts the timestamp and sends
    the metric to Datadog.
    """
    log.debug(
        "[TCP OWD server] Received connection from %s, you're welcome my friend", addr
    )
    prev_seq = -1
    while True:
        try:
            data = conn.recv(opts.get("max_size", MAX_SIZE))
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
            seq, src, send_ts, rtags, padding = str(data, "utf-8").split("|")
            log.debug(
                "[TCP OWD server] Received timestamp %s (SEQ: %d) from source %s, with tags %s",
                send_ts,
                seq,
                src,
                rtags,
            )
            owd_ns = ts - int(send_ts)
            seq = int(seq)
        except ValueError:
            log.error(
                "[TCP OWD server] Unable to unpack the OWD data received from source %s, with tags %s: %s",
                src,
                tags,
                data,
            )
            continue
        conn.sendall(
            bytes(
                MSG_FMT.format(seq=seq, timestamp=ts, source=opts["name"], tags=rtags)
                + padding,
                "utf-8",
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
        tags = [f"source:{src}", f"target:{opts['name']}"] + (
            ast.literal_eval(rtags) if rtags else []
        )
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

    addr = opts.get("address", "0.0.0.0")
    srv = socket.socket(
        socket.AF_INET6 if ":" in addr else socket.AF_INET, socket.SOCK_STREAM
    )
    srv.bind((addr, opts["tcp_port"]))
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
        for tid, tgt in enumerate(opts["targets"]):
            ttype = tgt.get("type")
            if ttype and ttype != "tcp":
                continue
            if not tid in threads:
                log.info("[TCP OWD client] Starting thread for OWD target %s", tgt)
                t = threading.Thread(
                    target=owd_tcp_client,
                    args=(
                        pub_q,
                        tgt,
                    ),
                    kwargs=opts,
                )
                t.start()
                threads[tid] = t
            else:
                # Thread exists but might not longer be active.
                t = threads[tid]
                if not t.is_alive():
                    log.info(
                        "[TCP OWD client] Thread for target %s got interrupted, respawning",
                        tgt,
                    )
                    threads.pop(tid)
        time.sleep(0.01)


def owd_tcp_client(pub_q, target, **opts):
    """
    Connects to a server and sends one single message containing the timestamp.
    """
    # TODO: use the timeout?
    # tout = target.get("timeout", opts.get("timeout", 1.0))
    size = target.get("size", opts.get("size"))
    port = target.get("tcp_port", opts["tcp_port"])
    ival = target.get("interval", opts.get("interval", 1.0))
    tags = _build_tags(opts["name"], target)
    try:
        with socket.socket(
            socket.AF_INET6 if ":" in target["host"] else socket.AF_INET,
            socket.SOCK_STREAM,
        ) as skt:
            try:
                skt.connect((target["host"], port))
            except Exception as err:
                # log and fail loudly, forcing a process restart
                log.error(
                    "[TCP OWD client] Unable to connect to %s:%d",
                    target["host"],
                    port,
                    exc_info=True,
                )
                raise err
            seq = 0
            while True:
                ts = time.time_ns()
                msg = bytes(
                    MSG_FMT.format(
                        seq=seq, timestamp=ts, source=opts["name"], tags=target.get("tags", [])
                    ),
                    "utf-8",
                )
                if size and len(msg) < size:
                    msg += b"0" * (size - len(msg))
                skt.sendall(msg)
                data = skt.recv(opts.get("max_size", MAX_SIZE))
                rtt_ns = time.time_ns() - ts
                rtt_ms = rtt_ns / 1e6
                try:
                    srv_seq, srv_src, srv_ts, rtags, padding = str(data, "utf-8").split(
                        "|"
                    )
                    log.debug(
                        "[TCP OWD client] received RTT timestamp %s (SEQ: %d) from %s with tags: %",
                        srv_ts,
                        srv_seq,
                        srv_src,
                        rtags,
                    )
                    srv_seq = int(srv_seq)
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
                pause = ival - (time.time_ns() - ts) / 1e9
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
        time.sleep(0.01)
        owd_tcp_client(pub_q, target, **opts)


def start_tcp_latency_pollers(pub_q, **opts):
    """
    Dispatch pollers into their own threads.
    """
    log.debug("Starting the poller subprocess")
    threads = {}
    while True:
        for tid, tgt in enumerate(opts["targets"]):
            ttype = tgt.get("type")
            if ttype and ttype != "tcp":
                continue
            if tid not in threads:
                t = threading.Thread(
                    target=tcp_latency_poll,
                    args=(
                        pub_q,
                        tgt,
                    ),
                    kwargs=opts,
                )
                t.start()
                threads[tid] = t
            else:
                # Thread exists but might not longer be active.
                t = threads[tid]
                if not t.is_alive():
                    log.info(
                        "Thread for TCP latency %s got interrupted, respawning",
                        tgt,
                    )
                    threads.pop(tid)
        time.sleep(0.01)


def tcp_latency_poll(pub_q, target, **opts):
    """
    Execute the TCP latency runs against the given ip and port, and send the
    metrics to the publisher worker.
    """
    port = target.get("tcp_port", opts["tcp_port"])
    tout = target.get("timeout", opts.get("timeout", 1.0))
    ival = target.get("interval", opts.get("interval", 1.0))
    log.debug(
        "Polling target %s, timeout set at",
        target,
        tout,
    )
    tags = _build_tags(opts["name"], target)
    while True:
        probe_time = time.time_ns()
        res = tcp_latency.latency_point(
            host=target["host"],
            port=port,
            timeout=tout,
        )
        if not res:
            log.info(
                "[TCP Latency] Polling %s returned no results, the destination is likely unreachable or timed out.",
                target,
            )
            res = 0
        metric = {
            "metric": "tcp.wan.latency",
            "points": [(probe_time, res * 1e6)],
            "tags": tags,
        }
        log.debug("Adding TCP latency metric to the publisher queue: %s", metric)
        pub_q.put(metric)
        pause = ival - (time.time_ns() - probe_time) / 1e9
        if pause > 0:
            time.sleep(pause)
