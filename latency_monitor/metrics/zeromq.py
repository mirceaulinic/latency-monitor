# -*- coding: utf-8 -*-
"""
ZeroMQ metrics backend
======================

Puts the metrics on the event bus as soon as they're received.

By default, the ZMQ socket will bind on the local port 8002 (listening to any
interface), but you can change that using the ``address`` and ``port`` options
that you can provide under the ``metrics`` block.

Once you started up the process, you can then subscribe to the ZMQ bus and start
receiving the metrics.
"""

import logging

try:
    import zmq

    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False

log = logging.getLogger(__name__)


class ZeroMQ:
    def __init__(self, **opts):
        """ """
        self.address = opts["metrics"].get("address", "0.0.0.0")
        self.port = opts["metrics"].get("port", 8002)
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        if ":" in self.address:
            self.socket.ipv6 = True
        try:
            self.socket.bind(
                "tcp://{addr}:{port}".format(addr=self.address, port=self.port)
            )
        except zmq.error.ZMQError as err:
            log.error(err, exc_info=True)
            raise

    def start(self, pub_q, **opts):
        """
        Worker that constantly checks if there's a new metric into the queue,
        and sends it over the ZeroMQ socket, from where you can pick it up.
        """
        log.debug("Starting ZeroMQ publisher")
        while True:
            log.debug("[ZeroMQ] Waiting for a new metric")
            m = pub_q.get()
            log.debug("[ZeroMQ] Picked metric from the queue: %s", m)
            self.socket.send(m)
