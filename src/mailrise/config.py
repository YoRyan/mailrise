"""
This is the YAML configuration parser for Mailrise.
"""

from __future__ import annotations

import io
import typing as typ
from dataclasses import dataclass
from enum import Enum
from logging import Logger

import apprise  # type: ignore
import yaml


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
        configs: A dictionary of Apprise YAML configurations. The key is the
            name of the configuration, and the value is the configuration
            itself.
    """
    logger: Logger
    listen_host: str
    listen_port: int
    tls_mode: TLSMode
    tls_certfile: typ.Optional[str]
    tls_keyfile: typ.Optional[str]
    smtp_hostname: typ.Optional[str]
    configs: dict[str, apprise.AppriseConfig]


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
    configs = {key: _load_apprise(config) for key, config in yml_configs.items()}

    logger.info('Loaded configuration with %d recipient(s)', len(configs))
    return MailriseConfig(
        logger=logger,
        listen_host=yml_listen.get('host', ''),
        listen_port=yml_listen.get('port', 8025),
        tls_mode=tls_mode,
        tls_certfile=tls_certfile,
        tls_keyfile=tls_keyfile,
        smtp_hostname=yml_smtp.get('hostname', None),
        configs=configs
    )


def _load_apprise(config: dict[str, typ.Any]) -> apprise.AppriseConfig:
    if not isinstance(config, dict):
        raise ConfigFileError("apprise node not a mapping")
    aconfig = apprise.AppriseConfig()
    aconfig.add_config(yaml.safe_dump(config), format='yaml')
    return aconfig
