"""
This is the YAML configuration parser for Mailrise.
"""

from __future__ import annotations

import io
import os
import typing as typ
from enum import Enum
from functools import partial
from logging import Logger
from typing import NamedTuple

import yaml

from mailrise.authenticator import Authenticator, BasicAuthenticator
from mailrise.router import ConfigFileError, Router
from mailrise.simple_router import load_from_yaml as load_simple_router


class ConfigFileLoader(yaml.FullLoader):  # pylint: disable=too-many-ancestors
    """Our YAML loader class, which comes with an attached logger."""
    logger: Logger

    def __init__(self, stream, logger: Logger) -> None:
        super().__init__(stream)
        self.logger = logger
        self.add_constructor('!env_var', ConfigFileLoader._env_var_constructor)

    @staticmethod
    def _env_var_constructor(loader: ConfigFileLoader, node: yaml.nodes.Node) -> str:
        """Load environment variables and embed them into the configuration YAML."""
        value = str(node.value)
        try:
            env, default = value.split(maxsplit=1)
        except ValueError:
            env, default = value, None

        if env in os.environ:
            return os.environ[env]
        if default:
            loader.logger.warning(
                'Environment variable %s not defined, using default value: %s',
                env, default)
            return default
        raise ConfigFileError(
            f'Environment variable {env} not defined and no default value provided')


class TLSMode(Enum):
    """Specifies a TLS encryption operating mode."""
    OFF = 'no TLS'
    ONCONNECT = 'TLS on connect'
    STARTTLS = 'STARTTLS, optional'
    STARTTLSREQUIRE = 'STARTTLS, required'


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
    router: Router
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
    yml = yaml.load(
        file, Loader=partial(ConfigFileLoader, logger=logger))  # type: ignore
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

    router = load_simple_router(logger, yml.get('configs', {}))

    return MailriseConfig(
        logger=logger,
        listen_host=yml_listen.get('host', ''),
        listen_port=yml_listen.get('port', 8025),
        tls_mode=tls_mode,
        tls_certfile=tls_certfile,
        tls_keyfile=tls_keyfile,
        smtp_hostname=yml_smtp.get('hostname', None),
        router=router,
        authenticator=_load_authenticator(yml_smtp.get('auth', {}))
    )


def _load_authenticator(config: dict[str, typ.Any]) -> typ.Optional[Authenticator]:
    if 'basic' in config and isinstance(config['basic'], dict):
        logins = {str(username): str(password)
                  for username, password in config['basic'].items()}
        return BasicAuthenticator(logins=logins)

    return None
