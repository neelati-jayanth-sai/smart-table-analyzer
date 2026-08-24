"""The recommendation seam only exposes reviewable remediation SQL."""

from src.investigator.critic.action_safety import approve_actionable_sql


TABLE = "cat.sch.orders"


def test_allows_a_rewrite_for_the_investigated_table():
    sql = "CALL system.rewrite_data_files(table => 'cat.sch.orders')"

    assert approve_actionable_sql(sql, TABLE) == f"{sql};"


def test_rejects_a_rewrite_for_another_table():
    sql = "CALL system.rewrite_data_files(table => 'cat.sch.secrets')"

    assert approve_actionable_sql(sql, TABLE) is None


def test_rejects_destructive_and_multi_statement_sql():
    assert approve_actionable_sql("DROP TABLE cat.sch.orders", TABLE) is None
    assert approve_actionable_sql("SELECT 1; DROP TABLE cat.sch.orders", TABLE) is None


def test_allows_canonical_property_update_only():
    valid = "ALTER TABLE cat.sch.orders SET TBLPROPERTIES ('write.target-file-size-bytes' = '134217728')"
    mixed_case = "ALTER TABLE cat.sch.orders SET TBLPROPERTIES ('Write.Target-File-Size-Bytes' = '134217728')"

    assert approve_actionable_sql(valid, TABLE) == f"{valid};"
    assert approve_actionable_sql(mixed_case, TABLE) is None
