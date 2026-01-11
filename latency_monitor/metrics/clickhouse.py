# -*- coding: utf-8 -*-
"""
Clickhouse metrics backend
==========================
"""
import datetime
import logging

from latency_monitor.metrics.accumulator import Accumulator

try:
    import clickhouse_connect

    HAS_CH = True
except ImportError:
    HAS_CH = False

log = logging.getLogger(__name__)


class Clickhouse(Accumulator):
    """
    Accumulate metrics and ship them at specific intervals.
    """

    def __init__(self, **opts):
        super().__init__(**opts)
        self.client = clickhouse_connect.get_client(
            host=self.opts["metrics"]["host"],
            port=self.opts["metrics"].get("port", 8443),
            username=self.opts["metrics"].get("username", "default"),
            password=self.opts["metrics"]["password"],
        )
        self.table = self.opts["metrics"].get("table", "metrics")
        self.columns = self.opts["metrics"].get(
            "columns", ["MetricName", "Timestamp", "MetricValue", "Tags", "InsertedAt"]
        )

    def _push_metrics(self, metrics):
        """
        Prepare the list of metrics and create the insert queries.
        """
        rows = []
        inserted_at = datetime.datetime.now(datetime.UTC).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )
        for metric in metrics:
            tags = dict(map(lambda t: t.split(":"), metric["tags"]))
            for p in metric["points"]:
                rows.append([metric["metric"], p[0], p[1], tags, inserted_at])
        log.debug("[Clickhouse] Inserting rows")
        self.client.insert(self.table, rows, column_names=self.columns)
