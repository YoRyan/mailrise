from mailrise.smtp import RecipientError, parsercpt

import apprise # type: ignore
import pytest


def test_parsercpt() -> None:
    """Tests for :fun:`parsercpt`."""
    rcpt = parsercpt('test@mailrise.xyz')
    assert rcpt.config_key == 'test'
    assert rcpt.notify_type == apprise.NotifyType.INFO

    rcpt = parsercpt('test.warning@mailrise.xyz')
    assert rcpt.config_key == 'test'
    assert rcpt.notify_type == apprise.NotifyType.WARNING

    rcpt = parsercpt('"with_quotes"@mailrise.xyz')
    assert rcpt.config_key == 'with_quotes'
    assert rcpt.notify_type == apprise.NotifyType.INFO

    rcpt = parsercpt('"with_quotes.success"@mailrise.xyz')
    assert rcpt.config_key == 'with_quotes'
    assert rcpt.notify_type == apprise.NotifyType.SUCCESS

    rcpt = parsercpt('"weird_quotes".success@mailrise.xyz')
    assert rcpt.config_key == '"weird_quotes"'
    assert rcpt.notify_type == apprise.NotifyType.SUCCESS

    rcpt = parsercpt('John Doe <johndoe.warning@mailrise.xyz>')
    assert rcpt.config_key == 'johndoe'
    assert rcpt.notify_type == apprise.NotifyType.WARNING

    with pytest.raises(RecipientError):
        parsercpt("Ryan Young <ryan@youngryan.com>")
