Clickhouse
==========

Inserts rows into a Clickhouse table, by default expected to be named ``metrics``. The metrics are accumulated for 30 
seconds (the interval can be adjusted), to avoid too frequent INSERT operations.

This backend requires the ``clickhouse-connect`` library, can either be installed separately, or invoking the clickhouse 
external dependency when using pip: ``pip install latency-monitor[clickhouse]``.

The following configuration options are available:

* ``host``: the IP or hostname of the Clickhouse server.
* ``port``: the port number Clickhouse is listening on. Default: ``9443``.
* ``username``: the Clickhouse username. Default: ``default``.
* ``password``: the Clickhouse password.
* ``table``: the table name where to insert the entries. Default: ``metrics``.
* ``columns``: the column names to insert the entries. This is a list, and the order matters. The default column names 
  are, in this order: ``MetricName``, ``Timestamp``, ``MetricValue``, ``Tags``, ``InsertedAt``. You may want to use 
  alternative column names, with similar use-case.
* ``send_interval``: for how long to accumulate metrics before sending them. Default: ``30`` (seconds).

Configuration example:

```toml
[metrics]
backend = "clickhouse"
host = "click.example.com"
password = "yourpass"
columns = ["name", "timestamp", "value", "tags", "inserted_at"]
```

Your Clickhouse table may look like this (or similar):

```sql
CREATE TABLE IF NOT EXISTS default.metrics
(
    MetricName        String,
    Timestamp         UInt64,
    MetricValue       UInt64,
    Tags              Map(LowCardinality(String), String),
    InsertedAt        DateTime64(9) CODEC (Delta, ZSTD),
    RetentionDays     UInt8 DEFAULT 30
) ENGINE = MergeTree()
    TTL toDateTime(InsertedAt) + toIntervalDay(RetentionDays)
    PARTITION BY toStartOfDay(InsertedAt)
    ORDER BY (MetricName, toUnixTimestamp64Nano(InsertedAt))
```

Using this configuration, Clickhouse will automatically cleanup entries older than 30 days -- but you may have different
requirements.
