"""
A dummy custom router and authenticator for testing and demonstration purposes.
"""

from logging import Logger
from types import SimpleNamespace
from typing import Any, AsyncGenerator

from aiosmtpd.smtp import AuthResult

from mailrise.router import AppriseNotification, EmailMessage, Router


# The typing and inheritance information is not strictly necessary, but it comes
# in handy when developing your code.

class FullyTypedNoopRouter(Router):  # pylint: disable=too-few-public-methods
    """A dummy custom router with full typing information."""
    async def email_to_apprise(
        self, logger: Logger, email: EmailMessage, auth_data: Any, **kwargs) \
            -> AsyncGenerator[AppriseNotification, None]:
        yield AppriseNotification(
            config='urls: ["json://localhost"]',
            title='Hello, World!',
            body='Lorem ipsum dolor sit amet')

class EasyNoopRouter:  # pylint: disable=too-few-public-methods
    """A dummy custom router with the minimum required code."""
    async def email_to_apprise(self, _logger, _email, _auth_data, **_kwargs):
        """Our replacement for email_to_apprise()."""
        # An ordinary dictionary will not work; we need dot notation access.
        yield SimpleNamespace(
            config='urls: ["json://localhost"]',
            title='Hello, World!',
            body='Lorem ipsum dolor sit amet')



# Technically, an authenticator has to satisfy the
# aiosmtpd.smtp.AuthenticatorType type, but there's no way in Python to
# communicate that to mypy.

def noop_authenticator(_server, _session, _envelope, _mechanism, _auth_data):
    """A dummy custom authenticator."""
    return AuthResult(success=False)


router = FullyTypedNoopRouter()
authenticator = noop_authenticator
