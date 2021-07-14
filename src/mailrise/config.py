"""
This is the YAML configuration parser for Mailrise.
"""

from __future__ import annotations

import io
import os
import typing as typ
from dataclasses import dataclass
from enum import Enum
from logging import Logger
from string import Template

import apprise  # type: ignore
import yaml
from apprise.common import NotifyType  # type: ignore


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


@dataclass
class Sender:
    """A configured target for Apprise notifications.

    Attributes:
        apprise: The Apprise instance.
        title_template: The template string for notification title texts.
        body_template: The template string for notification body texts.
        body_format: The content type for notifications. If None, this will be
            auto-detected from the body parts of emails.
    """
    apprise: apprise.Apprise
    title_template: Template
    body_template: Template
    body_format: typ.Optional[apprise.NotifyFormat]


@dataclass
class MailriseConfig:
    """Configuration data for a Mailrise instance.

    Attributes:
        logger: The logger, which is used to record interesting events.
        listen_host: The network address to listen on.
        listen_port: The network port to listen on.
        tls_mode: The TLS encryption mode.
        tls_certfile: The path to the TLS certificate chain file.
        tls_keyfile: The path to the TLS key file.
        smtp_hostname: The advertised SMTP server hostname.
        senders: A dictionary of notification targets. The key is the name of
            the configuration, and the value is the Sender instance itself.
    """
    logger: Logger
    listen_host: str
    listen_port: int
    tls_mode: TLSMode
    tls_certfile: typ.Optional[str]
    tls_keyfile: typ.Optional[str]
    smtp_hostname: typ.Optional[str]
    senders: dict[str, Sender]


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
    senders = {key: _load_sender(config) for key, config in yml_configs.items()}

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


def _load_sender(config: dict[str, typ.Any]) -> Sender:
    if not isinstance(config, dict):
        raise ConfigFileError("apprise config node not a mapping")

    # Extract Mailrise-specific values.
    mr_config = config.get('mailrise', {})
    config.pop('mailrise', None)
    title_template = mr_config.get('title_template', '$subject ($from)')
    body_template = mr_config.get('body_template', '$body')

    aconfig = apprise.AppriseConfig(asset=DEFAULT_ASSET)
    aconfig.add_config(yaml.safe_dump(config), format='yaml')
    apobj = apprise.Apprise()
    apobj.add(aconfig)

    return Sender(
        apprise=apobj,
        title_template=Template(title_template),
        body_template=Template(body_template),
        body_format=mr_config.get('body_format', None)
    )
