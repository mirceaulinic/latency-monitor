# -*- coding: utf-8 -*-
"""
Latency Monitor defaults
========================
"""

import json
import os
import socket

RTT = True
TCP = True
UDP = True
TCP_LATENCY = True
NAME = socket.gethostname()
CFG_FILE = os.path.join(os.getcwd(), "latency.toml")
TCP_PORT = 8000
UDP_PORT = 8001
TIMEOUT = 1.0
INTERVAL = 1000
MAX_SEQ = 100
MAX_CONN = 40
MAX_SIZE = 1470
MAX_LOST = 10
LOG_LEVEL = "INFO"
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(message)s"

MSG_FMT = "{seq}|{source}|{timestamp}|{tags}|"

FMT_MAP = {
    "json": json.dumps,
}
