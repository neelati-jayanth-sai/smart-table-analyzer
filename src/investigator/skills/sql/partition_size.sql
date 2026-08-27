SELECT COUNT(*) AS partition_count, AVG(total_data_file_size_in_bytes) AS avg_bytes,
       MIN(total_data_file_size_in_bytes) AS min_bytes, MAX(total_data_file_size_in_bytes) AS max_bytes
FROM {table_name}.partitions
