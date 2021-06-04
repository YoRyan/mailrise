from email.message import EmailMessage
from pathlib import Path

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


def test_parseattachments() -> None:
    """Tests for email message parsing with attachments."""
    img_name = 'bridge.jpg'
    with open(Path(__file__).parent/img_name, 'rb') as fp:
        img_data = fp.read()

    msg = EmailMessage()
    msg.set_content('Hello, World!')
    msg['Subject'] = 'Now With Images'
    msg.add_attachment(
        img_data,
        maintype='image',
        subtype='jpeg',
        filename=img_name
    )
    notification = parsemessage(msg)
    assert notification.title == 'Now With Images'
    assert notification.body == 'Hello, World!'
    assert notification.body_format == apprise.NotifyFormat.TEXT
    assert len(notification.attachments) == 1
    assert notification.attachments[0].data == img_data
    assert notification.attachments[0].filename == img_name

    msg = EmailMessage()
    msg.set_content('Hello, World!')
    msg['Subject'] = 'Now With Images'
    msg.add_attachment(
        img_data,
        maintype='image',
        subtype='jpeg',
        filename=f'1_{img_name}'
    )
    msg.add_attachment(
        img_data,
        maintype='image',
        subtype='jpeg',
        filename=f'2_{img_name}'
    )
    notification = parsemessage(msg)
    assert notification.title == 'Now With Images'
    assert notification.body == 'Hello, World!'
    assert notification.body_format == apprise.NotifyFormat.TEXT
    assert len(notification.attachments) == 2
    for attach in notification.attachments:
        assert attach.data == img_data
    assert notification.attachments[0].filename == f'1_{img_name}'
    assert notification.attachments[1].filename == f'2_{img_name}'
