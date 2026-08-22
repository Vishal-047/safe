import pytest
from datetime import datetime, timezone, timedelta
from safelane.contracts import AnalysisRequest
from safelane.evidence.release_context import run


@pytest.mark.unit
async def test_tuesday_10am_utc_pass():
    dt = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc) # Tuesday
    req = AnalysisRequest(pr_number=1, repository="test/testrepo", received_at=dt)
    
    result = await run(req)
        
    assert result.status == "pass"
    assert result.risk_score_modifier == 0
    assert not result.findings


@pytest.mark.unit
async def test_friday_5pm_utc_warning():
    # 5pm UTC = 17:00
    dt = datetime(2026, 8, 21, 17, 0, tzinfo=timezone.utc) # Friday
    req = AnalysisRequest(pr_number=1, repository="test/testrepo", received_at=dt)
    
    result = await run(req)
        
    assert result.status == "warning"
    # Friday (+15) + Fringe Hours (+5) = 20
    assert result.risk_score_modifier == 20
    assert any("Friday" in f for f in result.findings)
    assert any("fringe hours" in f for f in result.findings)


@pytest.mark.unit
async def test_saturday_critical():
    dt = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc) # Saturday
    req = AnalysisRequest(pr_number=1, repository="test/testrepo", received_at=dt)
    
    result = await run(req)
        
    assert result.status == "warning" or result.status == "critical"
    # Sat (+25) = 25 -> warning
    assert result.risk_score_modifier == 25


@pytest.mark.unit
async def test_christmas_day():
    dt = datetime(2026, 12, 25, 12, 0, tzinfo=timezone.utc) # Christmas Day
    req = AnalysisRequest(pr_number=1, repository="test/testrepo", received_at=dt)
    
    result = await run(req)
        
    # Christmas (+20), Friday (+15) = 35 -> warning
    assert result.status == "warning"
    assert result.risk_score_modifier == 35
    assert any("holiday" in f for f in result.findings)


@pytest.mark.unit
async def test_day_before_holiday():
    dt = datetime(2026, 12, 24, 12, 0, tzinfo=timezone.utc) # Thursday
    req = AnalysisRequest(pr_number=1, repository="test/testrepo", received_at=dt)
    
    result = await run(req)
        
    assert result.status == "warning" or result.status == "pass"
    # Day before (+10) -> 10 -> pass
    assert result.risk_score_modifier == 10
    assert any("before a holiday" in f for f in result.findings)


@pytest.mark.unit
async def test_none_timestamp():
    req = AnalysisRequest(pr_number=1, repository="test/testrepo", received_at=None)
    result = await run(req)
    # Default to now(), shouldn't error out
    assert result.risk_score_modifier >= 0


@pytest.mark.unit
async def test_naive_datetime():
    dt = datetime(2026, 8, 18, 10, 0) # Naive
    req = AnalysisRequest(pr_number=1, repository="test/testrepo", received_at=dt)
    
    result = await run(req)
    assert result.status == "pass"
