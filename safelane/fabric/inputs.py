import unicodedata
from safelane.contracts import PRPayload

MAX_DIFF_CHARS = 200_000
MAX_PATH_LENGTH = 1024

def clean_untrusted_text(value: str, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    # Strip null bytes
    value = value.replace("\x00", "")
    # Normalize unicode
    value = unicodedata.normalize("NFKC", value)
    # Cap length
    return value[:limit]

def normalize_pr_payload(raw: dict) -> PRPayload:
    pr_number = int(raw.get("pr_number", 0))
    repo = clean_untrusted_text(raw.get("repo", ""), limit=MAX_PATH_LENGTH)
    
    changed_files = raw.get("changed_files", [])
    if not isinstance(changed_files, list):
        changed_files = []
    
    clean_files = [clean_untrusted_text(f, limit=MAX_PATH_LENGTH) for f in changed_files if isinstance(f, str)]
    
    diff = clean_untrusted_text(raw.get("diff", ""), limit=MAX_DIFF_CHARS)
    
    raw_timestamp = raw.get("timestamp")
    timestamp = None
    if raw_timestamp:
        clean_ts = clean_untrusted_text(str(raw_timestamp), limit=100)
        timestamp = clean_ts if clean_ts else None
            
    head_sha = clean_untrusted_text(raw.get("head_sha", ""), limit=100)
    skip_autofix = bool(raw.get("skip_autofix", False))
    
    return PRPayload(
        pr_number=pr_number,
        repo=repo,
        changed_files=clean_files,
        diff=diff,
        timestamp=timestamp,
        head_sha=head_sha,
        skip_autofix=skip_autofix
    )
