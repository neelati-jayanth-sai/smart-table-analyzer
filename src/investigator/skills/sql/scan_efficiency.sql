SELECT COUNT(*) AS file_count, COALESCE(SUM(file_size_in_bytes), 0) AS data_bytes,
       COALESCE(SUM(record_count), 0) AS row_count
FROM {table_name}.files WHERE content = 0
