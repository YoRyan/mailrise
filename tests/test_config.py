"""
Tests for configuration loading.
"""

import logging
from io import StringIO

import pytest
from apprise import NotifyFormat

from mailrise.config import ConfigFileError, Key, load_config


_logger = logging.getLogger(__name__)


def test_errors() -> None:
    """Tests for :fun:`load_config`'s failure conditions."""
    with pytest.raises(ConfigFileError):
        file = StringIO("""
            24
        """)
        load_config(_logger, file)
    with pytest.raises(ConfigFileError):
        file = StringIO("""
            configs: 24
        """)
        load_config(_logger, file)
    with pytest.raises(ConfigFileError):
        file = StringIO("""
            configs:
              test: 24
        """)
        load_config(_logger, file)


def test_load() -> None:
    """Tests a successful load with :fun:`load_config`."""
    file = StringIO("""
        configs:
          test:
            urls:
              - json://localhost
    """)
    mrise = load_config(_logger, file)
    assert len(mrise.senders) == 1
    key = Key(user='test')
    assert key in mrise.senders

    sender = mrise.senders[key]
    assert len(sender.notifier) == 1
    assert sender.notifier[0].url().startswith('json://localhost/')


def test_multi_load() -> None:
    """Tests a sucessful load with :fun:`load_config` with multiple configs."""
    file = StringIO("""
        configs:
          test1:
            urls:
              - json://localhost
          test2:
            urls:
              - json://localhost
    """)
    mrise = load_config(_logger, file)
    assert len(mrise.senders) == 2

    for user in ('test1', 'test2'):
        key = Key(user=user)
        assert key in mrise.senders

        sender = mrise.senders[key]
        assert len(sender.notifier) == 1
        assert sender.notifier[0].url().startswith('json://localhost/')


def test_mailrise_options() -> None:
    """Tests a successful load with :fun:`load_config` with Mailrise-specific
    options."""
    file = StringIO("""
        configs:
          test:
            urls:
              - json://localhost
            mailrise:
              title_template: ""
              body_format: "text"
    """)
    mrise = load_config(_logger, file)
    assert len(mrise.senders) == 1
    key = Key(user='test')
    assert key in mrise.senders

    sender = mrise.senders[key]
    assert sender.title_template.template == ''
    assert sender.body_format == NotifyFormat.TEXT

    with pytest.raises(ConfigFileError):
        file = StringIO("""
            configs:
              test:
                urls:
                  - json://localhost
                mailrise:
                  body_format: "BAD"
        """)
        load_config(_logger, file)


def test_config_keys() -> None:
    """Tests the config key parser with both string and full email formats."""
    with pytest.raises(ConfigFileError):
        file = StringIO("""
            configs:
              has.periods:
                urls:
                  - json://localhost
        """)
        load_config(_logger, file)
    with pytest.raises(ConfigFileError):
        file = StringIO("""
            configs:
              bademail@:
                urls:
                  - json://localhost
        """)
        load_config(_logger, file)
    file = StringIO("""
        configs:
          user@example.com:
            urls:
              - json://localhost
    """)
    mrise = load_config(_logger, file)
    assert len(mrise.senders) == 1
    key = Key(user='user', domain='example.com')
    assert key in mrise.senders
