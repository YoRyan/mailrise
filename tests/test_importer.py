"""
Tests for the custom Python loader.
"""

import logging
from io import StringIO
from pathlib import Path
from typing import cast

import pytest
from aiosmtpd.smtp import Envelope, Session, SMTP

from mailrise.config import load_config
from mailrise.router import EmailMessage


_logger = logging.getLogger(__name__)
import_path = Path(__file__).parent/'noop_pluggable.py'


@pytest.mark.asyncio
async def test_import_noop() -> None:
    """Tests for the dummy router."""
    file = StringIO(f"""
        import_code: "{import_path}"
    """)
    mrise = load_config(_logger, file)

    router = mrise.router
    notifications = [n async for n
                     in router.email_to_apprise(_logger, cast(EmailMessage, {}), {})]
    assert len(notifications) == 1
    notification = notifications[0]
    assert notification.title == 'Hello, World!'
    assert notification.body == 'Lorem ipsum dolor sit amet'

    authenticator = mrise.authenticator
    assert authenticator is not None
    result = authenticator(cast(SMTP, {}), cast(Session, {}), cast(Envelope, {}), '', {})
    assert not result.success
