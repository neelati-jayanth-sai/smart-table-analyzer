"""Mock Alation adapter for testing."""

from __future__ import annotations

from .alation_adapter import AlationContextAdapter, TablePatterns


class MockAlationAdapter(AlationContextAdapter):
    """Mock Alation adapter that returns static patterns for testing."""

    def is_available(self) -> bool:
        return True

    def get_table_patterns(self, table_name: str) -> TablePatterns:
        return TablePatterns(
            common_joins=[
                {"table": "dim_customer", "join_type": "inner", "on": "customer_id"},
                {"table": "dim_product", "join_type": "left", "on": "product_id"},
            ],
            common_filters=[
                {"column": "order_date", "operator": ">=", "value": "2024-01-01"},
                {"column": "status", "operator": "=", "value": "active"},
            ],
            downstream_count=5,
            upstream_count=3,
            stewards=["data_team@example.com"],
            custom_fields={"sla_tier": "gold", "contains_pii": False},
            popular_columns=[
                {"name": "customer_id", "title": "Customer ID", "data_type": "int"},
                {"name": "order_date", "title": "Order Date", "data_type": "date"},
                {"name": "status", "title": "Status", "data_type": "string"},
            ],
            partition_columns=["order_date"],
            partition_definition="day(order_date)",
            table_comment="Customer orders fact table",
            table_sql="SELECT * FROM raw_orders",
            table_type="base",
            base_table_key=None,
        )
