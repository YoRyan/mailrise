"""
This is the YAML configuration parser for Mailrise.
"""

from __future__ import annotations

import io
import os
import typing as typ
from enum import Enum
from logging import Logger
from string import Template
from typing import NamedTuple

import apprise
import yaml
from apprise.common import NotifyType

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
        apprise: The Apprise instance.
        title_template: The template string for notification title texts.
        body_template: The template string for notification body texts.
        body_format: The content type for notifications. If None, this will be
            auto-detected from the body parts of emails.
        html_conversion: The option to convert html to a different format.
    """
    apprise: apprise.Apprise
    title_template: Template
    body_template: Template
    body_format: typ.Optional[apprise.NotifyFormat]
    send_message_encrypted: typ.Optional[bool]
    html_conversion: typ.Optional[str]


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
        senders: A dictionary of notification targets. The key is the identifier
            of the configuration, and the value is the Sender instance itself.
    """
    logger: Logger
    listen_host: str
    listen_port: int
    tls_mode: TLSMode
    tls_certfile: typ.Optional[str]
    tls_keyfile: typ.Optional[str]
    smtp_hostname: typ.Optional[str]
    senders: dict[Key, Sender]


class MailriseEncryption(NamedTuple):
    """Encryption data for the Mailrise instance.

    Args:
        decryptor_companion_port: The decryptor port to listen on.
        decryptor_companion_url: The decryptor url to listen on.
        enable_decryptor_companion: Enables the decryptor companion website.
        encryption_password: The encryption password.
        encryption_random_salt: The random salt.
        \t\\- Salt Creation: print("random16 Key:", os.random(16))
    """
    decryptor_companion_port: typ.Optional[int]
    decryptor_companion_url: typ.Optional[str]
    enable_decryptor_companion: typ.Optional[bool]
    encryption_password: typ.Optional[str]
    encryption_random_salt: typ.Optional[bytes]


def load_config(logger: Logger, f: io.TextIOWrapper) -> MailriseConfig:
    """Loads configuration data from a YAML file.

    Args:
        logger: The logger, which will be passed to the `MailriseConfig` instance.
        f: The file handle to load YAML from.

    Returns:
        The `MailriseConfig` instance.

    Raises:
        ConfigFileError: The configuration file is invalid.
    """
    yml = yaml.safe_load(f)
    if not isinstance(yml, dict):
        raise ConfigFileError("root node not a mapping")

    yml_listen = yml.get('listen', {})

    yml_tls = yml.get('tls', {})
    try:
        tls_mode = TLSMode[yml_tls.get('mode', 'off').upper()]
    except KeyError:
        raise ConfigFileError('invalid TLS operating mode')
    tls_certfile = yml_tls.get('certfile', None)
    tls_keyfile = yml_tls.get('keyfile', None)
    if tls_mode != TLSMode.OFF and not (tls_certfile and tls_keyfile):
        raise ConfigFileError(
            'TLS enabled, but certificate and key files not specified')

    yml_smtp = yml.get('smtp', {})

    yml_configs = yml.get('configs', [])
    if not isinstance(yml_configs, dict):
        raise ConfigFileError("'configs' node not a mapping")
    senders = {_parsekey(key): _load_sender(config)
               for key, config in yml_configs.items()}

    logger.info('Loaded configuration with %d recipient(s)', len(senders))
    return MailriseConfig(
        logger=logger,
        listen_host=yml_listen.get('host', ''),
        listen_port=yml_listen.get('port', 8025),
        tls_mode=tls_mode,
        tls_certfile=tls_certfile,
        tls_keyfile=tls_keyfile,
        smtp_hostname=yml_smtp.get('hostname', None),
        senders=senders
    )


def load_encryption(logger: Logger, f: io.TextIOWrapper) -> MailriseEncryption:
    """Loads encryption data from a YAML file.

    Args:
        logger: The logger, which will be passed to the `MailriseEncryption` instance.
        f: The file handle to load YAML from.

    Returns:
        The `MailriseEncryption` instance.

    Raises:
        ConfigFileError: The configuration file is invalid.
    """

    yml = yaml.safe_load(f)

    if not isinstance(yml, dict):
        raise ConfigFileError("root node not a mapping")

    yml_listen = yml.get('listen', {})

    yml_website = yml.get('website', {})
    if not isinstance(yml_website, dict):
        raise ConfigFileError("'website' not a mapping")

    yml_encryption = yml.get('encryption', {})
    if not isinstance(yml_encryption, dict):
        raise ConfigFileError("'website' not a mapping")

    logger.info('Loaded encryption')
    return MailriseEncryption(
        enable_decryptor_companion=yml_website.get('enable_decryptor_companion', None),
        decryptor_companion_url=yml_website.get('decryptor_companion_url', None),
        decryptor_companion_port=yml_listen.get('decryptor_companion_port', 5000),
        encryption_password=yml_encryption.get('encryption_password', None),
        encryption_random_salt=yml_encryption.get('encryption_random_salt', None),
    )


def _parsekey(s: str) -> Key:
    def err():
        return ConfigFileError(f"invalid config key '{s}'; should be a string or "
                               "an email address without periods in the username")
    if '@' in s:
        user, domain = parseaddrparts(s)
        if not user or not domain or '.' in user:
            raise err()
        return Key(user=user, domain=domain.lower())
    elif '.' in s:
        raise err()
    else:
        return Key(user=s)


def _load_sender(config: dict[str, typ.Any]) -> Sender:
    if not isinstance(config, dict):
        raise ConfigFileError("apprise config node not a mapping")

    # Extract Mailrise-specific values.
    mr_config = config.get('mailrise', {})
    config.pop('mailrise', None)
    title_template = mr_config.get('title_template', '$subject ($from)')
    body_template = mr_config.get('body_template', '$body')
    body_format = mr_config.get('body_format', None)
    html_conversion = mr_config.get('html_conversion', None)
    send_message_encrypted = mr_config.get('send_message_encrypted', None)

    if not any(body_format == c for c in (None,
                                          apprise.NotifyFormat.TEXT,
                                          apprise.NotifyFormat.HTML,
                                          apprise.NotifyFormat.MARKDOWN)):
        raise ConfigFileError(f"invalid apprise notification format: {body_format}")

    html_conversion = mr_config.get('html_conversion', None)
    if not any(html_conversion == c for c in (None,
                                              'text')):
        raise ConfigFileError(f"invalid mailrise html conversion option: {html_conversion}")

    aconfig = apprise.AppriseConfig(asset=DEFAULT_ASSET)
    aconfig.add_config(yaml.safe_dump(config), format='yaml')
    apobj = apprise.Apprise(aconfig)

    return Sender(
        apprise=apobj,
        title_template=Template(title_template),
        body_template=Template(body_template),
        body_format=body_format,
        html_conversion=html_conversion,
        send_message_encrypted=send_message_encrypted,
    )
