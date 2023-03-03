"""
Routers process email messages and produce notifications.
"""

import os
import typing as typ
from abc import ABCMeta, abstractmethod
from logging import Logger

from apprise import AppriseAsset, NotifyFormat
from apprise.common import NotifyType


DEFAULT_ASSET = AppriseAsset(
    app_id='Mailrise',
    app_desc='Mailrise SMTP Notification Relay',
    app_url='https://mailrise.xyz',
    html_notify_map={
        NotifyType.INFO: '#2e6e99',
        NotifyType.SUCCESS: '#2e992e',
        NotifyType.WARNING: '#99972e',
        NotifyType.FAILURE: '#993a2e'
    },
    theme=None,
    default_extension='.png',
    image_url_mask='https://raw.githubusercontent.com/YoRyan/mailrise/main/'
                   'src/mailrise/asset/mailrise-{TYPE}-{XY}{EXTENSION}',
    image_url_logo='https://raw.githubusercontent.com/YoRyan/mailrise/main/'
                   'src/mailrise/asset/mailrise-logo.png',
    image_path_mask=os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            'asset',
            'mailrise-{TYPE}-{XY}{EXTENSION}'
        )
    )
)


class ConfigFileError(Exception):
    """Exception raised for invalid configuration files.

    Attributes:
        message: The reason the configuration file is invalid.
    """
    message: str

    def __init__(self, message: str) -> None:
        super().__init__(self)
        self.message = message


class EmailAttachment(typ.NamedTuple):
    """Represents an email attachment.

    Attributes:
        data: The contents of the attachment.
        filename: The filename of the attachment as it was set by the sender.
    """
    data: bytes
    filename: str


class EmailMessage(typ.NamedTuple):
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
    body_format: NotifyFormat
    attachments: typ.List[EmailAttachment]


class AppriseNotification(typ.NamedTuple):
    """Encapsulates the information needed to submit a notification to Apprise.

    Attributes:
        asset: The Apprise asset, which controls the icon sent with the
            notification. If None, use some flavor of the Mailrise logo.
        config: The Apprise configuration file to use, as a string.
        config_format: The format of the configuration file. If None, Apprise
            will autodetect (with some slight overhead).
        title: The notification title.
        body: The notification body.
        body_format: The content type (text/html/markdown) of the body.
        notify_type: The class of notification (info/success/warning/failure).
        attachments: A list of attachments to send with the notification.
    """
    asset: AppriseAsset | None
    config: str
    config_format: typ.Literal['text', 'yaml'] | None
    title: str
    body: str
    body_format: NotifyFormat
    notify_type: NotifyType
    attachments: typ.List[EmailAttachment]


class Router(metaclass=ABCMeta):  # pylint: disable=too-few-public-methods
    """A pluggable module that dispatches emails."""

    @abstractmethod
    async def email_to_apprise(self, logger: Logger,
                               email: EmailMessage, recipients: typ.List[str]) \
            -> typ.AsyncGenerator[AppriseNotification, None]:
        """Converts an email into one or multiple Apprise notifications."""
        # Needed to pass mypy, which fails to realize this is an async generator.
        # See https://github.com/python/mypy/issues/5070
        yield AppriseNotification(
            asset=None,
            config='',
            config_format=None,
            title='',
            body='',
            body_format=NotifyFormat.TEXT,
            notify_type=NotifyType.INFO,
            attachments=[]
        )
