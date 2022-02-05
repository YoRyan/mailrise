"""
Miscellaneous common functions for parts of Mailrise.
"""

import re
from typing import Tuple


def parseaddrparts(email: str) -> Tuple[str, str]:
    """Parses an email address into its component user and domain parts."""
    match = re.search(r'(?:"([^"@]*)"|([^@]*))@([^@]*)$', email)
    if match is None:
        return '', ''
    quoted = match.group(1) is not None
    user = match.group(1) if quoted else match.group(2)
    domain = match.group(3)
    return user, domain
