SELECT MAX(record_count) AS max_rows, MIN(record_count) AS min_rows,
       AVG(record_count) AS avg_rows, COUNT(*) AS partition_count
FROM {table_name}.partitions
