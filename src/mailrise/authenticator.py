"""
This is the authentication functionality for the SMTP server.
"""

import typing as typ

from aiosmtpd.smtp import AuthResult, Envelope, LoginPassword, Session, SMTP


class BasicAuthenticator(typ.NamedTuple):
    """A simple authenticator that uses a static username and password list.
    """
    logins: typ.Mapping[str, str]

    # pylint: disable=too-many-arguments
    def __call__(self, server: SMTP, session: Session, envelope: Envelope,
                 mechanism: str, auth_data: LoginPassword):
        fail_nothandled = AuthResult(success=False, handled=False)
        if mechanism not in ("LOGIN", "PLAIN"):
            return fail_nothandled
        if not isinstance(auth_data, LoginPassword):
            return fail_nothandled

        username = auth_data.login.decode("utf-8")
        password = auth_data.password.decode("utf-8")
        success = self.logins.get(username) == password
        return AuthResult(success=success)

    def __str__(self) -> str:
        return f'Basic({len(self.logins)})'


Authenticator = BasicAuthenticator
