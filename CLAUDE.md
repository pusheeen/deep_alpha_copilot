# Instructions for Claude

## Code Safety
1. **Never delete all code without explicit permission** - Always preserve existing functionality unless explicitly instructed to remove it. If major deletions are needed, ask for confirmation first.

## Workflow Management
2. **Stay unblocked** - If you encounter a blocker or are waiting on something, always find alternative tasks to work on. Don't stay idle.

3. **Don't wait for input** - If you need user input but can make progress on other parts of the task, continue working on what you can do independently. Get yourself unblocked by working on parallel tasks.

## Data Integrity
4. **Never fabricate data** - If you don't have access to actual data:
   - Clearly flag it as unavailable or inaccessible
   - Do NOT create fake, mock, or assumed data
   - Explicitly state what data is missing and what would be needed to obtain it
   - Use placeholder values only when clearly marked as such (e.g., `TODO: Replace with actual data`)

---

# Agent Supervision System

The Deep Alpha Copilot uses a built-in supervision system to ensure agents never get blocked and always provide accurate, factual data.

## How It Works

### 1. Root Agent Supervision (Built-in)
The `Financial_Root_Agent` has built-in supervision tools that it uses **before delegating** to sub-agents:

**Supervision Tools:**
- `validate_data_exists(ticker, data_type)` - Checks if required data exists before delegating
- `log_blocking_issue(agent_name, issue, ticker, action)` - Logs blocking issues and suggests alternatives
- `detect_fabricated_data(data, data_type, ticker)` - Detects fake or placeholder data

**Workflow:**
1. User asks for analysis (e.g., "Analyze NVDA financials")
2. Root agent validates: `validate_data_exists("NVDA", "financials")`
3. If data exists → Delegate to `CompanyData_Agent`
4. If data missing → Log issue and suggest alternatives (different ticker, different analysis, etc.)
5. After receiving results → Verify data is not fabricated
6. Optionally → Delegate to `AgentEvaluator` for quality checks

### 2. AgentEvaluator Sub-Agent (Post-Execution QA)
The `AgentEvaluator` is used **after agents complete** to validate quality:

**Evaluation Tools:**
- `check_data_freshness(ticker, data_type)` - Verifies data meets freshness guidelines
- `validate_data_source(data, expected_source, data_type)` - Confirms data comes from correct source
- `fact_check_agent_output(agent_name, output, ticker)` - Cross-checks outputs against actual data

**Data Freshness Guidelines:**
- Financial Statements: Max 90 days old (Quarterly)
- Earnings Data: Max 90 days old (Quarterly)
- Stock Prices: Max 1 day old (Daily)
- News: Max 12 hours old
- Reddit Sentiment: Max 6 hours old
- Institutional Flow: Max 90 days old (Quarterly)
- Company Runtime Cache: Max 30 minutes old

## Blocking Issue Logs

When agents encounter blockers, issues are logged to:
```
data/logs/agent_blocking/blocking_log_YYYYMMDD.jsonl
```

Each log entry contains:
- Timestamp
- Agent name that was blocked
- Issue description
- Ticker (if applicable)
- Attempted action
- Severity (low/medium/high)
- Alternative approaches suggested
- Resolution recommendations

## Anti-Fabrication Rules

The system actively prevents fake data through:

1. **Placeholder Detection**: Flags data containing TODO, FIXME, PLACEHOLDER, TBD, N/A, Mock, Fake, etc.
2. **Suspicious Patterns**: Detects unrealistically round numbers, repeated values, copy-paste patterns
3. **Impossible Values**: Catches future dates in historical data, out-of-range scores
4. **Source Verification**: Validates data comes from documented sources (yfinance, SEC EDGAR, Reddit API, etc.)
5. **Cross-Referencing**: Fact-checks numerical claims against actual computed data

## Alternative Task Strategy

When blocked, agents follow this priority:
1. **Different ticker with available data** (e.g., if NVDA data missing, analyze AMD instead)
2. **Different data type** (e.g., if financials missing, use news analysis)
3. **Cached/historical data** (e.g., if real-time API fails, use cached data)
4. **Partial results with disclaimer** (e.g., provide available metrics, note what's missing)
5. **Parallel independent tasks** (e.g., work on other analysis while waiting)
6. **Document and move on** (e.g., log the blocker and proceed to next task)

## For Developers

When adding new agents or data sources:
- Always check data existence before attempting access
- Use `validate_data_exists()` before expensive operations
- Log blocking issues with `log_blocking_issue()` for debugging
- Verify data legitimacy with `detect_fabricated_data()`
- Document data freshness requirements
- Provide clear error messages when data unavailable
