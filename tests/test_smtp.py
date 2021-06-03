from email.message import EmailMessage

from mailrise.smtp import RecipientError, parsemessage, parsercpt

import apprise # type: ignore
import pytest


def test_parsercpt() -> None:
    """Tests for recipient parsing."""
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


def test_parsemessage() -> None:
    """Tests for email message parsing."""
    msg = EmailMessage()
    msg.set_content('Hello, World!')
    msg['Subject'] = 'Test Message'
    notification = parsemessage(msg)
    assert notification.title == 'Test Message'
    assert notification.body == 'Hello, World!'
    assert notification.body_format == apprise.NotifyFormat.TEXT

    msg = EmailMessage()
    msg.set_content('Hello, World!')
    msg.add_alternative('Hello, <strong>World!</strong>', subtype='html')
    notification = parsemessage(msg)
    assert notification.title == '(no subject)'
    assert notification.body == 'Hello, <strong>World!</strong>'
    assert notification.body_format == apprise.NotifyFormat.HTML
