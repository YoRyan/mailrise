"""
This is the SMTP server functionality for Mailrise.
"""

import re
from dataclasses import dataclass
from email.utils import parseaddr

import apprise # type: ignore


class RecipientError(Exception):
    """Exception raised for invalid recipient email addresses."""
    def __init__(self, message: str) -> None:
        self.message = message


@dataclass
class Recipient:
    """The routing information encoded into a recipient address."""
    config_key: str
    notify_type: apprise.NotifyType


def parsercpt(addr: str) -> Recipient:
    _, email = parseaddr(addr)
    rx_types = r'((?:\.(?:info|success|warning|failure))?)'
    rx = f'(?:"([^"@\\.]*){rx_types}"|([^@\\.]*){rx_types})@mailrise\\.xyz$'
    match = re.search(rx, email, re.IGNORECASE)
    if match is None:
        raise RecipientError(f"'{email}' is not a valid mailrise recipient")
    if match.group(1) is None:
        key = match.group(3)
        ntypes = match.group(4).lower()
    else:
        key = match.group(1)
        ntypes = match.group(2).lower()

    ntype = apprise.NotifyType.INFO
    if ntypes == '.info':
        pass
    elif ntypes == '.success':
        ntype = apprise.NotifyType.SUCCESS
    elif ntypes == '.warning':
        ntype = apprise.NotifyType.WARNING
    elif ntypes == '.failure':
        ntype = apprise.NotifyType.FAILURE

    return Recipient(config_key=key, notify_type=ntype)
