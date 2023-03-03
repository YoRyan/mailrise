"""
Tests for the YAML-based router.
"""

import apprise
import pytest

from mailrise.simple_router import _Key, _parsercpt


def test_parsercpt() -> None:
    """Tests for recipient parsing."""
    rcpt = _parsercpt('test@mailrise.xyz')
    assert rcpt.key == _Key(user='test')
    assert rcpt.notify_type == apprise.NotifyType.INFO

    rcpt = _parsercpt('test.warning@mailrise.xyz')
    assert rcpt.key == _Key(user='test')
    assert rcpt.notify_type == apprise.NotifyType.WARNING

    rcpt = _parsercpt('"with_quotes"@mailrise.xyz')
    assert rcpt.key == _Key(user='with_quotes')
    assert rcpt.notify_type == apprise.NotifyType.INFO

    rcpt = _parsercpt('"with_quotes.success"@mailrise.xyz')
    assert rcpt.key == _Key('with_quotes')
    assert rcpt.notify_type == apprise.NotifyType.SUCCESS

    rcpt = _parsercpt('"weird_quotes".success@mailrise.xyz')
    assert rcpt.key == _Key('"weird_quotes"')
    assert rcpt.notify_type == apprise.NotifyType.SUCCESS

    rcpt = _parsercpt('John Doe <johndoe.warning@mailrise.xyz>')
    assert rcpt.key == _Key('johndoe')
    assert rcpt.notify_type == apprise.NotifyType.WARNING

    with pytest.raises(ValueError):
        _parsercpt("Invalid Email <bad@>")
