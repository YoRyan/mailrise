"""
This is the YAML configuration parser for Mailrise.
"""

from __future__ import annotations

import importlib.util
import io
import os
import typing as typ
from enum import Enum
from functools import partial
from logging import Logger
from typing import NamedTuple

import yaml
from aiosmtpd.smtp import AuthenticatorType

from mailrise.basic_authenticator import BasicAuthenticator
from mailrise.router import Router
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
        loader.logger.critical(
            'Environment variable %s not defined and no default value provided', env)
        raise SystemExit(1)


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
    authenticator: typ.Optional[AuthenticatorType]


class MailriseImportedCode(NamedTuple):
    """The pluggable Python code for a Mailrise instance when imported as a
    Python module. Of course, the actual result will be a module rather than
    a named tuple, but we can expect it to share these attributes.

    Attributes:
        router: The custom router, if supplied.
        authenticator: The custom authenticator, if supplied.
    """
    router: typ.Optional[Router] = None
    authenticator: typ.Optional[AuthenticatorType] = None


def load_config(logger: Logger, file: io.TextIOWrapper) -> MailriseConfig:
    """Loads configuration data from a YAML file.

    Args:
        logger: The logger, which will be passed to the `MailriseConfig` instance.
        file: The file handle to load YAML from.

    Returns:
        The `MailriseConfig` instance.
    """
    yml = yaml.load(
        file, Loader=partial(ConfigFileLoader, logger=logger))  # type: ignore
    if not isinstance(yml, dict):
        logger.critical('YAML root node is not a mapping')
        raise SystemExit(1)

    yml_listen = yml.get('listen', {})

    yml_tls = yml.get('tls', {})
    yml_tls_mode = yml_tls.get('mode', 'off').upper()
    try:
        tls_mode = TLSMode[yml_tls_mode]
    except KeyError as exc:
        logger.critical('Invalid TLS operating mode: %s', yml_tls_mode)
        raise SystemExit(1) from exc
    tls_certfile = yml_tls.get('certfile', None)
    tls_keyfile = yml_tls.get('keyfile', None)
    if tls_mode != TLSMode.OFF and not (tls_certfile and tls_keyfile):
        logger.critical('TLS enabled, but certificate and key files not specified')
        raise SystemExit(1)

    yml_smtp = yml.get('smtp', {})

    router = None
    authenticator = None
    yml_import_path = yml.get('import_code', None)
    if yml_import_path:
        logger.info('Importing configurable Python code from: %s', yml_import_path)
        imported = _load_imported_code(logger, yml_import_path)
        if imported.router:
            logger.info('Discovered a custom router')
            router = imported.router
        if imported.authenticator:
            logger.info('Discovered a custom authenticator')
            authenticator = imported.authenticator
    if not router:
        router = load_simple_router(logger, yml.get('configs', {}))
    if not authenticator:
        authenticator = _load_authenticator(yml_smtp.get('auth', {}))

    return MailriseConfig(
        logger=logger,
        listen_host=yml_listen.get('host', ''),
        listen_port=yml_listen.get('port', 8025),
        tls_mode=tls_mode,
        tls_certfile=tls_certfile,
        tls_keyfile=tls_keyfile,
        smtp_hostname=yml_smtp.get('hostname', None),
        router=router,
        authenticator=authenticator
    )


def _load_imported_code(logger: Logger, file_path: str) -> MailriseImportedCode:
    spec = importlib.util.spec_from_file_location(os.path.basename(file_path), file_path)
    if not (spec and spec.loader):
        logger.critical(
            'Nonexistent path or invalid Python when importing code from: %s', file_path)
        raise SystemExit(1)

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pylint: disable=broad-except
        logger.critical('Exception when importing code from: %s', file_path, exc_info=True)
        raise SystemExit(1) from exc

    return typ.cast(MailriseImportedCode, module)


def _load_authenticator(config: dict[str, typ.Any]) -> typ.Optional[AuthenticatorType]:
    if 'basic' in config and isinstance(config['basic'], dict):
        logins = {str(username): str(password)
                  for username, password in config['basic'].items()}
        return typ.cast(AuthenticatorType, BasicAuthenticator(logins=logins))

    return None
