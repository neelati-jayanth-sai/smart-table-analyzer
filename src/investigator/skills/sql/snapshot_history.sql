SELECT COUNT(*) AS snapshot_count, MIN(committed_at) AS oldest_snapshot,
       MAX(committed_at) AS newest_snapshot
FROM {table_name}.snapshots
