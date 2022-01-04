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
import socket

from mailrise.config import ConfigFileError, Key, MailriseConfig, MailriseEncryption
from mailrise.util import parseaddrparts

import apprise
from aiosmtpd.smtp import Envelope, Session, SMTP
from apprise.common import ContentLocation

from ictoolkit.directors.html_director import HTMLConverter
from ictoolkit.directors.encryption_director import encrypt_info

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
    encryption: MailriseEncryption

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
            encryption=self.encryption,
            html_conversion_option=self.config.senders[parsercpt(message.get('To', '[no To]')).key].html_conversion,
            send_message_encrypted=self.config.senders[parsercpt(message.get('To', '[no To]')).key].send_message_encrypted,
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


def parsemessage(msg: EmailMessage, encryption: MailriseEncryption = None, **message_options) -> EmailNotification:
    """Parses an email message into an `EmailNotification`.

    Args:
        msg: The email message.
        encryption (optional): The encryption details.\\
        **message_options:
        \t\\- html_conversion_option: The option to convert the HTML to a different format.\\
        \t\\- send_message_encrypted: The option to send the message encrypted.

    Returns:
        The `EmailNotification` instance.
    """
    body_part = msg.get_body()

    html_conversion_option = message_options.get('html_conversion_option')
    send_message_encrypted = message_options.get('send_message_encrypted')

    body: str
    body_format: apprise.NotifyFormat
    if isinstance(body_part, EmailMessage):
        body = body_part.get_content().strip()
        if 'text' == html_conversion_option:
            parser = HTMLConverter()
            parser.feed(body, html_conversion_option)
            # Removes all html before the last "}". Some HTML can return additional style information with text output.
            body = parser.output.split('}')[-1].strip()
            body_format = apprise.NotifyFormat.TEXT
        else:
            body_format = \
                (apprise.NotifyFormat.HTML
                 if body_part.get_content_subtype() == 'html'
                 else apprise.NotifyFormat.TEXT)

        if (
            send_message_encrypted is True
            and (not encryption.encryption_password
            or not encryption.encryption_random_salt)
        ):
            raise ConfigFileError('Message encryption requires a set encryption password and random salt.')

        # Encryption Option for text and HTML
        if send_message_encrypted is True:
            body = encrypt_info(body, encryption.encryption_password, encryption.encryption_random_salt)
            if encryption.enable_decryptor_companion is True:
                if encryption.decryptor_companion_url:
                    decryptor_url = f'{encryption.decryptor_companion_url}:{encryption.decryptor_companion_port}'
                else:
                    # Gets the hosts IP address for message output.
                    host_ip = socket.gethostbyname(socket.gethostname())
                    decryptor_url = f'http://{host_ip}:{encryption.decryptor_companion_port}'
                body = 'Please use the code below to decrypt the message.\n\n\n' + str(body) + f'\n\n\nDecryption Site: {decryptor_url}'
            else:
                body = 'Please use the code below to decrypt the message.\n\n\n' + str(body)
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
