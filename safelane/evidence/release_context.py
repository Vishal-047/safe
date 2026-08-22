import logging
from datetime import datetime, timezone, date, timedelta

from safelane.contracts import AnalysisRequest, RepoContext, EvidenceResult

logger = logging.getLogger('safelane.release_context')


def get_us_holidays(year: int) -> set[date]:
    """Calculate US federal holidays for a given year (with observed dates)."""
    holidays = set()

    def add_observed(d: date):
        if d.weekday() == 5:  # Saturday
            holidays.add(d - timedelta(days=1))
        elif d.weekday() == 6:  # Sunday
            holidays.add(d + timedelta(days=1))
        else:
            holidays.add(d)

    # Fixed date holidays
    add_observed(date(year, 1, 1))    # New Year's Day
    add_observed(date(year, 7, 4))    # Independence Day
    add_observed(date(year, 11, 11))  # Veterans Day
    add_observed(date(year, 12, 25))  # Christmas

    # N-th weekday holidays
    def get_nth_weekday(y, m, weekday, n):
        d = date(y, m, 1)
        count = 0
        while d.month == m:
            if d.weekday() == weekday:
                count += 1
                if count == n:
                    return d
            d += timedelta(days=1)
        return d

    def get_last_weekday(y, m, weekday):
        d = date(y, m + 1, 1) - timedelta(days=1) if m < 12 else date(y, 12, 31)
        while d.weekday() != weekday:
            d -= timedelta(days=1)
        return d

    holidays.add(get_nth_weekday(year, 1, 0, 3))   # MLK Day
    holidays.add(get_nth_weekday(year, 2, 0, 3))   # Presidents' Day
    holidays.add(get_last_weekday(year, 5, 0))     # Memorial Day
    holidays.add(get_nth_weekday(year, 9, 0, 1))   # Labor Day
    holidays.add(get_nth_weekday(year, 10, 0, 2))  # Columbus Day
    holidays.add(get_nth_weekday(year, 11, 3, 4))  # Thanksgiving

    return holidays


async def run(request: AnalysisRequest, repo_context: RepoContext | None = None) -> EvidenceResult:
    """
    Evaluates risk based on deployment time and day (weekends, off-hours, holidays).
    """
    dt = request.received_at or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
        
    modifier = 0
    findings = []
    
    # Day of week
    wd = dt.weekday()
    if wd == 4:  # Friday
        modifier += 15
        findings.append("Deploying on a Friday increases rollback risk")
    elif wd in (5, 6):  # Saturday - Sunday
        modifier += 25
        findings.append("Deploying on a weekend increases rollback risk")
        
    # Time of day (UTC)
    hour = dt.hour
    if 6 <= hour < 9 or 16 <= hour < 20:
        modifier += 5
        findings.append("Deploy scheduled during fringe hours (6-9 or 16-20 UTC)")
    elif 20 <= hour or hour < 6:
        modifier += 15
        findings.append("Deploy scheduled during off-hours (20-6 UTC)")
        
    # Holiday proximity
    holidays = get_us_holidays(dt.year)
    d_date = dt.date()
    
    if d_date in holidays:
        modifier += 20
        findings.append("Deploying on a US federal holiday increases rollback risk")
    elif d_date + timedelta(days=1) in holidays:
        modifier += 10
        findings.append("Deploy scheduled the day before a holiday")
        
    modifier = min(100, modifier)
    
    if modifier <= 10:
        status = "pass"
    elif modifier <= 40:
        status = "warning"
    else:
        status = "critical"
        
    return EvidenceResult(
        module="release_context",
        status=status,
        risk_score_modifier=modifier,
        findings=findings,
        recommended_action="Review deployment schedule context"
    )
