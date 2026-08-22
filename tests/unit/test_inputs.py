import pytest
from safelane.fabric.inputs import clean_untrusted_text, normalize_pr_payload, MAX_DIFF_CHARS, MAX_PATH_LENGTH

@pytest.mark.unit
def test_clean_untrusted_text_strips_null_bytes():
    raw = "hello\x00world"
    assert clean_untrusted_text(raw, 100) == "helloworld"

@pytest.mark.unit
def test_clean_untrusted_text_caps_length():
    raw = "a" * 100
    assert clean_untrusted_text(raw, 50) == "a" * 50

@pytest.mark.unit
def test_clean_untrusted_text_normalizes_unicode():
    raw = "ﬁ"  # Ligature fi
    assert clean_untrusted_text(raw, 10) == "fi"

@pytest.mark.unit
def test_normalize_pr_payload_caps_diff():
    large_diff = "a" * (MAX_DIFF_CHARS + 100)
    raw = {
        "pr_number": 1,
        "repo": "owner/repo",
        "changed_files": ["file.txt"],
        "diff": large_diff
    }
    payload = normalize_pr_payload(raw)
    assert len(payload.diff) == MAX_DIFF_CHARS

@pytest.mark.unit
def test_normalize_pr_payload_bounds_path_length():
    long_path = "a" * (MAX_PATH_LENGTH + 100)
    raw = {
        "pr_number": 1,
        "repo": "owner/repo",
        "changed_files": [long_path]
    }
    payload = normalize_pr_payload(raw)
    assert len(payload.changed_files[0]) == MAX_PATH_LENGTH

@pytest.mark.unit
def test_normalize_pr_payload_handles_empty_inputs():
    payload = normalize_pr_payload({})
    assert payload.pr_number == 0
    assert payload.repo == ""
    assert payload.changed_files == []
    assert payload.diff == ""
