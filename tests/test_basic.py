import pytest

def test_basic_math():
    """A simple test to ensure the pytest framework is working."""
    assert 1 + 1 == 2

def test_security_score_thresholds():
    """Test standard security scoring thresholds."""
    def score_to_decision(phishing_risk: int) -> str:
        if phishing_risk >= 80:
            return "PHISHING"
        elif phishing_risk >= 40:
            return "QUARANTINE"
        else:
            return "ALLOW"
            
    assert score_to_decision(15) == "ALLOW"
    assert score_to_decision(55) == "QUARANTINE"
    assert score_to_decision(85) == "PHISHING"
