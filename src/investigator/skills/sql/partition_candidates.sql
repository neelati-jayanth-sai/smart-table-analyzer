SELECT COUNT(*) AS file_count, COALESCE(SUM(record_count), 0) AS row_count
FROM {table_name}.files WHERE content = 0
