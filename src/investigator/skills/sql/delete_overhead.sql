SELECT COUNT(*) AS delete_files, COALESCE(SUM(file_size_in_bytes), 0) AS delete_bytes
FROM {table_name}.files WHERE content != 0
