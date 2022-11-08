"""
This is the YAML configuration parser for Mailrise.
"""

from __future__ import annotations

import io
import os
import typing as typ
from enum import Enum
from fnmatch import fnmatchcase
from logging import Logger
from string import Template
from typing import NamedTuple

import apprise
import yaml
from apprise.common import NotifyType

from mailrise.authenticator import Authenticator, BasicAuthenticator
from mailrise.util import parseaddrparts


DEFAULT_ASSET = apprise.AppriseAsset(
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


class TLSMode(Enum):
    """Specifies a TLS encryption operating mode."""
    OFF = 'no TLS'
    ONCONNECT = 'TLS on connect'
    STARTTLS = 'STARTTLS, optional'
    STARTTLSREQUIRE = 'STARTTLS, required'


class Key(NamedTuple):
    """A unique identifier for a sender target.

    Attributes:
        user: The user portion of the recipient address.
        domain: The domain portion of the recipient address, which defaults
            to "mailrise.xyz".
    """
    user: str
    domain: str = 'mailrise.xyz'

    def __str__(self) -> str:
        return f'{self.user}@{self.domain}'

    def as_configured(self) -> str:
        """Drop the domain part of this identifier if it is 'mailrise.xyz'."""
        return self.user if self.domain == 'mailrise.xyz' else str(self)


class Sender(NamedTuple):
    """A configured target for Apprise notifications.

    Attributes:
        notifier: The Apprise instance.
        title_template: The template string for notification title texts.
        body_template: The template string for notification body texts.
        body_format: The content type for notifications. If None, this will be
            auto-detected from the body parts of emails.
    """
    notifier: apprise.Apprise
    title_template: Template
    body_template: Template
    body_format: typ.Optional[apprise.NotifyFormat]


class SenderList(NamedTuple):
    """A list of senders configured for a Mailrise instance, each with a
    matching pattern.

    Attributes:
        by_pattern: A list of [key, sender] tuples, where key contains username
            and domain patterns that can be matched by fnmatch and sender is
            the Sender instance itself.
    """
    by_pattern: list[typ.Tuple[Key, Sender]]

    def __len__(self):
        return len(self.by_pattern)

    def __getitem__(self, key: Key) -> Sender:
        for (pattern_key, sender) in self.by_pattern:
            if (fnmatchcase(key.user, pattern_key.user)
                    and fnmatchcase(key.domain, pattern_key.domain)):
                return sender
        raise KeyError()

    def __contains__(self, key: Key) -> bool:
        try:
            self[key]
        except KeyError:
            return False
        else:
            return True


class MailriseConfig(NamedTuple):
    """Configuration data for a Mailrise instance.

    Attributes:
        logger: The logger, which is used to record interesting events.
        listen_host: The network address to listen on.
        listen_port: The network port to listen on.
        tls_mode: The TLS encryption mode.
        tls_certfile: The path to the TLS certificate chain file.
        tls_keyfile: The path to the TLS key file.
        smtp_hostname: The advertised SMTP server hostname.
        senders: A list of notification targets, each with a [key, sender]
            tuple, where key contains username and domain patterns that can be
            matched by fnmatch and sender is the Sender instance itself.
    """
    logger: Logger
    listen_host: str
    listen_port: int
    tls_mode: TLSMode
    tls_certfile: typ.Optional[str]
    tls_keyfile: typ.Optional[str]
    smtp_hostname: typ.Optional[str]
    senders: SenderList
    authenticator: typ.Optional[Authenticator]


def load_config(logger: Logger, file: io.TextIOWrapper) -> MailriseConfig:
    """Loads configuration data from a YAML file.

    Args:
        logger: The logger, which will be passed to the `MailriseConfig` instance.
        file: The file handle to load YAML from.

    Returns:
        The `MailriseConfig` instance.

    Raises:
        ConfigFileError: The configuration file is invalid.
    """
    yml = yaml.safe_load(file)
    if not isinstance(yml, dict):
        raise ConfigFileError("root node not a mapping")

    yml_listen = yml.get('listen', {})

    yml_tls = yml.get('tls', {})
    try:
        tls_mode = TLSMode[yml_tls.get('mode', 'off').upper()]
    except KeyError as key_err:
        raise ConfigFileError('invalid TLS operating mode') from key_err
    tls_certfile = yml_tls.get('certfile', None)
    tls_keyfile = yml_tls.get('keyfile', None)
    if tls_mode != TLSMode.OFF and not (tls_certfile and tls_keyfile):
        raise ConfigFileError(
            'TLS enabled, but certificate and key files not specified')

    yml_smtp = yml.get('smtp', {})

    yml_configs = yml.get('configs', [])
    if not isinstance(yml_configs, dict):
        raise ConfigFileError("'configs' node not a mapping")
    senders = SenderList(
        by_pattern=[(_parsekey(key), _load_sender(config))
                    for key, config in yml_configs.items()])

    logger.info('Loaded configuration with %d recipient(s)', len(senders))
    return MailriseConfig(
        logger=logger,
        listen_host=yml_listen.get('host', ''),
        listen_port=yml_listen.get('port', 8025),
        tls_mode=tls_mode,
        tls_certfile=tls_certfile,
        tls_keyfile=tls_keyfile,
        smtp_hostname=yml_smtp.get('hostname', None),
        senders=senders,
        authenticator=_load_authenticator(yml_smtp.get('auth', {}))
    )


def _parsekey(key: str) -> Key:
    def err():
        return ConfigFileError(f"invalid config key '{key}'; should be a string or "
                               "an email address without periods in the username")
    if '@' in key:
        user, domain = parseaddrparts(key)
        if not user or not domain or '.' in user:
            raise err()
        return Key(user=user, domain=domain.lower())
    if '.' in key:
        raise err()

    return Key(user=key)


def _load_sender(config: dict[str, typ.Any]) -> Sender:
    if not isinstance(config, dict):
        raise ConfigFileError("apprise config node not a mapping")

    # Extract Mailrise-specific values.
    mr_config = config.get('mailrise', {})
    config.pop('mailrise', None)
    title_template = mr_config.get('title_template', '$subject ($from)')
    body_template = mr_config.get('body_template', '$body')
    body_format = mr_config.get('body_format', None)
    if not any(body_format == c for c in (None,
                                          apprise.NotifyFormat.TEXT,
                                          apprise.NotifyFormat.HTML,
                                          apprise.NotifyFormat.MARKDOWN)):
        raise ConfigFileError(f"invalid apprise notification format: {body_format}")

    aconfig = apprise.AppriseConfig(asset=DEFAULT_ASSET)
    aconfig.add_config(yaml.safe_dump(config), format='yaml')
    apobj = apprise.Apprise(aconfig)

    return Sender(
        notifier=apobj,
        title_template=Template(title_template),
        body_template=Template(body_template),
        body_format=body_format
    )


def _load_authenticator(config: dict[str, typ.Any]) -> typ.Optional[Authenticator]:
    if 'basic' in config and isinstance(config['basic'], dict):
        logins = {str(username): str(password) for username, password in config['basic'].items()}
        return BasicAuthenticator(logins=logins)

    return None
