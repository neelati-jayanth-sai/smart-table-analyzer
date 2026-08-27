SELECT COUNT(*) AS file_count, MIN(file_size_in_bytes) AS min_bytes,
       MAX(file_size_in_bytes) AS max_bytes, AVG(file_size_in_bytes) AS avg_bytes
FROM {table_name}.files WHERE content = 0
