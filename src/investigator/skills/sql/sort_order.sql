SELECT COUNT(DISTINCT sort_order_id) AS sort_orders, COUNT(*) AS file_count
FROM {table_name}.files WHERE content = 0
