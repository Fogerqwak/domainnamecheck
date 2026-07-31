"""Runnable self-check for scanner.py's pure logic. python test_scanner.py"""

from scanner import DomainStatus, classify_status


def test_classify_status() -> None:
    assert classify_status(404) is DomainStatus.AVAILABLE
    assert classify_status(200) is DomainStatus.TAKEN
    assert classify_status(429) is None
    assert classify_status(500) is None
    assert classify_status(503) is None
    assert classify_status(400) is DomainStatus.TAKEN


if __name__ == "__main__":
    test_classify_status()
    print("OK")
