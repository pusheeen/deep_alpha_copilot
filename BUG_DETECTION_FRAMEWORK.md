# Bug Detection Framework for AgentEvaluator

## Overview

The AgentEvaluator has been enhanced with comprehensive bug detection capabilities that go beyond data validation to include UI testing, business logic validation, and bug reporting/coordination.

## Framework Components

### 1. Feature Functionality Testing (`test_ui_feature`)

**Purpose**: Systematically test each UI feature to verify it's working correctly.

**Supported Features**:
- `score_display`: Tests score generation and display API
- `price_chart`: Tests price history chart rendering
- `news_section`: Tests news fetching and display
- `comparison`: Tests multi-stock comparison feature
- `chat`: Tests AI chat interface
- `market_conditions`: Tests market indicators display
- `flow_data`: Tests institutional/retail flow data
- `valuation_metrics`: Tests P/E, P/S ratio display

**What It Checks**:
- API endpoint availability and response codes
- Required fields presence
- Data validity (scores 0-10, valid recommendations, etc.)
- Response structure correctness

**Example Usage**:
```python
test_ui_feature("score_display", "NVDA")
# Returns: {"status": "PASS", "issues": [], ...}
```

### 2. Business Logic Validation (`validate_business_logic`)

**Purpose**: Use domain knowledge and common sense reasoning to validate if scores/recommendations make sense.

**Domain Knowledge Base**:
- **GOOGL**: Expected score >= 7.0 (strong cloud business, AI leadership, momentum)
- **INTC**: Expected score >= 6.0 (US government backing, Apple chip manufacturing potential, TSMC partnership)
- **NVDA**: Expected score >= 8.0 (AI chip dominance, strong fundamentals)
- **TSM**: Expected score >= 8.0 (semiconductor manufacturing leader, strategic importance)
- **AMD**: Expected score >= 7.0 (AI competition, data center growth)

**What It Checks**:
- Score ranges against expected domain knowledge
- Component score consistency (Critical Path, Business, etc.)
- Recommendation consistency with overall score
- Cross-validation of scores with company fundamentals

**Example Scenarios**:
1. **GOOGL scores 6.0**: Flagged as bug - should be >= 7.0 given strong cloud/AI business
2. **INTC scores 5.0**: Flagged as bug - should be >= 6.0 given government backing and strategic partnerships
3. **Score 8.5 but recommendation "Hold"**: Flagged as inconsistency - should be "Buy" or "Strong Buy"

**Example Usage**:
```python
validate_business_logic("GOOGL", scores)
# Returns: {"status": "FAIL", "business_logic_issues": ["Score 6.0 below expected minimum 7.0"], ...}
```

### 3. Bug Reporting (`report_bug`)

**Purpose**: Document bugs with structured information for tracking and fixing.

**Bug Types**:
- `ui`: UI rendering or functionality issues
- `api`: API endpoint errors or incorrect responses
- `business_logic`: Scoring or recommendation logic errors
- `data`: Data quality or freshness issues
- `performance`: Performance or latency issues

**Severity Levels**:
- `CRITICAL`: System down, data corruption, security issues
- `HIGH`: Business logic errors, incorrect scores, broken core features
- `MEDIUM`: UI glitches, minor data inconsistencies, performance issues
- `LOW`: Cosmetic issues, minor warnings, edge cases

**Bug Report Structure**:
```json
{
  "bug_id": "BUG-20250101-123456-BUSINESS_LOGIC",
  "timestamp": "2025-01-01T12:34:56",
  "bug_type": "business_logic",
  "severity": "HIGH",
  "description": "GOOGL score too low given fundamentals",
  "feature": "scoring",
  "ticker": "GOOGL",
  "reproduction_steps": [...],
  "expected_behavior": "Score should be >= 7.0",
  "actual_behavior": "Score is 6.0",
  "suggested_fix": "Review scoring weights for cloud/AI factors",
  "status": "OPEN"
}
```

**Storage**: Bugs are saved to `data/logs/bugs/` directory as individual JSON files and appended to `bug_log.jsonl`.

### 4. Fix Coordination (`coordinate_fix`)

**Purpose**: Coordinate with root agent to fix reported bugs.

**Process**:
1. Load bug report
2. Create fix plan based on bug type
3. Assign tasks to appropriate agents
4. Update bug status to "IN_PROGRESS"
5. Return coordination result with assigned tasks

**Task Assignment**:
- `ui` bugs → Root Agent (inspect UI code)
- `business_logic` bugs → Root Agent + CompanyData_Agent (review scoring logic)
- `api` bugs → Root Agent (fix API endpoint)

## Complete Bug Detection Workflow

### Example: Detecting GOOGL Score Issue

1. **Test UI Feature**:
   ```python
   test_ui_feature("score_display", "GOOGL")
   # Result: PASS - API works correctly
   ```

2. **Validate Business Logic**:
   ```python
   validate_business_logic("GOOGL", scores)
   # Result: FAIL - Score 6.0 below expected minimum 7.0
   ```

3. **Report Bug**:
   ```python
   report_bug(
       bug_type="business_logic",
       severity="HIGH",
       description="GOOGL score 6.0 too low given strong cloud business, AI leadership, and momentum",
       feature="scoring",
       ticker="GOOGL",
       expected_behavior="Score should be >= 7.0",
       actual_behavior="Score is 6.0",
       suggested_fix="Review scoring weights for cloud/AI factors in compute_business_score()"
   )
   # Returns: bug_id = "BUG-20250101-123456-BUSINESS_LOGIC"
   ```

4. **Coordinate Fix**:
   ```python
   coordinate_fix(
       bug_id="BUG-20250101-123456-BUSINESS_LOGIC",
       fix_plan="Review scoring weights for cloud/AI factors in compute_business_score()",
       required_agents=["Root Agent", "CompanyData_Agent"]
   )
   ```

5. **Inform Root Agent**:
   - Root agent receives coordination result
   - Executes fix plan
   - Updates bug status to "RESOLVED"

## Integration with Root Agent

The AgentEvaluator is called by the root agent **after** other agents complete their work:

```
User Query → Root Agent → Sub-Agent → Results → AgentEvaluator → Validation/Bug Detection → Report/Coordinate Fix
```

## Testing Checklist

### UI Features to Test:
- [ ] Score display (API endpoint, data validity)
- [ ] Price chart (data availability, rendering)
- [ ] News section (article fetching, structure)
- [ ] Comparison feature (multiple tickers)
- [ ] Market conditions (indicators display)
- [ ] Flow data (institutional/retail data)
- [ ] Valuation metrics (P/E, P/S ratios)
- [ ] Chat interface (AI responses)

### Business Logic to Validate:
- [ ] GOOGL score >= 7.0 (cloud, AI, momentum)
- [ ] INTC score >= 6.0 (government backing, partnerships)
- [ ] NVDA score >= 8.0 (AI dominance)
- [ ] TSM score >= 8.0 (manufacturing leader)
- [ ] AMD score >= 7.0 (AI competition, growth)
- [ ] Recommendation consistency with scores
- [ ] Component score consistency

## Benefits

1. **Comprehensive Coverage**: Tests both functionality and business logic
2. **Domain Knowledge**: Uses real-world understanding to catch errors
3. **Structured Reporting**: Bugs are documented with all necessary information
4. **Fix Coordination**: Automatically coordinates with root agent for resolution
5. **Continuous Improvement**: Bug logs enable tracking and prevention

## 5. Chatbot Testing (`test_chatbot_query` and `run_chatbot_test_suite`)

**Purpose**: Comprehensive testing framework for chatbot functionality that validates query routing, answer relevance, accuracy, and data source usage.

### Test Components

1. **Routing Test**: Verifies that queries route to the correct agents
2. **Relevance Test**: Checks if answers are relevant to the query (score >= 60/100)
3. **Accuracy Test**: Cross-references answers with actual data
4. **Data Source Test**: Validates that expected data sources are used

### Example: Testing Sentiment Query

```python
test_chatbot_query(
    query="what is the sentiment for MU right now",
    expected_agents=["RedditSentiment_Agent", "Twitter_Agent"],
    expected_data_sources=["reddit", "twitter"],
    ticker="MU"
)
```

**What It Tests**:
- ✅ Routing: Should call RedditSentiment_Agent and Twitter_Agent
- ✅ Relevance: Answer should mention sentiment, MU ticker, Reddit/Twitter data
- ✅ Data Sources: Answer should reference Reddit and Twitter sources
- ✅ Accuracy: Cross-reference sentiment scores with actual data

### Test Suite

The `run_chatbot_test_suite()` function runs a comprehensive set of tests:

**Default Test Scenarios**:
1. **Sentiment Query - MU**: Tests Reddit + Twitter sentiment routing
2. **Sentiment Query - NVDA**: Tests sentiment routing for different ticker
3. **Financial Scores Query**: Tests CompanyData_Agent routing
4. **News Query**: Tests NewsSearch_Agent routing
5. **Flow Data Query**: Tests FlowData_Agent routing
6. **CEO Query**: Tests CEOLookup_Agent routing

**Test Results Structure**:
```json
{
  "total_tests": 6,
  "passed": 4,
  "failed": 1,
  "partial": 1,
  "errors": 0,
  "summary": {
    "pass_rate": 66.7,
    "average_score": 72.5
  },
  "recommendations": [
    "1 test(s) failed - review chatbot routing and answer quality"
  ]
}
```

### Chatbot Testing Checklist

- [ ] Sentiment queries route to RedditSentiment_Agent + Twitter_Agent
- [ ] Financial queries route to CompanyData_Agent
- [ ] News queries route to NewsSearch_Agent
- [ ] Flow queries route to FlowData_Agent
- [ ] CEO queries route to CEOLookup_Agent
- [ ] Answers are relevant to queries (relevance score >= 60)
- [ ] Answers use expected data sources
- [ ] Answers are accurate (cross-referenced with actual data)
- [ ] Response time is reasonable (< 10 seconds)

### Common Issues Detected

1. **Routing Failures**: Query doesn't route to expected agents
   - Example: Sentiment query doesn't call RedditSentiment_Agent
   - Fix: Review root agent routing logic

2. **Relevance Issues**: Answer doesn't address the query
   - Example: Sentiment query returns financial data
   - Fix: Improve agent response synthesis

3. **Missing Data Sources**: Answer doesn't use expected sources
   - Example: Sentiment answer doesn't mention Reddit/Twitter
   - Fix: Ensure agents properly cite data sources

4. **Accuracy Issues**: Answer contains incorrect data
   - Example: Sentiment score doesn't match actual data
   - Fix: Verify agent data retrieval and processing

## Future Enhancements

- Automated regression testing
- Performance benchmarking
- User experience validation
- A/B testing for scoring algorithms
- Integration with CI/CD pipeline
- Chatbot conversation flow testing
- Multi-turn conversation testing

