"""Realistic mock Iceberg tables.

Each scenario builds the metadata an Iceberg table actually exposes — `.files`,
`.partitions`, `.snapshots`, `.history`, table properties — with values chosen
so exactly one class of problem is present. That lets a test assert that the
Legacy Analyzer detects the intended signal *and* that it does not fire the
others, which is what proves the Investigator adapts to the table in front of it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

MB = 1024 * 1024
TARGET_FILE_BYTES = 128 * MB

# Iceberg metadata table schemas, trimmed to the columns real queries use.
FILES_COLUMNS = [
    ("content", "int"),
    ("file_path", "string"),
    ("file_format", "string"),
    ("spec_id", "int"),
    ("record_count", "bigint"),
    ("file_size_in_bytes", "bigint"),
    ("sort_order_id", "int"),
    ("partition", "struct<order_date:date>"),
]
PARTITIONS_COLUMNS = [
    ("partition", "struct<order_date:date>"),
    ("spec_id", "int"),
    ("record_count", "bigint"),
    ("file_count", "int"),
    ("total_data_file_size_in_bytes", "bigint"),
    ("last_updated_at", "timestamp"),
]
SNAPSHOTS_COLUMNS = [
    ("committed_at", "timestamp"),
    ("snapshot_id", "bigint"),
    ("parent_id", "bigint"),
    ("operation", "string"),
    ("manifest_list", "string"),
]
HISTORY_COLUMNS = [
    ("made_current_at", "timestamp"),
    ("snapshot_id", "bigint"),
    ("parent_id", "bigint"),
    ("is_current_ancestor", "boolean"),
]

BASE_COLUMNS = [
    ("order_id", "bigint"),
    ("customer_id", "bigint"),
    ("region", "string"),
    ("status", "string"),
    ("amount", "decimal(18,2)"),
    ("order_date", "date"),
]

_EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)


@dataclass
class MockIcebergTable:
    """One table's worth of Iceberg metadata.

    `row_count` is the table's logical row count, which a real 600M-row table
    reports from `COUNT(*)` while `rows` holds only the sample a `LIMIT` would
    return. `column_stats` supplies per-column cardinality/null counts for the
    same reason: real cardinality analysis runs over the full table, not the
    sample.
    """

    name: str
    row_count: int
    columns: list[tuple[str, str]] = field(default_factory=lambda: list(BASE_COLUMNS))
    rows: list[dict[str, Any]] = field(default_factory=list)
    files: list[dict[str, Any]] = field(default_factory=list)
    partitions: list[dict[str, Any]] = field(default_factory=list)
    snapshots: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    properties: dict[str, str] = field(default_factory=dict)
    partition_columns: list[str] = field(default_factory=list)
    column_stats: dict[str, tuple[int, int]] = field(default_factory=dict)

    def metadata_rows(self, suffix: str) -> list[dict[str, Any]]:
        return {
            "files": self.files,
            "partitions": self.partitions,
            "snapshots": self.snapshots,
            "history": self.history,
        }[suffix]

    def metadata_columns(self, suffix: str) -> list[tuple[str, str]]:
        return {
            "files": FILES_COLUMNS,
            "partitions": PARTITIONS_COLUMNS,
            "snapshots": SNAPSHOTS_COLUMNS,
            "history": HISTORY_COLUMNS,
        }[suffix]

    @property
    def total_data_bytes(self) -> int:
        return sum(f["file_size_in_bytes"] for f in self.files if f["content"] == 0)

    @property
    def avg_file_bytes(self) -> float:
        data_files = [f for f in self.files if f["content"] == 0]
        return self.total_data_bytes / len(data_files) if data_files else 0.0


# --------------------------------------------------------------- row builders


def _data_file(index: int, size_bytes: int, records: int, partition: str,
               sort_order_id: int = 0, content: int = 0) -> dict[str, Any]:
    return {
        "content": content,
        "file_path": f"s3://warehouse/orders/data/{partition}/{index:05d}.parquet",
        "file_format": "PARQUET",
        "spec_id": 0,
        "record_count": records,
        "file_size_in_bytes": size_bytes,
        "sort_order_id": sort_order_id,
        "partition": {"order_date": partition},
    }


def _partition_row(partition: str, records: int, files: int, bytes_: int) -> dict[str, Any]:
    return {
        "partition": {"order_date": partition},
        "spec_id": 0,
        "record_count": records,
        "file_count": files,
        "total_data_file_size_in_bytes": bytes_,
        "last_updated_at": (_EPOCH + timedelta(days=1)).isoformat(),
    }


def _snapshots(count: int) -> list[dict[str, Any]]:
    return [
        {
            "committed_at": (_EPOCH + timedelta(hours=i)).isoformat(),
            "snapshot_id": 7000000000000000000 + i,
            "parent_id": 7000000000000000000 + i - 1 if i else None,
            "operation": "append",
            "manifest_list": f"s3://warehouse/orders/metadata/snap-{i}.avro",
        }
        for i in range(count)
    ]


def _history(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "made_current_at": s["committed_at"],
            "snapshot_id": s["snapshot_id"],
            "parent_id": s["parent_id"],
            "is_current_ancestor": True,
        }
        for s in snapshots
    ]


def _sample_rows(count: int, regions: list[str], seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    return [
        {
            "order_id": 100000 + i,
            "customer_id": rng.randint(1, 50_000),
            "region": rng.choice(regions),
            "status": rng.choice(["SHIPPED", "PENDING", "CANCELLED"]),
            "amount": round(rng.uniform(10, 5000), 2),
            "order_date": (_EPOCH + timedelta(days=rng.randint(0, 400))).date().isoformat(),
        }
        for i in range(count)
    ]


_HEALTHY_PROPERTIES = {
    "format-version": "2",
    "write.target-file-size-bytes": str(TARGET_FILE_BYTES),
    "write.distribution-mode": "hash",
    "history.expire.max-snapshot-age-ms": "604800000",
}

def _finalize(table: MockIcebergTable) -> MockIcebergTable:
    """Derive the totals Iceberg reports from metadata, keeping them coherent.

    A table's row count is the sum of its data files' record counts, and
    `order_date` cardinality is its partition count — the mock must not report
    numbers a real table could never report together.
    """
    table.row_count = sum(f["record_count"] for f in table.files if f["content"] == 0)
    distinct_customers = min(50_000, max(table.row_count // 2_000, 1))
    table.column_stats = {
        "order_id": (table.row_count, 0),
        "customer_id": (distinct_customers, 0),
        "region": (len({r["region"] for r in table.rows}) or 1, 0),
        "status": (3, 0),
        "amount": (max(table.row_count // 500, 1), 0),
        "order_date": (len(table.partitions) or 1, 0),
    }
    return table


# ----------------------------------------------------------------- scenarios


def healthy_table(name: str = "cat.sch.orders_healthy") -> MockIcebergTable:
    """Well-maintained: 128 MB files, even partitions, sorted, few snapshots."""
    partitions, files = [], []
    for day in range(120):
        partition = f"2026-{1 + day // 30:02d}-{1 + day % 30:02d}"
        size = 130 * MB
        partitions.append(_partition_row(partition, 1_000_000, 2, size * 2))
        files += [
            _data_file(len(files), size, 500_000, partition, sort_order_id=1),
            _data_file(len(files) + 1, size, 500_000, partition, sort_order_id=1),
        ]
    snapshots = _snapshots(4)
    return _finalize(MockIcebergTable(
        name=name,
        row_count=0,
        rows=_sample_rows(50, ["AMER", "EMEA", "APJ"], seed=1),
        files=files,
        partitions=partitions,
        snapshots=snapshots,
        history=_history(snapshots),
        properties={**_HEALTHY_PROPERTIES, "sort-order": "order_date ASC, region ASC"},
        partition_columns=["order_date"],
    ))


def partition_skew_table(name: str = "cat.sch.orders_skewed") -> MockIcebergTable:
    """One partition holds ~40x the average; file sizes are otherwise healthy."""
    partitions, files = [], []
    for day in range(200):
        partition = f"2026-{1 + day // 30:02d}-{1 + day % 30:02d}"
        if day == 7:
            records, file_count, size = 40_000_000, 8, 140 * MB
        else:
            records, file_count, size = 1_000_000, 1, 130 * MB
        partitions.append(_partition_row(partition, records, file_count, size * file_count))
        for _ in range(file_count):
            files.append(
                _data_file(len(files), size, records // file_count, partition, sort_order_id=1)
            )
    snapshots = _snapshots(6)
    return _finalize(MockIcebergTable(
        name=name,
        row_count=0,
        rows=_sample_rows(50, ["AMER", "EMEA"], seed=2),
        files=files,
        partitions=partitions,
        snapshots=snapshots,
        history=_history(snapshots),
        properties={**_HEALTHY_PROPERTIES, "sort-order": "order_date ASC"},
        partition_columns=["order_date"],
    ))


def small_files_table(name: str = "cat.sch.orders_fragmented") -> MockIcebergTable:
    """Streaming ingest left ~6 MB files; partitions are otherwise balanced."""
    partitions, files = [], []
    for day in range(120):
        partition = f"2026-{1 + day // 30:02d}-{1 + day % 30:02d}"
        file_count = 25
        size = 6 * MB
        partitions.append(_partition_row(partition, 1_000_000, file_count, size * file_count))
        for _ in range(file_count):
            files.append(_data_file(len(files), size, 40_000, partition, sort_order_id=1))
    snapshots = _snapshots(12)
    return _finalize(MockIcebergTable(
        name=name,
        row_count=0,
        rows=_sample_rows(50, ["AMER", "EMEA", "APJ", "LATAM"], seed=3),
        files=files,
        partitions=partitions,
        snapshots=snapshots,
        history=_history(snapshots),
        properties={**_HEALTHY_PROPERTIES, "sort-order": "order_date ASC"},
        partition_columns=["order_date"],
    ))


def missing_sort_order_table(name: str = "cat.sch.orders_unsorted") -> MockIcebergTable:
    """Healthy sizes and balanced partitions, but nothing is sorted."""
    table = healthy_table(name)
    table.files = [{**f, "sort_order_id": 0} for f in table.files]
    table.properties = dict(_HEALTHY_PROPERTIES)
    table.properties.pop("write.distribution-mode", None)
    return table


def delete_heavy_table(name: str = "cat.sch.orders_mor") -> MockIcebergTable:
    """Merge-on-read deletes are a third of the table's bytes."""
    table = healthy_table(name)
    delete_files = [
        _data_file(10_000 + i, 40 * MB, 50_000, f"2026-01-{1 + i % 30:02d}", content=1)
        for i in range(240)
    ]
    table.files = table.files + delete_files
    table.name = name
    return _finalize(table)


def caps_properties_table(name: str = "cat.sch.orders_caps") -> MockIcebergTable:
    """Properties written with uppercase names, which Iceberg will not honour."""
    table = healthy_table(name)
    table.properties = {**table.properties, "Write.Target-File-Size-Bytes": "268435456"}
    table.name = name
    return table


def empty_table(name: str = "cat.sch.orders_empty") -> MockIcebergTable:
    """Declared but never written to."""
    return MockIcebergTable(
        name=name,
        row_count=0,
        rows=[],
        files=[],
        partitions=[],
        snapshots=[],
        history=[],
        properties=dict(_HEALTHY_PROPERTIES),
        partition_columns=["order_date"],
    )


SCENARIOS = {
    "healthy": healthy_table,
    "partition_skew": partition_skew_table,
    "small_files": small_files_table,
    "missing_sort_order": missing_sort_order_table,
    "delete_overhead": delete_heavy_table,
    "table_property_naming": caps_properties_table,
    "empty": empty_table,
}
