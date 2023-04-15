"""
This is the SMTP server functionality for Mailrise.
"""

from __future__ import annotations

import asyncio
import email.policy
import os
import typing as typ
from email import contentmanager
from email.message import EmailMessage as StdlibEmailMessage
from email.parser import BytesParser
from tempfile import NamedTemporaryFile

import apprise
from aiosmtpd.smtp import Envelope, Session, SMTP
from apprise.common import ContentLocation

from mailrise.config import MailriseConfig
import mailrise.router as r

# Mypy, for some reason, considers AttachBase a module, not a class.
MYPY = False
# pylint: disable=ungrouped-imports
if MYPY:
    from apprise.attachment.AttachBase import AttachBase
else:
    from apprise.attachment import AttachBase


class AppriseNotifyFailure(Exception):
    """Exception raised when Apprise fails to deliver a notification.

    Note: Apprise does not provide any information about the reason for the
    failure.
    """


class UnreadableMultipart(Exception):
    """Exception raised for multipart messages that can't be parsed.

    Attributes:
        message: The multipart email part.
    """
    message: StdlibEmailMessage

    def __init__(self, message: StdlibEmailMessage) -> None:
        super().__init__(self)
        self.message = message


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
        self.config.logger.info('Added recipient: %s', address)
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
        assert isinstance(message, StdlibEmailMessage)
        try:
            notification = _parsemessage(message, envelope)
        except UnreadableMultipart as mpe:
            subparts = \
                ' '.join(part.get_content_type() for part in mpe.message.iter_parts())
            self.config.logger.error('Failed to parse %s message: [ %s ]',
                                     mpe.message.get_content_type(), subparts)
        self.config.logger.info('Accepted email, subject: %s', notification.subject)

        try:
            to_send = [data async for data in self.config.router.email_to_apprise(
                           logger=self.config.logger,
                           email=notification,
                           auth_data=session.auth_data
                       )]
        except Exception as exc:  # pylint: disable=broad-except
            return f'450 router had internal exception: {exc}'

        results = await asyncio.gather(
            *(_apprise_notify(self.config, data) for data in to_send),
            return_exceptions=True
        )
        if any(isinstance(result, AppriseNotifyFailure) for result in results):
            addresses = ' '.join(envelope.rcpt_tos)
            self.config.logger.warning('Notification failed: %s ➤ %s',
                                       notification.subject, addresses)
            return '450 failed to send notification'

        return '250 OK'


def _parsemessage(msg: StdlibEmailMessage, envelope: Envelope) -> r.EmailMessage:
    """Parses an email message into an `EmailNotification`.

    Args:
        msg: The email message.

    Returns:
        The `EmailNotification` instance.
    """
    py_body_part = msg.get_body()
    body: typ.Optional[tuple[str, apprise.NotifyFormat]]
    if isinstance(py_body_part, StdlibEmailMessage):
        body_part: StdlibEmailMessage
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
                   if isinstance(part, StdlibEmailMessage)]
    return r.EmailMessage(
        email_message=msg,
        subject=msg.get('Subject', '[no subject]'),
        from_=msg.get('From', '[no sender]'),
        to=envelope.rcpt_tos,
        # Apprise will fail if no body is supplied.
        body=body[0] if body else '[no body]',
        body_format=body[1] if body else apprise.NotifyFormat.TEXT,
        attachments=attachments
    )


def _getmultiparttext(msg: StdlibEmailMessage) -> StdlibEmailMessage:
    """Search for the textual body part of a multipart email."""
    content_type = msg.get_content_type()
    if content_type in ('multipart/related', 'multipart/alternative'):
        parts = list(msg.iter_parts())
        # Look for these types of parts in descending order.
        for parttype in ('multipart/alternative', 'multipart/related',
                         'text/html', 'text/plain'):
            found = \
                next((p for p in parts if isinstance(p, StdlibEmailMessage)
                     and p.get_content_type() == parttype), None)
            if found is not None:
                return _getmultiparttext(found)
        raise UnreadableMultipart(msg)
    return msg


def _parseattachment(part: StdlibEmailMessage) -> r.EmailAttachment:
    return r.EmailAttachment(data=part.get_content(), filename=part.get_filename(''))


async def _apprise_notify(config: MailriseConfig, data: r.AppriseNotification):
    ap_config = apprise.AppriseConfig(asset=data.asset or r.DEFAULT_ASSET)
    ap_config.add_config(data.config, format=data.config_format)
    ap_instance = apprise.Apprise(ap_config)

    attach_base = [_AttachMailrise(config, attach) for attach in data.attachments]
    success = await ap_instance.async_notify(
        title=data.title,
        body=data.body,
        body_format=data.body_format,
        notify_type=data.notify_type,
        attach=attach_base
    )
    # NOTE: This should probably be called by Apprise itself, but it isn't?
    for base in attach_base:
        base.invalidate()
    if not success:
        raise AppriseNotifyFailure


class _AttachMailrise(AttachBase):
    """An Apprise attachment type that wraps `Attachment`.

    Data is stored in temporary files for upload.

    Args:
        config: The Mailrise configuration to use.
        attach: The `Attachment` instance.
    """
    location = ContentLocation.LOCAL

    _mrfile = None  # Satisfy mypy by initializing as an Optional.

    def __init__(self, config: MailriseConfig,
                 attach: r.EmailAttachment, **kwargs: typ.Any) -> None:
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
