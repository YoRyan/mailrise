"""
Mailrise is an SMTP gateway for Apprise notifications.
"""

from importlib.metadata import PackageNotFoundError, version  # pragma: no cover

try:
    # Change here if project is renamed and does not equal the package name
    DIST_NAME = __name__
    __version__ = version(DIST_NAME)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError
