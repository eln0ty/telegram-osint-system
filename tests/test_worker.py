from datetime import datetime, timezone

from code.worker import MessageWorker


def test_parse_datetime_handles_none() -> None:
    worker = object.__new__(MessageWorker)
    parsed = worker._parse_datetime(None)
    assert isinstance(parsed, datetime)
    assert parsed.tzinfo == timezone.utc
