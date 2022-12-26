"""
This is the entry point for the `mailrise` command-line program.
"""

from __future__ import annotations

import argparse
import logging
import signal
import ssl
import sys
import typing as typ
from asyncio.events import new_event_loop
from functools import partial

from aiosmtpd.controller import UnthreadedController

from mailrise import __version__
from mailrise.config import ConfigFileError, TLSMode, load_config
from mailrise.smtp import AppriseHandler

__author__ = "Ryan Young"
__copyright__ = "Ryan Young"
__license__ = "MIT"

_logger = logging.getLogger(__name__)


# ---- Python API ----
# The functions defined in this section can be imported by users in their
# Python scripts/interactive interpreter, e.g. via
# `from mailrise.skeleton import fib`,
# when using this Python module as a library.


# ---- CLI ----
# The functions defined in this section are wrappers around the main Python
# API allowing them to be called directly from the terminal as a CLI
# executable/script.


def parse_args(args: list[str]) -> argparse.Namespace:
    """Parse command line parameters.

    Args:
      args (List[str]): command line parameters as list of strings
          (for example  ``["--help"]``).

    Returns:
      :obj:`argparse.Namespace`: command line parameters namespace.
    """
    parser = argparse.ArgumentParser(
        description="An SMTP gateway for Apprise notifications")
    parser.add_argument(
        "--version",
        action="version",
        version=f"mailrise {__version__}"
    )
    parser.add_argument(
        dest="config",
        help="path to configuration file",
        type=argparse.FileType("r"),
        metavar="CONFIG"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="loglevel",
        help="set loglevel to INFO",
        action="store_const",
        const=logging.INFO,
    )
    parser.add_argument(
        "-vv",
        "--very-verbose",
        dest="loglevel",
        help="set loglevel to DEBUG",
        action="store_const",
        const=logging.DEBUG,
    )
    return parser.parse_args(args)


def setup_logging(loglevel: int) -> None:
    """Setup basic logging.

    Args:
      loglevel (int): Minimum loglevel for emitting messages.
    """
    logformat = "[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(
        level=loglevel, stream=sys.stdout, format=logformat, datefmt="%Y-%m-%d %H:%M:%S"
    )


def main(args: list[str]) -> None:
    """Loads the configuration specified on the command-line and starts an SMTP
    server.

    Args:
      args (List[str]): command line parameters as list of strings
          (for example  ``["--verbose", "42"]``).
    """
    pargs = parse_args(args)
    setup_logging(pargs.loglevel)

    try:
        config = load_config(_logger, pargs.config)
    except ConfigFileError as err:
        _logger.critical('Error loading configuration file: %s', err.message)
        return
    if len(config.senders) < 1:
        _logger.critical('Error loading configuration file: '
                         'there are no Apprise configs')
        return

    tls: typ.Optional[ssl.SSLContext] = None
    tls_mode = config.tls_mode
    if tls_mode != TLSMode.OFF:
        assert isinstance(config.tls_certfile, str)
        assert isinstance(config.tls_keyfile, str)
        tls = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        tls.load_cert_chain(config.tls_certfile, keyfile=config.tls_keyfile)
        _logger.info('TLS enabled and successfully initialized')
    tls_onconnect = tls if tls_mode == TLSMode.ONCONNECT else None
    tls_starttls = \
        tls if tls_mode in (TLSMode.STARTTLS, TLSMode.STARTTLSREQUIRE) else None

    makecon = partial(
        UnthreadedController,
        AppriseHandler(config=config),
        authenticator=config.authenticator,
        auth_required=config.authenticator is not None,
        # We assume that if you've enabled STARTTLS, you'll want to require it.
        auth_require_tls=tls_starttls is not None,
        hostname=config.listen_host,
        port=config.listen_port,
        server_hostname=config.smtp_hostname,
        decode_data=False,
        ident=f'Mailrise {__version__}',
        tls_context=tls_starttls,
        ssl_context=tls_onconnect,
        require_starttls=tls_mode == TLSMode.STARTTLSREQUIRE
    )
    _logger.debug(
        'Arguments for aiosmtpd: %s',
        ', '.join(f'{kw}={makecon.keywords[kw]}'
                  for kw in ('authenticator', 'auth_required', 'auth_require_tls',
                             'tls_context', 'ssl_context', 'require_starttls')))

    eloop = new_event_loop()
    controller = makecon(loop=eloop)

    def clean_exit():
        _logger.info('Caught exit signal...')
        eloop.stop()
        controller.end()
    for sig in (signal.SIGINT, signal.SIGTERM):
        eloop.add_signal_handler(sig, clean_exit)

    controller.begin()
    eloop.run_forever()


def run() -> None:
    """Calls :func:`main` passing the CLI arguments extracted from :obj:`sys.argv`.

    This function can be used as entry point to create console scripts with setuptools.
    """
    main(sys.argv[1:])


if __name__ == "__main__":
    # ^  This is a guard statement that will prevent the following code from
    #    being executed in the case someone imports this file instead of
    #    executing it as a script.
    #    https://docs.python.org/3/library/__main__.html

    # After installing your project with pip, users can also run your Python
    # modules as scripts via the ``-m`` flag, as defined in PEP 338::
    #
    #     python -m mailrise.skeleton 42
    #
    run()
