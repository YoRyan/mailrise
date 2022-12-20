"""
This is the SMTP server functionality for Mailrise.
"""

from __future__ import annotations

import asyncio
import email.policy
import os
import re
import typing as typ
from email import contentmanager
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr
from tempfile import NamedTemporaryFile

import apprise
from aiosmtpd.smtp import Envelope, Session, SMTP
from apprise.common import ContentLocation

from mailrise.config import Key, MailriseConfig
from mailrise.util import parseaddrparts

# Mypy, for some reason, considers AttachBase a module, not a class.
MYPY = False
# pylint: disable=ungrouped-imports
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
        super().__init__(self)
        self.message = message


class AppriseNotifyFailure(Exception):
    """Exception raised when Apprise fails to deliver a notification.

    Note: Apprise does not provide any information about the reason for the
    failure."""


class UnreadableMultipart(Exception):
    """Exception raised for multipart messages that can't be parsed.

    Attributes:
        message: The multipart email part.
    """
    message: EmailMessage

    def __init__(self, message: EmailMessage) -> None:
        super().__init__(self)
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
    _, rcpt = parseaddr(addr)
    user, domain = parseaddrparts(rcpt)
    if not user or not domain:
        raise RecipientError(f"'{rcpt}' is not a valid mailrise recipient")
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

    # pylint: disable=invalid-name,unused-argument,too-many-arguments
    async def handle_RCPT(self, server: SMTP, session: Session, envelope: Envelope,
                          address: str, rcpt_options: list[str]) -> str:
        """Called during RCPT TO."""
        try:
            rcpt = parsercpt(address)
        except RecipientError as rcpt_err:
            self.config.logger.warning('Invalid recipient: %s', address)
            return f'550 {rcpt_err.message}'
        if self.config.get_sender(rcpt.key) is None:
            self.config.logger.warning('Unknown recipient: %s', address)
            return '551 recipient does not exist in configuration file'
        self.config.logger.info('Accepted recipient: %s', address)
        envelope.rcpt_tos.append(address)
        return '250 OK'

    # pylint: disable=invalid-name,unused-argument
    async def handle_DATA(self, server: SMTP, session: Session, envelope: Envelope) \
            -> str:
        """Called during DATA after the entire message ('SMTP content' as described
        in RFC 5321) has been received."""
        assert isinstance(envelope.content, bytes)
        parser = BytesParser(policy=email.policy.default)
        message = parser.parsebytes(envelope.content)
        assert isinstance(message, EmailMessage)
        try:
            notification = parsemessage(message)
        except UnreadableMultipart as mpe:
            subparts = \
                ' '.join(part.get_content_type() for part in mpe.message.iter_parts())
            self.config.logger.error('Failed to parse %s message: [ %s ]',
                                     mpe.message.get_content_type(), subparts)
        self.config.logger.info('Accepted email, subject: %s', notification.subject)

        rcpts = (parsercpt(addr) for addr in envelope.rcpt_tos)
        aws = (notification.submit(self.config, rcpt) for rcpt in rcpts)
        try:
            await asyncio.gather(*aws)
        except AppriseNotifyFailure:
            addresses = ' '.join(envelope.rcpt_tos)
            self.config.logger.warning('Notification failed: %s ➤ %s',
                                       notification.subject, addresses)
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
        sender = config.get_sender(rcpt.key)
        assert sender is not None
        mapping = {
            'subject': self.subject,
            'from': self.from_,
            'body': self.body,
            'to': str(rcpt.key),
            'config': rcpt.key.as_configured(),
            'type': rcpt.notify_type
        }
        attachbase = [AttachMailrise(config, attach) for attach in self.attachments]
        res = await sender.notifier.async_notify(
            title=sender.title_template.safe_substitute(mapping),
            body=sender.body_template.safe_substitute(mapping),
            # Use the configuration body format if specified.
            body_format=sender.body_format or self.body_format,
            notify_type=rcpt.notify_type,
            attach=apprise.AppriseAttachment(attachbase)
        )
        # NOTE: This should probably be called by Apprise itself, but it isn't?
        for base in attachbase:
            base.invalidate()
        if not res:
            raise AppriseNotifyFailure()


def parsemessage(msg: EmailMessage) -> EmailNotification:
    """Parses an email message into an `EmailNotification`.

    Args:
        msg: The email message.

    Returns:
        The `EmailNotification` instance.
    """
    py_body_part = msg.get_body()
    body: typ.Optional[tuple[str, apprise.NotifyFormat]]
    if isinstance(py_body_part, EmailMessage):
        body_part: EmailMessage
        try:
            py_body_part.get_content()
        except KeyError:  # stdlib failed to read the content, which means multipart
            body_part = _getmultiparttext(py_body_part)
        else:
            body_part = py_body_part
        body_content = contentmanager.raw_data_manager.get_content(body_part)
        is_html = body_part.get_content_subtype() == 'html'
        body = (body_content.strip(),
                apprise.NotifyFormat.HTML if is_html else apprise.NotifyFormat.TEXT)
    else:
        body = None
    attachments = [_parseattachment(part) for part in msg.iter_attachments()
                   if isinstance(part, EmailMessage)]
    return EmailNotification(
        subject=msg.get('Subject', '[no subject]'),
        from_=msg.get('From', '[no sender]'),
        # Apprise will fail if no body is supplied.
        body=body[0] if body else '[no body]',
        body_format=body[1] if body else apprise.NotifyFormat.TEXT,
        attachments=attachments
    )


def _getmultiparttext(msg: EmailMessage) -> EmailMessage:
    """Search for the textual body part of a multipart email."""
    content_type = msg.get_content_type()
    if content_type in ('multipart/related', 'multipart/alternative'):
        parts = list(msg.iter_parts())
        # Look for these types of parts in descending order.
        for parttype in ('multipart/alternative', 'multipart/related',
                         'text/html', 'text/plain'):
            found = \
                next((p for p in parts if isinstance(p, EmailMessage)
                     and p.get_content_type() == parttype), None)
            if found is not None:
                return _getmultiparttext(found)
        raise UnreadableMultipart(msg)
    return msg


def _parseattachment(part: EmailMessage) -> Attachment:
    return Attachment(data=part.get_content(), filename=part.get_filename(''))


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

        with NamedTemporaryFile(delete=False) as tfile:
            tfile.write(self._mrattach.data)
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

    def url(self, *args: typ.Any, **kwargs: typ.Any) -> str:
        return f'mailrise://{hex(id(self))}'

    @staticmethod
    def parse_url(url: str, verify_host: bool = True,
                  mimetype_db: typ.Any = None) -> typ.Dict[str, typ.Any]:
        return {}
