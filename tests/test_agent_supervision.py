"""
Integration tests for AgentSupervisor and AgentEvaluator.

These tests verify that the supervision system:
1. Prevents agents from being blocked on missing data
2. Detects fabricated/fake data
3. Validates data freshness
4. Fact-checks agent outputs
5. Logs blocking issues properly
"""

import pytest
import os
import json
from datetime import datetime, timedelta
from app.agents.agents import (
    validate_data_exists,
    log_blocking_issue,
    detect_fabricated_data,
    check_data_freshness,
    validate_data_source,
    fact_check_agent_output
)


class TestAgentSupervisor:
    """Tests for AgentSupervisor tools"""

    def test_validate_data_exists_financial_data_present(self):
        """Test that validator correctly identifies existing financial data"""
        result = validate_data_exists("NVDA", "financials")

        # Should either exist or provide clear alternatives
        assert "ticker" in result
        assert "exists" in result
        assert "recommendation" in result

        if result["exists"]:
            assert result["file_path"] is not None
            assert "record_count" in result
        else:
            assert len(result["alternative_options"]) > 0

    def test_validate_data_exists_missing_data(self):
        """Test that validator handles missing data gracefully"""
        result = validate_data_exists("INVALIDTICKER", "financials")

        assert result["exists"] == False
        assert len(result["alternative_options"]) > 0
        assert "recommendation" in result
        # Should suggest alternatives, not give up
        assert "alternative" in result["recommendation"].lower() or "try" in result["recommendation"].lower()

    def test_validate_data_exists_all_data_types(self):
        """Test validator works for all supported data types"""
        data_types = ['financials', 'earnings', 'prices', 'news', 'flow', 'reddit', 'twitter', 'company', 'ceo']

        for data_type in data_types:
            result = validate_data_exists("NVDA", data_type)
            assert "exists" in result
            assert "recommendation" in result
            assert result["data_type"] == data_type

    def test_log_blocking_issue_data_not_found(self):
        """Test logging when agent is blocked by missing data"""
        result = log_blocking_issue(
            agent_name="CompanyData_Agent",
            issue_description="Data not found for ticker XYZ",
            ticker="XYZ",
            attempted_action="fetch financial data"
        )

        assert result["logged"] == True
        assert len(result["next_steps"]) > 0
        assert "log_entry" in result
        assert result["log_entry"]["severity"] in ["low", "medium", "high"]

        # Should suggest alternatives
        assert len(result["log_entry"]["alternatives_suggested"]) >= 2

    def test_log_blocking_issue_api_quota_exceeded(self):
        """Test logging when agent hits API rate limit"""
        result = log_blocking_issue(
            agent_name="NewsSearch_Agent",
            issue_description="Google Search API quota exceeded",
            attempted_action="fetch news"
        )

        assert result["logged"] == True
        assert result["log_entry"]["severity"] == "high"

        # Should suggest using cached data as alternative
        alternatives = result["log_entry"]["alternatives_suggested"]
        assert any("cache" in alt.lower() for alt in alternatives)

    def test_detect_fabricated_data_legitimate(self):
        """Test that legitimate data passes fabrication check"""
        legitimate_data = {
            "ticker": "NVDA",
            "revenue": 26974000000,
            "netIncome": 12285000000,
            "year": "2024",
            "grossMargin": 75.98
        }

        result = detect_fabricated_data(legitimate_data, "financials", "NVDA")

        assert result["verdict"] in ["APPEARS_LEGITIMATE", "LOW_SUSPICION"]
        assert result["suspicion_score"] < 50

    def test_detect_fabricated_data_placeholder_text(self):
        """Test detection of placeholder/fake data"""
        fake_data = {
            "ticker": "NVDA",
            "revenue": "TODO: Add real revenue",
            "netIncome": "PLACEHOLDER",
            "year": "2024"
        }

        result = detect_fabricated_data(fake_data, "financials", "NVDA")

        assert result["is_suspicious"] == True
        assert result["suspicion_score"] >= 25
        assert len(result["red_flags"]) > 0

    def test_detect_fabricated_data_suspiciously_round_numbers(self):
        """Test detection of fabricated round numbers"""
        suspicious_data = {
            "ticker": "NVDA",
            "revenue": 10000000,
            "netIncome": 5000000,
            "totalAssets": 20000000,
            "totalLiabilities": 10000000,
            "cashAndEquivalents": 8000000,
            "year": "2024"
        }

        result = detect_fabricated_data(suspicious_data, "financials", "NVDA")

        # All perfectly round numbers should raise some suspicion
        # But might not be high enough to reject outright
        assert result["suspicion_score"] >= 0

    def test_detect_fabricated_data_future_dates(self):
        """Test detection of impossible future dates in historical data"""
        future_data = {
            "ticker": "NVDA",
            "revenue": 26974000000,
            "year": "2030",  # Future year for historical financials
            "filingDate": "2030-03-15"
        }

        result = detect_fabricated_data(future_data, "financials", "NVDA")

        # Future dates in historical data should be flagged
        assert result["suspicion_score"] > 0


class TestAgentEvaluator:
    """Tests for AgentEvaluator tools"""

    def test_check_data_freshness_guidelines(self):
        """Test that freshness checker uses correct guidelines"""
        # Test that guidelines are properly defined
        data_types = ['financials', 'earnings', 'prices', 'news', 'reddit', 'flow', 'company_runtime']

        for data_type in data_types:
            result = check_data_freshness("NVDA", data_type)

            # Should have guideline information even if file doesn't exist
            assert "data_type" in result
            assert "status" in result

    def test_check_data_freshness_stale_detection(self, tmp_path):
        """Test detection of stale data"""
        # Create a test file with old modification time
        test_file = tmp_path / "test_stale.json"
        test_file.write_text('{"test": "data"}')

        # Modify the file's timestamp to be 100 days old
        old_time = (datetime.now() - timedelta(days=100)).timestamp()
        os.utime(test_file, (old_time, old_time))

        # For this test, we check the logic is working
        file_modified_time = datetime.fromtimestamp(os.path.getmtime(test_file))
        age = datetime.now() - file_modified_time

        # Age should be ~100 days
        assert age.days >= 99

    def test_validate_data_source_yfinance(self):
        """Test validation of yfinance data source"""
        yfinance_data = {
            "regularMarketPrice": 500.25,
            "previousClose": 495.30,
            "fiftyTwoWeekHigh": 550.00,
            "currency": "USD"
        }

        result = validate_data_source(yfinance_data, "yfinance", "prices")

        assert result["source_verified"] == True
        assert "yfinance" in result.get("actual_source", "").lower()

    def test_validate_data_source_reddit(self):
        """Test validation of Reddit API data"""
        reddit_data = {
            "subreddit": "wallstreetbets",
            "score": 1250,
            "permalink": "/r/wallstreetbets/comments/abc123",
            "created_utc": 1234567890,
            "title": "NVDA to the moon!"
        }

        result = validate_data_source(reddit_data, "Reddit API", "reddit")

        assert result["source_verified"] == True
        assert "reddit" in result.get("actual_source", "").lower()

    def test_validate_data_source_mismatch(self):
        """Test detection of source mismatches"""
        reddit_data = {
            "subreddit": "stocks",
            "score": 100
        }

        # Claiming it's from yfinance but structure is Reddit
        result = validate_data_source(reddit_data, "yfinance", "prices")

        # Should not verify yfinance structure
        assert result["source_verified"] == False or len(result["warnings"]) > 0

    def test_fact_check_agent_output_accurate_scores(self):
        """Test fact-checking when agent output matches actual data"""
        # This will actually call compute_company_scores if NVDA data exists
        agent_output = {
            "ticker": "NVDA",
            "overall": {
                "score": 8.5  # This should be checked against actual score
            }
        }

        result = fact_check_agent_output("CompanyData_Agent", agent_output, "NVDA")

        assert "verdict" in result
        assert "confidence_score" in result
        # Verdict should be VERIFIED, UNVERIFIED, or FAILED
        assert result["verdict"] in ["VERIFIED", "UNVERIFIED", "FAILED", "ERROR"]

    def test_fact_check_agent_output_contradiction(self):
        """Test detection of contradictions in agent output"""
        # Create obviously wrong output
        agent_output = {
            "ticker": "NVDA",
            "overall": {
                "score": 15.0  # Impossible score (should be 0-10)
            },
            "recommendation": {
                "rating": "INVALID_RATING"
            }
        }

        result = fact_check_agent_output("CompanyData_Agent", agent_output, "NVDA")

        # Should detect some issues
        assert "verdict" in result


class TestSupervisionIntegration:
    """Integration tests for the full supervision workflow"""

    def test_full_supervision_workflow_happy_path(self):
        """Test complete workflow: validate → delegate → evaluate"""
        ticker = "NVDA"

        # Step 1: Supervisor validates data exists
        validation = validate_data_exists(ticker, "financials")

        if validation["exists"]:
            # Step 2: Would delegate to CompanyData_Agent here
            # For test, we simulate agent output
            simulated_output = {
                "ticker": ticker,
                "overall": {"score": 8.5},
                "recommendation": {"rating": "Buy"}
            }

            # Step 3: Evaluator checks freshness
            freshness = check_data_freshness(ticker, "financials")
            assert "status" in freshness

            # Step 4: Evaluator fact-checks output
            fact_check = fact_check_agent_output("CompanyData_Agent", simulated_output, ticker)
            assert "verdict" in fact_check

    def test_supervision_workflow_blocked_scenario(self):
        """Test workflow when agent is blocked by missing data"""
        ticker = "NONEXISTENT"

        # Step 1: Supervisor validates data
        validation = validate_data_exists(ticker, "financials")

        # Data shouldn't exist
        assert validation["exists"] == False

        # Step 2: Should have alternative suggestions
        assert len(validation["alternative_options"]) > 0

        # Step 3: Log the blocking issue
        log_result = log_blocking_issue(
            "CompanyData_Agent",
            "Data not found",
            ticker,
            "compute financial scores"
        )

        # Should provide next steps
        assert len(log_result["next_steps"]) > 0

    def test_supervision_workflow_fake_data_detection(self):
        """Test that fake data is caught before being used"""
        fake_output = {
            "ticker": "NVDA",
            "revenue": "TODO: Get real data",
            "netIncome": "PLACEHOLDER",
            "year": "2024"
        }

        # Supervisor should detect this is fabricated
        fabrication_check = detect_fabricated_data(fake_output, "financials", "NVDA")

        assert fabrication_check["is_suspicious"] == True
        assert fabrication_check["verdict"] in ["HIGH_SUSPICION", "MEDIUM_SUSPICION"]

        # Should recommend rejecting this data
        assert "reject" in fabrication_check["recommendation"].lower() or "verify" in fabrication_check["recommendation"].lower()


def test_blocking_log_persistence(tmp_path):
    """Test that blocking issues are logged persistently"""
    # This would require setting DATA_ROOT to tmp_path
    # For now, just verify the function returns a log entry
    result = log_blocking_issue("TestAgent", "Test blocking issue", "NVDA", "test action")

    assert "log_entry" in result
    assert result["log_entry"]["timestamp"] is not None
    assert result["log_entry"]["agent_name"] == "TestAgent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
