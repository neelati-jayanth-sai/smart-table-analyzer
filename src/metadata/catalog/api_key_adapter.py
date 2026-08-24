"""Alation API key adapter using standard REST API."""

from __future__ import annotations

import logging
import os

import requests

from .alation_adapter import AlationContextAdapter, TablePatterns
from .api_helpers import _fetch_additional_table_metadata

logger = logging.getLogger(__name__)


class AlationAPIKeyAdapter(AlationContextAdapter):
    """Alation context adapter using API key authentication."""

    def __init__(
        self,
        base_url: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        user_id: str | None = None,
        verify_ssl: bool = False,
    ):
        self._base_url = base_url or os.getenv("ALATION_BASE_URL")
        self._access_token = access_token or os.getenv("ALATION_ACCESS_TOKEN")
        self._refresh_token = refresh_token or os.getenv("ALATION_REFRESH_TOKEN")
        self._user_id = user_id or os.getenv("ALATION_USER_ID")
        self._verify_ssl = verify_ssl or os.getenv("ALATION_VERIFY_SSL", "false").lower() == "true"
        self._session = requests.Session()

    def is_available(self) -> bool:
        if not self._base_url or not self._access_token:
            return False
        try:
            response = self._session.get(
                f"{self._base_url}/integration/v1/datasource/",
                headers={"TOKEN": self._access_token},
                timeout=10,
                verify=self._verify_ssl,
            )
            return response.status_code == 200
        except Exception:
            return False

    def _get_access_token(self) -> str:
        if not self._access_token:
            raise ValueError("No access token available")
        return self._access_token

    def get_table_patterns(self, table_name: str) -> TablePatterns:
        token = self._get_access_token()
        headers = {"TOKEN": token}

        # Use actual table name from environment if provided (for replica tables)
        alation_table_name = os.getenv("ALATION_ACTUAL_TABLE_NAME", table_name)
        
        logger.info(f"Fetching patterns for table: {table_name} (Alation lookup: {alation_table_name})")

        # Try to find the table by name in v2 table API
        table_id = None
        try:
            table_response = self._session.get(
                f"{self._base_url}/integration/v2/table/",
                headers=headers,
                params={"name__icontains": alation_table_name, "limit": 5},
                timeout=10,
                verify=self._verify_ssl,
            )
            if table_response.status_code == 200:
                tables = table_response.json()
                if isinstance(tables, list) and len(tables) > 0:
                    # Find exact match or closest match
                    for t in tables:
                        if t.get("name", "").lower() == alation_table_name.lower():
                            table_id = t.get("id")
                            break
                    if not table_id:
                        table_id = tables[0].get("id")
        except Exception as e:
            logger.debug(f"Table lookup failed: {e}")

        # Get joins using v2 API (may not be available on all instances)
        common_joins = []
        if table_id:
            try:
                joins_response = self._session.get(
                    f"{self._base_url}/integration/v2/join_predicates/table/{table_id}/",
                    headers=headers,
                    params={"limit": 5},
                    timeout=10,
                    verify=self._verify_ssl,
                )
                if joins_response.status_code == 200:
                    joins = joins_response.json()
                    common_joins = [
                        {
                            "content": j.get("content"),
                            "freq": j.get("freq", 0),
                            "is_suggested": j.get("is_suggested", False),
                        }
                        for j in joins[:5]
                    ]
            except Exception as e:
                logger.debug(f"Joins fetch failed: {e}")

        # Get table metadata and columns using v2 API
        custom_fields = {}
        stewards = []
        popular_columns = []
        if table_id:
            try:
                table_response = self._session.get(
                    f"{self._base_url}/integration/v2/table/",
                    headers=headers,
                    params={"id": table_id, "limit": 1},
                    timeout=10,
                    verify=self._verify_ssl,
                )
                if table_response.status_code == 200:
                    tables = table_response.json()
                    if isinstance(tables, list) and len(tables) > 0:
                        table_data = tables[0]
                        custom_fields = table_data.get("custom_fields", {})
                        if "stewards" in table_data:
                            stewards = [s.get("name", s.get("username", "")) for s in table_data["stewards"]]

                # Get columns for this table
                columns_response = self._session.get(
                    f"{self._base_url}/integration/v2/column/",
                    headers=headers,
                    params={"table_id": table_id, "limit": 50},
                    timeout=10,
                    verify=self._verify_ssl,
                )
                if columns_response.status_code == 200:
                    columns = columns_response.json()
                    if isinstance(columns, list):
                        popular_columns = [
                            {
                                "name": c.get("name"),
                                "title": c.get("title"),
                                "data_type": c.get("data_type"),
                                "custom_fields": c.get("custom_fields", {}),
                            }
                            for c in columns[:50]
                        ]
            except Exception as e:
                logger.warning(f"Table/columns metadata fetch failed: {e}")

        # For now, common_filters is not available via standard API
        # It requires the AI Agent SDK's aggregated context tool
        common_filters = []

        additional_metadata = _fetch_additional_table_metadata(
            self._session, self._base_url, table_id, headers, self._verify_ssl
        )
        
        return TablePatterns(
            common_joins=common_joins,
            common_filters=common_filters,
            downstream_count=0,  # Not available via standard API
            upstream_count=0,  # Not available via standard API
            stewards=stewards,
            custom_fields=custom_fields,
            popular_columns=popular_columns,
            **additional_metadata,
        )
