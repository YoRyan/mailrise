"""
Tests for the SMTP server functionality.
"""

from email.message import EmailMessage
from pathlib import Path

import apprise
import pytest

from mailrise.config import Key
from mailrise.smtp import RecipientError, parsemessage, parsercpt


def test_parsercpt() -> None:
    """Tests for recipient parsing."""
    rcpt = parsercpt('test@mailrise.xyz')
    assert rcpt.key == Key(user='test')
    assert rcpt.notify_type == apprise.NotifyType.INFO

    rcpt = parsercpt('test.warning@mailrise.xyz')
    assert rcpt.key == Key(user='test')
    assert rcpt.notify_type == apprise.NotifyType.WARNING

    rcpt = parsercpt('"with_quotes"@mailrise.xyz')
    assert rcpt.key == Key(user='with_quotes')
    assert rcpt.notify_type == apprise.NotifyType.INFO

    rcpt = parsercpt('"with_quotes.success"@mailrise.xyz')
    assert rcpt.key == Key('with_quotes')
    assert rcpt.notify_type == apprise.NotifyType.SUCCESS

    rcpt = parsercpt('"weird_quotes".success@mailrise.xyz')
    assert rcpt.key == Key('"weird_quotes"')
    assert rcpt.notify_type == apprise.NotifyType.SUCCESS

    rcpt = parsercpt('John Doe <johndoe.warning@mailrise.xyz>')
    assert rcpt.key == Key('johndoe')
    assert rcpt.notify_type == apprise.NotifyType.WARNING

    with pytest.raises(RecipientError):
        parsercpt("Invalid Email <bad@>")


def test_parsemessage() -> None:
    """Tests for email message parsing."""
    msg = EmailMessage()
    msg.set_content('Hello, World!')
    msg['From'] = ''
    msg['Subject'] = 'Test Message'
    notification = parsemessage(msg)
    assert notification.subject == 'Test Message'
    assert notification.body == 'Hello, World!'
    assert notification.body_format == apprise.NotifyFormat.TEXT

    msg = EmailMessage()
    msg.set_content('Hello, World!')
    msg.add_alternative('Hello, <strong>World!</strong>', subtype='html')
    notification = parsemessage(msg)
    assert notification.subject == '[no subject]'
    assert notification.from_ == '[no sender]'
    assert notification.body == 'Hello, <strong>World!</strong>'
    assert notification.body_format == apprise.NotifyFormat.HTML


def test_multipart() -> None:
    """Tests for email message parsing with multipart components."""
    img_name = 'bridge.jpg'
    with open(Path(__file__).parent/img_name, 'rb') as file:
        img_data = file.read()
    msg = EmailMessage()
    msg.add_related('Hello, World!')
    msg.add_related(img_data, maintype='image', subtype='jpeg')
    msg['From'] = ''
    msg['Subject'] = 'Test Message'
    notification = parsemessage(msg)
    assert notification.subject == 'Test Message'
    assert notification.body == 'Hello, World!'
    assert notification.body_format == apprise.NotifyFormat.TEXT

    msg = EmailMessage()
    msg.add_alternative('Hello, World!', subtype='plain')
    msg.add_alternative('<strong>Hello, World!</strong>', subtype='html')
    msg['From'] = ''
    msg['Subject'] = 'Test Message'
    notification = parsemessage(msg)
    assert notification.subject == 'Test Message'
    assert notification.body == '<strong>Hello, World!</strong>'
    assert notification.body_format == apprise.NotifyFormat.HTML


def test_parseattachments() -> None:
    """Tests for email message parsing with attachments."""
    img_name = 'bridge.jpg'
    with open(Path(__file__).parent/img_name, 'rb') as file:
        img_data = file.read()

    msg = EmailMessage()
    msg.set_content('Hello, World!')
    msg['From'] = 'sender@example.com'
    msg['Subject'] = 'Now With Images'
    msg.add_attachment(
        img_data,
        maintype='image',
        subtype='jpeg',
        filename=img_name
    )
    notification = parsemessage(msg)
    assert notification.subject == 'Now With Images'
    assert notification.from_ == 'sender@example.com'
    assert notification.body == 'Hello, World!'
    assert notification.body_format == apprise.NotifyFormat.TEXT
    assert len(notification.attachments) == 1
    assert notification.attachments[0].data == img_data
    assert notification.attachments[0].filename == img_name

    msg = EmailMessage()
    msg.set_content('Hello, World!')
    msg['From'] = 'sender@example.com'
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
    assert notification.subject == 'Now With Images'
    assert notification.from_ == 'sender@example.com'
    assert notification.body == 'Hello, World!'
    assert notification.body_format == apprise.NotifyFormat.TEXT
    assert len(notification.attachments) == 2
    for attach in notification.attachments:
        assert attach.data == img_data
    assert notification.attachments[0].filename == f'1_{img_name}'
    assert notification.attachments[1].filename == f'2_{img_name}'
