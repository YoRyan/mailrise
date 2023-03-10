"""
Tests for the YAML-based router.
"""

import apprise
import pytest
from logging import Logger
from string import Template
from email.message import EmailMessage as StdlibEmailMessage

from mailrise.router import EmailMessage, AppriseNotification
from mailrise.simple_router import _Key, _parsercpt, SimpleRouter, _SimpleSender

pytest_plugins = ('pytest_asyncio',)


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
async def test_body_template_substitutions():
    logger = Logger(name='TestLogger')
    router = SimpleRouter([(
        _Key(user='test', domain='test.test'),
        _SimpleSender(
            config_yaml="",
            title_template=Template("$subject"),
            body_template=Template("hello $body"),
            body_format=apprise.NotifyFormat.TEXT,
            body_pattern=None
        ))])

    email = EmailMessage(
        email_message=StdlibEmailMessage(),
        subject="Test",
        from_="test@test.test",
        to=["test@test.test"],
        body="world",
        body_format=apprise.NotifyFormat.TEXT,
        attachments=[]
    )

    expected = [AppriseNotification(
        config="",
        title="Test",
        body="hello world",
        body_format=apprise.NotifyFormat.TEXT,
        config_format='yaml'
    )]
    actual = [data async for data in router.email_to_apprise(logger=logger, email=email)]

    assert actual == expected


@pytest.mark.asyncio
async def test_title_template_substitutions():
    logger = Logger(name='TestLogger')
    router = SimpleRouter([(
        _Key(user='test', domain='test.test'),
        _SimpleSender(
            config_yaml="",
            title_template=Template("hello $subject"),
            body_template=Template("$body"),
            body_format=apprise.NotifyFormat.TEXT,
            body_pattern=None
        ))])

    email = EmailMessage(
        email_message=StdlibEmailMessage(),
        subject="world",
        from_="test@test.test",
        to=["test@test.test"],
        body="test",
        body_format=apprise.NotifyFormat.TEXT,
        attachments=[]
    )

    expected = [AppriseNotification(
        config="",
        title="hello world",
        body="test",
        body_format=apprise.NotifyFormat.TEXT,
        config_format='yaml'
    )]
    actual = [data async for data in router.email_to_apprise(logger=logger, email=email)]

    assert actual == expected


@pytest.mark.asyncio
async def test_body_patterns():
    logger = Logger(name='TestLogger')
    router = SimpleRouter([(
        _Key(user='test', domain='test.test'),
        _SimpleSender(
            config_yaml="",
            title_template=Template("$subject"),
            body_template=Template("$body its me!"),
            body_format=apprise.NotifyFormat.TEXT,
            body_pattern=r"(?<=<p>).+?(?=<\/p>)"
        ))])

    email = EmailMessage(
        email_message=StdlibEmailMessage(),
        subject="Test",
        from_="test@test.test",
        to=["test@test.test"],
        body="<html><h1>Ignore me</h1><p>hello world</p></html>",
        body_format=apprise.NotifyFormat.TEXT,
        attachments=[]
    )

    expected = [AppriseNotification(
        config="",
        title="Test",
        body="hello world its me!",
        body_format=apprise.NotifyFormat.TEXT,
        config_format='yaml'
    )]
    actual = [data async for data in router.email_to_apprise(logger=logger, email=email)]

    assert actual == expected
