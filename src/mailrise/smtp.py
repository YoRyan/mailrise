"""
This is the SMTP server functionality for Mailrise.
"""

import email.policy
import functools
import re
from asyncio import get_running_loop
from dataclasses import dataclass
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr

from mailrise.config import MailriseConfig

import apprise # type: ignore
from aiosmtpd.smtp import Envelope, Session, SMTP


class RecipientError(Exception):
    """Exception raised for invalid recipient email addresses."""
    def __init__(self, message: str) -> None:
        self.message = message


class AppriseNotifyFailure(Exception):
    """Exception raised when Apprise fails to deliver a notification."""
    pass


@dataclass
class Recipient:
    """The routing information encoded into a recipient address."""
    config_key: str
    notify_type: apprise.NotifyType


def parsercpt(addr: str) -> Recipient:
    """Parses an email address into a `Recipient`."""
    _, email = parseaddr(addr)
    rx_types = r'((?:\.(?:info|success|warning|failure))?)'
    rx = f'(?:"([^"@\\.]*){rx_types}"|([^@\\.]*){rx_types})@mailrise\\.xyz$'
    match = re.search(rx, email, re.IGNORECASE)
    if match is None:
        raise RecipientError(f"'{email}' is not a valid mailrise recipient")
    if match.group(1) is None:
        key = match.group(3)
        ntypes = match.group(4).lower()
    else:
        key = match.group(1)
        ntypes = match.group(2).lower()

    ntype = apprise.NotifyType.INFO
    if ntypes == '.info':
        pass
    elif ntypes == '.success':
        ntype = apprise.NotifyType.SUCCESS
    elif ntypes == '.warning':
        ntype = apprise.NotifyType.WARNING
    elif ntypes == '.failure':
        ntype = apprise.NotifyType.FAILURE

    return Recipient(config_key=key, notify_type=ntype)


@dataclass
class AppriseHandler:
    """The aiosmtpd handler for Mailrise. Dispatches Apprise notifications."""
    config: MailriseConfig

    async def handle_RCPT(self, server: SMTP, session: Session, envelope: Envelope,
                          address: str, rcpt_options: list[str]) -> str:
        try:
            rcpt = parsercpt(address)
        except RecipientError as e:
            return f'550 {e.message}'
        if rcpt.config_key not in self.config.configs:
            return '551 recipient does not exist in configuration file'
        self.config.logger.info('Accepted recipient: %s', address)
        envelope.rcpt_tos.append(address)
        return '250 OK'

    async def handle_DATA(self, server: SMTP, session: Session, envelope: Envelope) \
            -> str:
        assert isinstance(envelope.content, bytes)
        parser = BytesParser(policy=email.policy.default)
        message = parser.parsebytes(envelope.content)
        assert isinstance(message, EmailMessage)
        notification = parsemessage(message)
        self.config.logger.info('Accepted email, subject: %s', notification.title)

        for rcpt in (parsercpt(addr) for addr in envelope.rcpt_tos):
            try:
                await notification.submit(self.config, rcpt)
            except AppriseNotifyFailure:
                return '450 failed to send notification'
        return '250 OK'


@dataclass
class Attachment:
    """Represents an email attachment."""
    data: bytes
    suffix: str


@dataclass
class EmailNotification:
    """Represents the contents of an email message."""
    title: str
    body: str
    body_format: apprise.NotifyFormat
    attachments: list[Attachment]

    async def submit(self, config: MailriseConfig, rcpt: Recipient) -> None:
        """Turns the email into an Apprise notification and submits it."""
        apobj = apprise.Apprise()
        apobj.add(config.configs[rcpt.config_key])
        notify = functools.partial(
            apobj.notify,
            title=self.title,
            body=self.body,
            body_format=self.body_format,
            notify_type=rcpt.notify_type
        )
        res = await get_running_loop().run_in_executor(None, notify)
        if not res:
            raise AppriseNotifyFailure()


def parsemessage(msg: EmailMessage) -> EmailNotification:
    """Parses an email message into an `EmailNotification`."""
    title = msg.get('Subject', '(no subject)')
    attachments = [_parseattachment(part) for part in msg.iter_attachments()
                   if isinstance(part, EmailMessage)]
    body_part = msg.get_body()
    if body_part is None:
        return EmailNotification(
            title=title,
            body='',
            body_format=apprise.NotifyFormat.TEXT,
            attachments=attachments
        )
    else:
        assert isinstance(body_part, EmailMessage)
        body = body_part.get_content().strip()
        body_format = \
            (apprise.NotifyFormat.HTML if body_part.get_content_subtype() == 'html'
             else apprise.NotifyFormat.TEXT)
        return EmailNotification(
            title=title,
            body=body,
            body_format=body_format,
            attachments=attachments
        )


def _parseattachment(part: EmailMessage) -> Attachment:
    filename = part.get_filename('')
    match = re.search(r'(\..*)?$', filename)
    assert match is not None
    return Attachment(data=part.get_content(), suffix=match.group(1) or '')
