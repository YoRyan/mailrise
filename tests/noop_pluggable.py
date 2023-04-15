"""
A dummy custom router for testing and demonstration purposes.
"""

from logging import Logger
from types import SimpleNamespace
from typing import AsyncGenerator

from mailrise.router import AppriseNotification, EmailMessage, Router


# The typing and inheritance information is not strictly necessary, but it comes
# in handy when developing your code.


class FullyTypedNoopRouter(Router):  # pylint: disable=too-few-public-methods
    """
    A dummy custom router with full typing information.
    """
    async def email_to_apprise(self, logger: Logger, email: EmailMessage) \
            -> AsyncGenerator[AppriseNotification, None]:
        yield AppriseNotification(
            config='urls: ["json://localhost"]',
            title='Hello, World!',
            body='Lorem ipsum dolor sit amet')


class EasyNoopRouter:  # pylint: disable=too-few-public-methods
    """
    A dummy custom router with the minimum required code.
    """
    async def email_to_apprise(self, _logger, _email):
        """Our replacement for email_to_apprise()."""
        # An ordinary dictionary will not work; we need dot notation access.
        yield SimpleNamespace(
            config='urls: ["json://localhost"]',
            title='Hello, World!',
            body='Lorem ipsum dolor sit amet')


router = FullyTypedNoopRouter()
