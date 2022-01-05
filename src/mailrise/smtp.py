"""
This is the SMTP server functionality for Mailrise.
"""

from __future__ import annotations

import asyncio
import email.policy
import os
import re
import typing as typ
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr
from tempfile import NamedTemporaryFile

from mailrise.config import Key, MailriseConfig
from mailrise.util import parseaddrparts

import apprise
from aiosmtpd.smtp import Envelope, Session, SMTP
from apprise.common import ContentLocation

from html.parser import HTMLParser
from os import linesep

# Mypy, for some reason, considers AttachBase a module, not a class.
MYPY = False
if MYPY:
    from apprise.attachment.AttachBase import AttachBase
else:
    from apprise.attachment import AttachBase


class RecipientError(Exception):
    """Exception raised for invalid recipient email addresses.

    Attributes:
        message: The reason the recipient is invalid.
    """
    message: str

    def __init__(self, message: str) -> None:
        self.message = message


class AppriseNotifyFailure(Exception):
    """Exception raised when Apprise fails to deliver a notification.

    Note: Apprise does not provide any information about the reason for the
    failure."""
    pass


class BodyConversionError(Exception):
    """Exception raised for a failed body conversion.

    Attributes:
        message: The reason the conversion failed.
    """
    message: str

    def __init__(self, message: str) -> None:
        self.message = message


class Recipient(typ.NamedTuple):
    """The routing information encoded into a recipient address.

    Attributes:
        key: An index into the dictionary of senders.
        notify_type: The type of notification to send.
    """
    key: Key
    notify_type: apprise.NotifyType


def parsercpt(addr: str) -> Recipient:
    """Parses an email address into a `Recipient`.

    Args:
        addr: The email address to parse.

    Returns:
        The `Recipient` instance.
    """
    _, email = parseaddr(addr)
    user, domain = parseaddrparts(email)
    if not user or not domain:
        raise RecipientError(f"'{email}' is not a valid mailrise recipient")
    match = re.search(
        r'(.*)\.(info|success|warning|failure)$', user, re.IGNORECASE)
    ntype = apprise.NotifyType.INFO
    if match is not None:
        user = match.group(1)
        ntypes = match.group(2)
        if ntypes == 'info':
            pass
        elif ntypes == 'success':
            ntype = apprise.NotifyType.SUCCESS
        elif ntypes == 'warning':
            ntype = apprise.NotifyType.WARNING
        elif ntypes == 'failure':
            ntype = apprise.NotifyType.FAILURE
    return Recipient(key=Key(user=user, domain=domain.lower()), notify_type=ntype)


class AppriseHandler(typ.NamedTuple):
    """The aiosmtpd handler for Mailrise. Dispatches Apprise notifications.

    Attributes:
        config: This server's Mailrise configuration.
    """
    config: MailriseConfig

    async def handle_RCPT(self, server: SMTP, session: Session, envelope: Envelope,
                          address: str, rcpt_options: list[str]) -> str:
        try:
            rcpt = parsercpt(address)
        except RecipientError as e:
            return f'550 {e.message}'
        if rcpt.key not in self.config.senders:
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
        notification = parsemessage(
            message,
            html_conversion=self.config.senders[parsercpt(message.get('To', '[no To]')).key].html_conversion,
        )
        self.config.logger.info('Accepted email, subject: %s', notification.subject)

        rcpts = (parsercpt(addr) for addr in envelope.rcpt_tos)
        aws = (notification.submit(self.config, rcpt) for rcpt in rcpts)
        try:
            await asyncio.gather(*aws)
        except AppriseNotifyFailure:
            return '450 failed to send notification'
        return '250 OK'


class Attachment(typ.NamedTuple):
    """Represents an email attachment.

    Attributes:
        data: The contents of the attachment.
        filename: The filename of the attachment as it was set by the sender.
    """
    data: bytes
    filename: str


class ConvertingBody(typ.NamedTuple):
    """Represents a converting body message.

    Attributes:
        body: The original body message.
        html_conversion: The conversion option.
    """
    body: str
    html_conversion: str


class ConvertedBody(typ.NamedTuple):
    """Represents a converted body message.

    Attributes:
        converted_body: The converted body message from the selected conversion option.
    """
    converted_body: str


class EmailNotification(typ.NamedTuple):
    """Represents an email accepted for notifying.

    Attributes:
        subject: The email subject.
        from_: The email sender address.
        body: The contents of the email.
        body_format: The type of the contents of the email.
        attachments: The email attachments.
    """
    subject: str
    from_: str
    body: str
    body_format: apprise.NotifyFormat
    attachments: list[Attachment]

    async def submit(self, config: MailriseConfig, rcpt: Recipient) -> None:
        """Turns the email into an Apprise notification and submits it.

        Args:
            config: The Mailrise configuration to use.
            rcpt: The recipient data to use.

        Raises:
            AppriseNotifyFailure: Apprise failed to submit the notification.
        """
        sender = config.senders[rcpt.key]
        mapping = {
            'subject': self.subject,
            'from': self.from_,
            'body': self.body,
            'to': str(rcpt.key),
            'config': rcpt.key.as_configured(),
            'type': rcpt.notify_type
        }
        attachbase = [AttachMailrise(config, attach) for attach in self.attachments]
        res = await sender.apprise.async_notify(
            title=sender.title_template.safe_substitute(mapping),
            body=sender.body_template.safe_substitute(mapping),
            # Use the configuration body format if specified.
            body_format=sender.body_format or self.body_format,
            notify_type=rcpt.notify_type,
            attach=apprise.AppriseAttachment(attachbase)
        )
        # NOTE: This should probably be called by Apprise itself, but it isn't?
        for ab in attachbase:
            ab.invalidate()
        if not res:
            raise AppriseNotifyFailure()


def parsemessage(msg: EmailMessage, html_conversion: str) -> EmailNotification:
    """Parses an email message into an `EmailNotification`.

    Args:
        msg: The email message.

    Returns:
        The `EmailNotification` instance.
    """
    body_part = msg.get_body()
    body: str
    body_format: apprise.NotifyFormat
    if isinstance(body_part, EmailMessage):
        body = body_part.get_content().strip()
        if html_conversion:
            parser = HTMLConverter()
            converting_body = ConvertingBody(
                body,
                html_conversion
            )
            body = parser.feed(converting_body)
            body_format = apprise.NotifyFormat.TEXT
        else:
            body_format = \
                (apprise.NotifyFormat.HTML
                 if body_part.get_content_subtype() == 'html'
                 else apprise.NotifyFormat.TEXT)
    else:
        body = ''
        body_format = apprise.NotifyFormat.TEXT
    attachments = [_parseattachment(part) for part in msg.iter_attachments()
                   if isinstance(part, EmailMessage)]
    return EmailNotification(
        subject=msg.get('Subject', '[no subject]'),
        from_=msg.get('From', '[no sender]'),
        body=body,
        body_format=body_format,
        attachments=attachments
    )


def _parseattachment(part: EmailMessage) -> Attachment:
    return Attachment(data=part.get_content(), filename=part.get_filename(''))


class HTMLConverter(HTMLParser):
    """HTML email body is converted to the selected format."""
    def __init__(self) -> None:
        HTMLParser.__init__(self)

    def feed(self, body: ConvertingBody) -> ConvertedBody:
        self.body_formatting = ""
        # Supports text conversion, but other conversions such as PDF, image, etc can be added in the future.
        if body.html_conversion == 'text':
            super(HTMLConverter, self).feed(body.body)

            # Removes all html before the last "}". Some HTML can return additional style information with text output.
            converted_body = str(self.body_formatting).split('}')[-1].strip()

            return converted_body
        else:
            raise BodyConversionError("invalid conversion option")

    def handle_data(self, data: str) -> None:
        self.body_formatting += data.strip()

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == 'li':
            self.body_formatting += linesep + '- '
        elif tag == 'blockquote':
            self.body_formatting += linesep + linesep + '\t'
        elif tag in ['br', 'p', 'h1', 'h2', 'h3', 'h4', 'tr', 'th']:
            self.body_formatting += linesep + '\n'

    def handle_endtag(self, tag: str) -> None:
        if tag == 'blockquote':
            self.body_formatting += linesep + linesep


class AttachMailrise(AttachBase):
    """An Apprise attachment type that wraps `Attachment`.

    Data is stored in temporary files for upload.

    Args:
        config: The Mailrise configuration to use.
        attach: The `Attachment` instance.
    """
    location = ContentLocation.LOCAL

    _mrfile = None  # Satisfy mypy by initializing as an Optional.

    def __init__(self, config: MailriseConfig,
                 attach: Attachment, **kwargs: typ.Any) -> None:
        super().__init__(**kwargs)
        self._mrconfig = config
        self._mrattach = attach

    def download(self) -> bool:
        self.invalidate()

        tfile = NamedTemporaryFile(delete=False)
        tfile.write(self._mrattach.data)
        tfile.close()
        self._mrfile = tfile
        self.download_path = tfile.name
        self.detected_name = self._mrattach.filename

        return True  # Indicates the "download" was successful.

    def invalidate(self) -> None:
        tfile = self._mrfile
        if tfile:
            try:
                os.remove(tfile.name)
            except (FileNotFoundError, OSError):
                self._mrconfig.logger.info(
                    'Failed to delete attachment file: %s', tfile.name)
            self._mrfile = None
        super().invalidate()

    def url(self, **kwargs: typ.Any) -> str:
        return f'mailrise://{hex(id(self))}'

    @staticmethod
    def parse_url(url: str, verify_host: bool = True) -> typ.Dict[str, typ.Any]:
        return {}
