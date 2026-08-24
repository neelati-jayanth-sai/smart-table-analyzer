"""Helper functions for Alation API adapters."""



def _fetch_additional_table_metadata(
    session, base_url: str, table_id: int | None, headers: dict, verify_ssl: bool
) -> dict:
    """Fetch additional table-level metadata from Alation."""
    if not table_id:
        return {
            "partition_columns": None,
            "partition_definition": None,
            "table_comment": None,
            "table_sql": None,
            "table_type": None,
            "base_table_key": None,
        }
    
    try:
        table_response = session.get(
            f"{base_url}/integration/v2/table/",
            headers=headers,
            params={"id": table_id, "limit": 1},
            timeout=10,
            verify=verify_ssl,
        )
        if table_response.status_code == 200:
            tables = table_response.json()
            if isinstance(tables, list) and len(tables) > 0:
                table_data = tables[0]
                return {
                    "partition_columns": table_data.get("partition_columns"),
                    "partition_definition": table_data.get("partition_definition"),
                    "table_comment": table_data.get("table_comment"),
                    "table_sql": table_data.get("sql"),
                    "table_type": table_data.get("table_type"),
                    "base_table_key": table_data.get("base_table_key"),
                }
    except Exception:
        pass
    
    return {
        "partition_columns": None,
        "partition_definition": None,
        "table_comment": None,
        "table_sql": None,
        "table_type": None,
        "base_table_key": None,
    }
