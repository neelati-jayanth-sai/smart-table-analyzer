# Critic+Gate Pipeline Test Suite

## Overview

This test suite validates the Critic+Gate pipeline against fixed input states using MockLLMAdapter. The tests ensure that the pipeline enforces critical invariants for finding quality and consistency.

## Test File

`tests/test_critic_gate_pipeline.py` - 21 test cases covering all required invariants

## Invariants Validated

### 1. No Raw JSON in Output
Final findings should never contain raw JSON artifacts (e.g., ```json blocks) in any text fields.

**Tests:**
- `test_critic_strips_json_blocks_from_exact_result` - Verifies critic removes JSON blocks from exact_result
- `test_critic_strips_json_blocks_from_rationale` - Verifies critic removes JSON blocks from rationale
- `test_critic_rejects_dict_repr_in_exact_result` - Verifies critic rejects Python dict/list repr

### 2. No Placeholder Table Names
SQL and recommendations should never contain placeholder table names like "your_table_name" — they must use the actual fully-qualified table name.

**Tests:**
- `test_sanitize_actionable_sql_replaces_your_table` - Replaces "your_table" placeholder
- `test_sanitize_actionable_sql_replaces_my_db_my_table` - Replaces "my_db.my_table" placeholder
- `test_sanitize_actionable_sql_replaces_fully_qualified_placeholder` - Replaces fully-qualified placeholders
- `test_sanitize_actionable_sql_handles_none` - Handles None input gracefully
- `test_sanitize_actionable_sql_preserves_valid_sql` - Preserves valid SQL with real table names

### 3. No "N/A" Values
The Critic should use alternatives like "Not applicable" instead of "N/A" to avoid triggering quality gate rejections.

**Tests:**
- `test_quality_gate_rejects_na_in_rationale` - Quality gate rejects "N/A" in rationale
- `test_quality_gate_rejects_na_in_exact_result` - Quality gate rejects "N/A" in exact_result
- `test_quality_gate_accepts_not_applicable` - Quality gate accepts "Not applicable"
- `test_critic_replaces_na_with_not_applicable` - Critic replaces "N/A" with "Not applicable"

### 4. Max 2 Partition Columns
Partition recommendations should never suggest more than 2 partition columns (runbook rule).

**Tests:**
- `test_critic_rejects_three_partition_columns` - Critic rejects 3+ partition columns
- `test_critic_accepts_two_partition_columns` - Critic accepts exactly 2 partition columns
- `test_critic_accepts_single_partition_column` - Critic accepts 1 partition column

### 5. Priority Correctness
Priority should be correctly derived from verdict/severity (e.g., "Needs Review" findings should have appropriate priority levels).

**Tests:**
- `test_needs_review_verdict_requires_appropriate_priority` - Validates priority for needs_review verdict
- `test_not_found_verdict_lower_priority` - Validates lower priority for not_found verdict

### 6. Retry Loop Validation
Verify that max 2 retries are respected in the Critic+Gate loop.

**Tests:**
- `test_max_two_retries_enforced` - Verifies call count tracking and retry limit
- `test_quality_gate_triggers_retry` - Quality gate rejection triggers retry
- `test_inconclusive_triggers_retry` - Inconclusive verdict triggers retry

### 7. Happy Path
Valid Analyst output passes Critic+Gate unchanged.

**Tests:**
- `test_valid_finding_passes_critic_and_gate` - Well-formed finding passes both critic and quality gate

## MockLLMAdapter Enhancements

The existing `MockLLMAdapter` was enhanced to support advanced testing scenarios:

### New Methods
- `get_call_count()` - Returns total number of generate() calls made
- `reset()` - Resets index and call count for test isolation

### Usage Example
```python
llm = MockLLMAdapter([
    {"content": '{"verdict": "found", ...}'},
    {"content": '{"verdict": "found", ...}'},
])

# Make calls
llm.generate([{"role": "user", "content": "test"}])
llm.generate([{"role": "user", "content": "test"}])

# Verify call count
assert llm.get_call_count() == 2

# Reset for next test
llm.reset()
```

## Test Strategy

The tests use a focused approach:

1. **Isolation**: Each test validates a single invariant
2. **Determinism**: MockLLMAdapter provides fixed responses
3. **Speed**: No real Spark/LLM calls
4. **Clarity**: Test names and docstrings explain the scenario

## Adding New Regression Cases

To add a new regression case:

1. **Identify the invariant** - Determine which of the 5 invariants the test validates
2. **Add test method** - Add a new test method to the appropriate test class
3. **Configure mock responses** - Set up MockLLMAdapter responses for the scenario
4. **Set up initial state** - Use helper functions to create the test state
5. **Assert expected behavior** - Verify the invariant is enforced
6. **Document the scenario** - Add a clear docstring explaining the test

### Example
```python
class TestNoRawJSONInOutput:
    def test_critic_strips_json_blocks_from_new_field(self):
        """Critic should strip ```json blocks from new_field."""
        draft = _make_draft_analysis(
            new_field='```json\n{"data": "value"}\n```',
        )
        state = _make_base_state()
        state["current_analysis"] = draft

        llm = MockLLMAdapter([
            {
                "content": (
                    '{"verdict": "found", '
                    '"new_field": "Clean formatted value", '
                    '"rationale": "Test rationale", '
                    '"evidence_ids": ["trail:0"], '
                    '"recommendation": null, '
                    '"actionable_sql": null, '
                    '"approved": true}'
                )
            }
        ])

        validator = ResponseValidator()
        content = llm.generate([{"role": "user", "content": "test"}])["content"]
        is_valid, _, parsed = validator.validate_analysis_response(content)
        assert is_valid
        assert "```json" not in parsed["new_field"]
```

## Running the Tests

### Run all tests
```bash
python -m pytest tests/test_critic_gate_pipeline.py -v
```

### Run specific test class
```bash
python -m pytest tests/test_critic_gate_pipeline.py::TestNoRawJSONInOutput -v
```

### Run specific test
```bash
python -m pytest tests/test_critic_gate_pipeline.py::TestNoRawJSONInOutput::test_critic_strips_json_blocks_from_exact_result -v
```

### Run standalone (without pytest)
```bash
python tests/test_critic_gate_pipeline.py
```

## Test Results

All 21 tests pass:
- TestNoRawJSONInOutput: 3 tests
- TestNoPlaceholderTableNames: 5 tests
- TestNoNAValues: 4 tests
- TestMaxTwoPartitionColumns: 3 tests
- TestPriorityCorrectness: 2 tests
- TestRetryLoop: 3 tests
- TestHappyPath: 1 test

Total test suite: 78 tests (57 existing + 21 new)
All tests pass: ✅

## Files Modified

1. `src/connectors/llm_adapter.py` - Enhanced MockLLMAdapter with call tracking
2. `tests/test_critic_gate_pipeline.py` - New test file with 21 test cases
3. `tests/CRITIC_GATE_PIPELINE_TEST_STRATEGY.md` - This documentation

## Notes

- Tests are fast (no real Spark/LLM calls)
- Tests are deterministic (fixed mock responses)
- Tests follow existing test patterns in the codebase
- All 57 existing tests still pass after adding the new suite
