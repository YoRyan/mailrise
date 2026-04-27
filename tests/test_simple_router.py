"""
Tests for the YAML-based router.
"""

from email.message import EmailMessage as StdlibEmailMessage
import logging

import apprise
import pytest

from mailrise.router import EmailMessage
from mailrise.simple_router import _Key, _parsercpt, load_from_yaml


_logger = logging.getLogger(__name__)


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


@pytest.mark.asyncio
async def test_direct_config_routes_by_recipient() -> None:
    """Tests that legacy direct configs still match the recipient address."""
    router = load_from_yaml(_logger, {
        'alerts': {
            'urls': ['json://localhost']
        }
    })
    email = _make_email(
        from_='sender@example.com',
        to=['alerts@mailrise.xyz'],
    )

    notifications = [
        notification async for notification
        in router.email_to_apprise(_logger, email, auth_data=None)
    ]

    assert len(notifications) == 1
    assert notifications[0].title == 'Subject (sender@example.com)'


@pytest.mark.asyncio
async def test_nested_config_routes_by_sender_and_recipient() -> None:
    """Tests that nested configs match both sender and recipient addresses."""
    router = load_from_yaml(_logger, {
        'sender@example.com': {
            'alerts@example.net': {
                'urls': ['json://localhost']
            }
        }
    })
    matching_email = _make_email(
        from_='sender@example.com',
        to=['alerts@example.net'],
    )
    other_sender_email = _make_email(
        from_='other@example.com',
        to=['alerts@example.net'],
    )

    matching = [
        notification async for notification
        in router.email_to_apprise(_logger, matching_email, auth_data=None)
    ]
    other_sender = [
        notification async for notification
        in router.email_to_apprise(_logger, other_sender_email, auth_data=None)
    ]

    assert len(matching) == 1
    assert len(other_sender) == 0


@pytest.mark.asyncio
async def test_email_to_apprise_handles_multiple_recipients() -> None:
    """Tests that one email can produce notifications for multiple recipients."""
    router = load_from_yaml(_logger, {
        'alerts': {
            'urls': ['json://localhost']
        },
        'ops': {
            'urls': ['json://localhost']
        }
    })
    email = _make_email(
        from_='sender@example.com',
        to=['alerts@mailrise.xyz', 'ops@mailrise.xyz'],
    )

    notifications = [
        notification async for notification
        in router.email_to_apprise(_logger, email, auth_data=None)
    ]

    assert len(notifications) == 2
    assert [notification.body for notification in notifications] == ['Body', 'Body']


def _make_email(from_: str, to: list[str]) -> EmailMessage:
    return EmailMessage(
        email_message=StdlibEmailMessage(),
        subject='Subject',
        from_=from_,
        to=to,
        body='Body',
        body_format=apprise.NotifyFormat.TEXT,
        attachments=[]
    )
