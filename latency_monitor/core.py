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
import ast
import logging
import select
import socket
import threading
import time

import latency_monitor.defaults as defaults

log = logging.getLogger(__name__)


def _next_seq(seq):
    """
    Returns the next sequence number.
    """
    if seq >= defaults.MAX_SEQ or seq < 0:
        return 0
    return seq + 1


def _max_size(opts):
    """
    Yields the maximum packet size based on the configuration options.
    If the max_size option is configured, that'll be the preferred value,
    otherwise it'll try to guess based on the configured size per target
    (although that's not always sufficient, as the other end may have a
    different configuration). If non of these are available, it'll default to
    the 1470 bytes.
    """
    max_size = (
        opts.get("max_size", 0)
        or (
            max([tgt.get("size", 0) for tgt in opts["targets"]])
            if opts.get("targets")
            else 0
        )
        or defaults.MAX_SIZE
    )
    log.debug("Setting receiving size to %d bytes", max_size)
    return max_size


def _build_tags(source, target):
    """
    Return a list of tags given the source and the target.
    """
    return [
        f"source:{source}",
        "target:{}".format(target.get("label", target["host"])),
    ] + target.get("tags", [])


def serve_owd_udp(metrics_q, srv, ts, data, addr, seq_dict, **opts):
    """
    Receives the packet from the OWD client, extracts the timestamp and sends
    the metric to the queue.
    """
    log.debug(
        "[UDP OWD server] Received connection from %s, you're welcome my friend", addr
    )
    if not data:
        return
    try:
        seq, src, send_ts, rtags, padding = str(data, "utf-8").split("|")
        owd_ns = ts - int(send_ts)
        seq = int(seq)
        log.debug(
            "[UDP OWD client] Received timestamp %s (SEQ: %d) from source: %s, with tags: %s",
            send_ts,
            seq,
            src,
            rtags,
        )
    except ValueError:
        log.error(
            "[UDP OWD client] Unable to unpack the timestamp from source: %s, with tags %s: %s",
            src,
            rtags,
            data,
        )
        owd_ns = 0
        seq = defaults.MAX_SEQ + 1
    log.debug("[UDP OWD client] Sending timestamp %s to client %s", ts, addr)
    srv.sendto(
        bytes(
            defaults.MSG_FMT.format(
                seq=seq, source=opts["name"], timestamp=ts, tags=rtags
            )
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
    metric = {
        "metric": "udp.wan.owd",
        "points": [(time.time_ns(), owd_ns)],
        "tags": tags,
    }
    log.debug("Adding UDP OWD metric to the metrics queue: %s", metric)
    metrics_q.put(metric)
    seq_dict[addr] = seq


def start_udp_server(metrics_q, **opts):
    """
    Starts a server that listens to UDP connections on the port provided.
    """
    log.debug("Starting the UDP server, bring it on")

    addr = opts.get("address", "0.0.0.0")
    srv = socket.socket(
        socket.AF_INET6 if ":" in addr else socket.AF_INET, socket.SOCK_DGRAM
    )
    srv.bind((addr, opts["udp_port"]))
    max_size = _max_size(opts)

    client_seqs = {}

    while True:
        data, addr = srv.recvfrom(max_size)
        ts = time.time_ns()
        t = threading.Thread(
            target=serve_owd_udp,
            args=(
                metrics_q,
                srv,
                ts,
                data,
                addr,
                client_seqs,
            ),
            kwargs=opts,
        )
        t.start()


def start_owd_udp_clients(metrics_q, **opts):
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
            if tid not in threads:
                log.info("Starting thread for UDP OWD target %s", tgt)
                t = threading.Thread(
                    target=owd_udp_client,
                    args=(
                        metrics_q,
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


def owd_udp_client(metrics_q, target, **opts):
    """
    Connects to a server and sends one single message containing the sequence
    number, the timestamp, the source label and the tags.
    """
    size = target.get("size", opts["max_size"])
    port = target.get("udp_port", opts["udp_port"])
    tout = target.get("timeout", opts["timeout"])
    ival = target.get("interval", opts["interval"])
    max_lost = target.get("max_lost", opts["max_lost"])
    rtt = target.get("rtt", opts["rtt"])
    tags = _build_tags(opts["name"], target)
    max_size = _max_size(opts)
    lost = 0
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as skt:
            seq = 0
            while True:
                ts = time.time_ns()
                log.debug("[UDP OWD client] sending timestamp %s to %s", ts, target)
                msg = bytes(
                    defaults.MSG_FMT.format(
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
                if rtt:
                    incoming = select.select([skt], [], [], tout)
                    try:
                        data, srv = incoming[0][0].recvfrom(max_size)
                    except IndexError:
                        log.debug(
                            "[UDP OWD client] didn't receive a response from the UDP server %s",
                            target,
                        )
                        data = b""
                        srv = None
                    rtt_ns = time.time_ns() - ts
                    try:
                        srv_seq, srv_srv, owd_ns, srv_tags, padding = str(
                            data, "utf-8"
                        ).split("|")
                        srv_seq = int(srv_seq)
                        log.debug(
                            "[UDP OWD client] received OWD timestamp %s (SEQ: %d) from %s",
                            owd_ns,
                            srv_seq,
                            srv,
                        )
                    except ValueError:
                        log.error(
                            "[UDP OWD client] Unable to unpack the computed UDP OWD "
                            "from the server %s. Received: %s",
                            target,
                            data,
                        )
                        owd_ns = 0
                        srv_seq = -1
                    if seq != srv_seq:
                        log.info(
                            "[UDP OWD client] Ignoring timestamp as SEQ doesn't "
                            "match: expected %d, got %d",
                            seq,
                            srv_seq,
                        )
                        rtt_ns = 0
                        lost += 1
                    else:
                        lost = 0
                    metric = {
                        "metric": "udp.wan.rtt",
                        "points": [(time.time_ns(), rtt_ns)],
                        "tags": tags,
                    }
                    log.debug(
                        "[UDP OWD client] Adding RTT metric to the queue: %s", metric
                    )
                    metrics_q.put(metric)
                seq = _next_seq(seq)
                pause = ival - (time.time_ns() - ts) / 1e6
                if pause > 0:
                    log.debug(
                        "[UDP OWD client] Waiting %s seconds before sending the next probe to %s",
                        pause,
                        target,
                    )
                    time.sleep(pause / 1e3)
                if lost >= max_lost:
                    raise ConnectionResetError(f"Too many packets out of sync ({lost})")
    except (BrokenPipeError, ConnectionRefusedError, ConnectionResetError):
        log.info(
            "[UDP OWD client] Can't connect or connection lost with %s, will try again shortly...",
            target,
            exc_info=True,
        )
        time.sleep(0.1)
        owd_udp_client(metrics_q, target, **opts)


def _read_tcp(skt, tout, max_size):
    """
    Read from the TCP socket, but timeout after a given amount of time, don't
    wait forever.
    """
    incoming = select.select([skt], [], [], tout)
    try:
        data = incoming[0][0].recv(max_size)
    except IndexError:
        return b""
    if data and data == b"0" * len(data):
        # too fast, socket not ready, read again
        return _read_tcp(skt, tout, max_size)
    return data


def serve_owd_tcp(metrics_q, conn, addr, **opts):
    """
    Receives the packet from the OWD client, extracts the timestamp and sends
    the metric to the queue.
    """
    log.debug(
        "[TCP OWD server] Received connection from %s, you're welcome my friend", addr
    )
    prev_seq = -1
    max_size = _max_size(opts)
    while True:
        try:
            data = _read_tcp(conn, opts["timeout"], max_size)
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
            owd_ns = ts - int(send_ts)
            seq = int(seq)
            log.debug(
                "[TCP OWD server] Received timestamp %s (SEQ: %d) from source %s, with tags %s",
                send_ts,
                seq,
                src,
                rtags,
            )
        except ValueError:
            log.error(
                "[TCP OWD server] Unable to unpack the OWD data received from "
                "source %s, with tags %s: %s",
                src,
                rtags,
                data,
            )
            continue
        conn.sendall(
            bytes(
                defaults.MSG_FMT.format(
                    seq=seq, timestamp=ts, source=opts["name"], tags=rtags
                )
                + padding,
                "utf-8",
            )
        )
        expected_seq = _next_seq(prev_seq)
        if seq != expected_seq:
            log.warning(
                "[TCP OWD server] Ignoring OWD packet, it seems out of sequence "
                "(expected: %d, got: %d)",
                expected_seq,
                seq,
            )
            owd_ns = 0
        if owd_ns < 0:
            owd_ns = 0
        tags = [f"source:{src}", f"target:{opts['name']}"] + (
            ast.literal_eval(rtags) if rtags else []
        )
        metric = {
            "metric": "tcp.wan.owd",
            "points": [(time.time_ns(), owd_ns)],
            "tags": tags,
        }
        log.debug("[TCP OWD server] Adding metric to the queue %s", metric)
        metrics_q.put(metric)
        prev_seq = seq


def start_tcp_server(metrics_q, **opts):
    """
    Starts a server that listens to TCP connections on the port provided.
    """
    log.debug("Starting the TCP server, bring it on")

    addr = opts.get("address", "0.0.0.0")
    srv = socket.socket(
        socket.AF_INET6 if ":" in addr else socket.AF_INET, socket.SOCK_STREAM
    )
    srv.bind((addr, opts["tcp_port"]))
    srv.listen(defaults.MAX_CONN)

    while True:
        conn, addr = srv.accept()
        log.debug("[TCP server] Received connection from: %s", addr)
        t = threading.Thread(
            target=serve_owd_tcp, args=(metrics_q, conn, addr), kwargs=opts
        )
        t.start()


def start_owd_tcp_clients(metrics_q, **opts):
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
            if tid not in threads:
                log.info("[TCP OWD client] Starting thread for OWD target %s", tgt)
                t = threading.Thread(
                    target=owd_tcp_client,
                    args=(
                        metrics_q,
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


def owd_tcp_client(metrics_q, target, **opts):
    """
    Connects to a server and sends one single message containing the timestamp.
    """
    tout = target.get("timeout", opts["timeout"])
    size = target.get("size", opts["max_size"])
    port = target.get("tcp_port", opts["tcp_port"])
    ival = target.get("interval", opts["interval"])
    max_lost = target.get("max_lost", opts["max_lost"])
    rtt = target.get("rtt", opts["rtt"])
    tags = _build_tags(opts["name"], target)
    max_size = _max_size(opts)
    lost = 0
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
                    defaults.MSG_FMT.format(
                        seq=seq,
                        timestamp=ts,
                        source=opts["name"],
                        tags=target.get("tags", []),
                    ),
                    "utf-8",
                )
                if size and len(msg) < size:
                    msg += b"0" * (size - len(msg))
                log.debug(
                    "[TCP OWD client] Sending timestamp %s (SEQ: %d) to %s with tags: %s",
                    ts,
                    seq,
                    target["host"],
                    target.get("tags", []),
                )
                skt.sendall(msg)
                if rtt:
                    data = _read_tcp(skt, tout, max_size)
                    if not data:
                        log.warning(
                            "[TCP OWD client] didn't receive a response within %d "
                            "seconds from the TCP server: %s",
                            tout,
                            target,
                        )
                        rtt_ns = 0
                        lost += 1
                    else:
                        rtt_ns = time.time_ns() - ts
                        try:
                            srv_seq, srv_src, srv_ts, rtags, padding = str(
                                data, "utf-8"
                            ).split("|")
                            srv_seq = int(srv_seq)
                            log.debug(
                                "[TCP OWD client] Received RTT timestamp %s (SEQ: %d) "
                                "from %s with tags: %s",
                                srv_ts,
                                srv_seq,
                                srv_src,
                                rtags,
                            )
                        except ValueError:
                            srv_seq = -1
                            log.error(
                                "[TCP OWD client] Unable to unpack the computed OWD "
                                "from the server: %s",
                                data,
                            )
                        if srv_seq != seq:
                            rtt_ns = 0
                            log.warning(
                                "[TCP OWD client] Ignoring RTT packet, the seq "
                                "doesn't match (%d vs %d)",
                                seq,
                                srv_seq,
                            )
                            lost += 1
                        else:
                            lost = 0
                    rtt_metric = {
                        "metric": "tcp.wan.rtt",
                        "points": [(time.time_ns(), rtt_ns)],
                        "tags": tags,
                    }
                    log.debug(
                        "[TCP OWD client] Adding RTT metric to the metrics queue: %s",
                        rtt_metric,
                    )
                    metrics_q.put(rtt_metric)
                seq = _next_seq(seq)
                pause = ival - (time.time_ns() - ts) / 1e6
                if pause > 0:
                    log.debug(
                        "[TCP OWD client] Waiting %s milliseconds before sending the next probe",
                        pause,
                    )
                    time.sleep(pause / 1e3)
                if lost >= max_lost:
                    raise ConnectionResetError(f"Too many packets out of sync ({lost})")
    except (BrokenPipeError, ConnectionRefusedError, ConnectionResetError):
        log.info(
            "[TCP OWD client] Can't connect or connection lost with %s, will try again shortly...",
            target,
            exc_info=True,
        )
        time.sleep(0.1)
        owd_tcp_client(metrics_q, target, **opts)


def start_tcp_latency_pollers(metrics_q, **opts):
    """
    Dispatch pollers into their own threads.
    """
    log.debug("Starting the poller subprocess")
    threads = {}
    while True:
        for tid, tgt in enumerate(opts["targets"]):
            ttype = tgt.get("type")
            if (ttype and ttype != "tcp") or not tgt.get("tcp_latency", True):
                # Won't start a polling thread when the probe type is not TCP,
                # or when TCP latency probing is disabled.
                continue
            if tid not in threads:
                t = threading.Thread(
                    target=tcp_latency_poll,
                    args=(
                        metrics_q,
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


def _latency_point(host, port=defaults.TCP_PORT, timeout=defaults.TIMEOUT):
    """
    :rtype: Returns float if possible
    Calculate a latency point using sockets. If something bad happens the point returned is None.
    This function has been imported from the tcp-latency library and adapted to
    use nanoseconds timestamps and results for consistency with the rest of the code.
    """

    # Start a timer
    s_start = time.time_ns()

    # Try to Connect
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.shutdown(socket.SHUT_RD)

    # If something bad happens, the latency_point is None
    except socket.timeout:
        return None
    except OSError:
        return None

    return time.time_ns() - s_start


def tcp_latency_poll(metrics_q, target, **opts):
    """
    Execute the TCP latency runs against the given ip and port, and send the
    metrics to the publisher worker.
    """
    port = target.get("tcp_port", opts["tcp_port"])
    tout = target.get("timeout", opts["timeout"])
    ival = target.get("interval", opts["interval"])
    log.debug(
        "Polling target %s, timeout set at",
        target,
        tout,
    )
    tags = _build_tags(opts["name"], target)
    while True:
        probe_time = time.time_ns()
        res = _latency_point(
            host=target["host"],
            port=port,
            timeout=tout,
        )
        if not res:
            log.info(
                "[TCP Latency] Polling %s returned no results, "
                "the destination is likely unreachable or timed out.",
                target,
            )
            res = 0
        metric = {
            "metric": "tcp.wan.latency",
            "points": [(probe_time, res)],
            "tags": tags,
        }
        log.debug("Adding TCP latency metric to the publisher queue: %s", metric)
        metrics_q.put(metric)
        pause = ival - (time.time_ns() - probe_time) / 1e6
        if pause > 0:
            time.sleep(pause / 1e3)
