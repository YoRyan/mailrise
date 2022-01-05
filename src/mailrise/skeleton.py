"""
This is the entry point for the `mailrise` command-line program.
"""

from __future__ import annotations

import argparse
import logging
import ssl
import sys
import typing as typ
import os
from pathlib import Path
import threading
import time
import socket
from typing import Union
from asyncio import get_event_loop
from functools import partial

from ictoolkit.directors.thread_director import start_function_thread
from ictoolkit.directors.encryption_director import launch_decryptor_website

from mailrise import __version__
from mailrise.config import ConfigFileError, TLSMode, load_config, load_encryption
from mailrise.smtp import AppriseHandler

from aiosmtpd.controller import Controller

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
        version="mailrise {ver}".format(ver=__version__),
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


def setup_decryptor_companion(decryptor_companion_port: int, encryption_password: str, encryption_random_salt: Union[bytes, str]) -> None:
    _logger = logging.getLogger(__name__)
    # Checks if the launch_decryptor_website companion program program is not running for initial startup.
    if 'companion_decryptor_thread' not in str(threading.enumerate()):
        _logger.info('Starting the launch_decryptor_website companion program')
        # Gets the main program root directory 3 levels up.
        main_root_directory = (Path(__file__) / ".." / ".."/"..").resolve()
        # Creates the decryptor template path.
        decryptor_template_path = os.path.abspath(f'{main_root_directory}/decrypt_templates')
        # This calls the start_function_thread function and passes the companion launch_decryptor_website function and arguments to the start_function_thread.
        # You have to use functools for this to work correctly. Adding the function without functools will cause the function to start before being passed to the start_function_thread.
        start_function_thread(partial(launch_decryptor_website, encryption_password, encryption_random_salt, decryptor_template_path, decryptor_companion_port), 'companion_decryptor_thread', False)
        # Sleeps 5 seconds to allow startup.
        time.sleep(5)
        # Gets the hosts IP address for message output.
        host_ip = socket.gethostbyname(socket.gethostname())
        decryptor_url = f'http://{host_ip}:{decryptor_companion_port}/'
        # Validates the launch_decryptor_website companion program started.
        if 'companion_decryptor_thread' in str(threading.enumerate()):
            _logger.info(f'The decryptor site companion program has started. You may access the webpage via http://127.0.0.1:{decryptor_companion_port}/ or {decryptor_url}')
        else:
            _logger.warning('Failed to start the launch_decryptor_website companion program. The program will continue, but additional troubleshooting will be required to utilize the decryption companion\'s web interface')
    else:
        # Gets the hosts IP address for message output.
        host_ip = socket.gethostbyname(socket.gethostname())
        decryptor_url = f'http://{host_ip}:{decryptor_companion_port}/'
        _logger.debug(f'The decryptor site companion program check passed. The site is still reachable via http://127.0.0.1:{decryptor_companion_port}/ or {decryptor_url}.')


def main(args: list[str]) -> None:
    """Loads the configuration specified on the command-line and starts an SMTP
    server.

    Args:
      args (List[str]): command line parameters as list of strings
          (for example  ``["--verbose", "42"]``).
    """
    pargs1 = parse_args(args)
    pargs2 = parse_args(args)
    setup_logging(pargs1.loglevel)
    setup_logging(pargs2.loglevel)

    try:
        config = load_config(_logger, pargs1.config)
        encryption = load_encryption(_logger, pargs2.config)
    except ConfigFileError as e:
        _logger.critical('Error loading configuration file: %s', e.message)
        return

    if len(config.senders) < 1:
        _logger.critical('Error loading configuration file: '
                         'there are no Apprise configs')
        return

    if (
        encryption.enable_decryptor_companion is True
        and (not encryption.encryption_password
        or not encryption.encryption_random_salt)
    ):
        _logger.critical('Error loading configuration file: '
                            'Decryptor companion requires a set encryption '
                            'password and random salt.')
        return

    if encryption.enable_decryptor_companion is True:
        try:
            setup_decryptor_companion(encryption.decryptor_companion_port, encryption.encryption_password, encryption.encryption_random_salt)
        except Exception as e:
            _logger.critical('Error setting up the decryptor companion:\n%s', e)
            return
        
    tls: typ.Optional[ssl.SSLContext]
    tls_mode = config.tls_mode
    if tls_mode != TLSMode.OFF:
        assert isinstance(config.tls_certfile, str)
        assert isinstance(config.tls_keyfile, str)
        tls = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        tls.load_cert_chain(config.tls_certfile, keyfile=config.tls_keyfile)
        _logger.info('TLS enabled and successfully initialized')
    tls_onconnect = \
        (tls if tls_mode == TLSMode.ONCONNECT else None)
    tls_starttls = \
        (tls if tls_mode == TLSMode.STARTTLS or tls_mode == TLSMode.STARTTLSREQUIRE
         else None)

    # TODO: Use UnthreadedController (with `loop`) when that becomes available
    # in stable aiosmtpd.

    makecon = partial(
        Controller,
        AppriseHandler(config=config, encryption=encryption),
        hostname=config.listen_host,
        port=config.listen_port,
        server_hostname=config.smtp_hostname,
        decode_data=False,
        ident=f'Mailrise {__version__}',
        tls_context=tls_starttls,
        require_starttls=tls_mode == TLSMode.STARTTLSREQUIRE,
    )
    controller = (makecon(ssl_context=tls_onconnect)
                  if tls_onconnect is not None else makecon())
    try:
        controller.start()
    except Exception as e:
        _logger.critical('Failed to start aiosmtpd controller: %s', e)
        controller.stop()
        return

    eloop = get_event_loop()
    try:
        eloop.run_forever()
    finally:
        eloop.close()
        controller.stop()


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
