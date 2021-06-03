"""
This is a skeleton file that can serve as a starting point for a Python
console script. To run this script uncomment the following lines in the
``[options.entry_points]`` section in ``setup.cfg``::

    console_scripts =
         fibonacci = mailrise.skeleton:run

Then run ``pip install .`` (or ``pip install -e .`` for editable mode)
which will install the command ``fibonacci`` inside your current environment.

Besides console scripts, the header (i.e. until ``_logger``...) of this file can
also be used as template for Python modules.

Note:
    This skeleton file can be safely removed if not needed!

References:
    - https://setuptools.readthedocs.io/en/latest/userguide/entry_point.html
    - https://pip.pypa.io/en/stable/reference/pip_install
"""

import argparse
import logging
import sys
from asyncio import get_event_loop

from mailrise import __version__
from mailrise.config import ConfigFileError, load_config
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
    """Parse command line parameters

    Args:
      args (List[str]): command line parameters as list of strings
          (for example  ``["--help"]``).

    Returns:
      :obj:`argparse.Namespace`: command line parameters namespace
    """
    parser = argparse.ArgumentParser(description="An SMTP gateway for Apprise notifications")
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
    """Setup basic logging

    Args:
      loglevel (int): minimum loglevel for emitting messages
    """
    logformat = "[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(
        level=loglevel, stream=sys.stdout, format=logformat, datefmt="%Y-%m-%d %H:%M:%S"
    )


def main(args: list[str]) -> None:
    """Wrapper allowing :func:`fib` to be called with string arguments in a CLI fashion

    Instead of returning the value from :func:`fib`, it prints the result to the
    ``stdout`` in a nicely formatted message.

    Args:
      args (List[str]): command line parameters as list of strings
          (for example  ``["--verbose", "42"]``).
    """
    pargs = parse_args(args)
    setup_logging(pargs.loglevel)

    try:
        config = load_config(_logger, pargs.config)
    except ConfigFileError as e:
        _logger.critical('Error loading configuration file: %s', e.message)
        return
    if len(config.configs) < 1:
        _logger.critical('Error loading configuration file: '
                         'there are no Apprise configs')
        return

    # TODO: Use UnthreadedController (with `loop`) when that becomes available
    # in stable aiosmtpd.

    controller = Controller(AppriseHandler(config=config))
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
    """Calls :func:`main` passing the CLI arguments extracted from :obj:`sys.argv`

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
