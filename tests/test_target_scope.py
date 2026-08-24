"""Evidence SQL cannot escape the investigated table scope."""

from src.query.target_scope import TargetTableHook


def test_allows_the_target_and_iceberg_metadata_relations():
    hook = TargetTableHook("cat.sch.orders")

    assert hook.validate("SELECT * FROM cat.sch.orders").is_valid
    assert hook.validate("SELECT * FROM cat.sch.orders.files").is_valid


def test_rejects_another_table_in_the_allowed_schema():
    result = TargetTableHook("cat.sch.orders").validate("SELECT * FROM cat.sch.secrets")

    assert not result.is_valid
    assert "cat.sch.secrets" in result.error_message
