import logging
from io import StringIO

from mailrise.config import ConfigFileError, Key, load_config

import pytest
from apprise import NotifyFormat


_logger = logging.getLogger(__name__)


def test_errors() -> None:
    """Tests for :fun:`load_config`'s failure conditions."""
    with pytest.raises(ConfigFileError):
        f = StringIO("""
            24
        """)
        load_config(_logger, f)
    with pytest.raises(ConfigFileError):
        f = StringIO("""
            configs: 24
        """)
        load_config(_logger, f)
    with pytest.raises(ConfigFileError):
        f = StringIO("""
            configs:
              test: 24
        """)
        load_config(_logger, f)


def test_load() -> None:
    """Tests a successful load with :fun:`load_config`."""
    f = StringIO("""
        configs:
          test:
            urls:
              - json://localhost
    """)
    mrise = load_config(_logger, f)
    assert len(mrise.senders) == 1
    key = Key(user='test')
    assert key in mrise.senders

    sender = mrise.senders[key]
    assert len(sender.apprise) == 1
    assert sender.apprise[0].url().startswith('json://localhost/')


def test_multi_load() -> None:
    """Tests a sucessful load with :fun:`load_config` with multiple configs."""
    f = StringIO("""
        configs:
          test1:
            urls:
              - json://localhost
          test2:
            urls:
              - json://localhost
    """)
    mrise = load_config(_logger, f)
    assert len(mrise.senders) == 2

    for user in ('test1', 'test2'):
        key = Key(user=user)
        assert key in mrise.senders

        sender = mrise.senders[key]
        assert len(sender.apprise) == 1
        assert sender.apprise[0].url().startswith('json://localhost/')


def test_mailrise_options() -> None:
    """Tests a successful load with :fun:`load_config` with Mailrise-specific
    options."""
    f = StringIO("""
        configs:
          test:
            urls:
              - json://localhost
            mailrise:
              title_template: ""
              body_format: "text"
              html_conversion: "text"
    """)
    mrise = load_config(_logger, f)
    assert len(mrise.senders) == 1
    key = Key(user='test')
    assert key in mrise.senders

    sender = mrise.senders[key]
    assert sender.title_template.template == ''
    assert sender.body_format == NotifyFormat.TEXT
    assert sender.html_conversion == NotifyFormat.TEXT
    
    with pytest.raises(ConfigFileError):
        f = StringIO("""
            configs:
              test:
                urls:
                  - json://localhost
                mailrise:
                  body_format: "BAD"
        """)
        load_config(_logger, f)


def test_config_keys() -> None:
    """Tests the config key parser with both string and full email formats."""
    with pytest.raises(ConfigFileError):
        f = StringIO("""
            configs:
              has.periods:
                urls:
                  - json://localhost
        """)
        load_config(_logger, f)
    with pytest.raises(ConfigFileError):
        f = StringIO("""
            configs:
              bademail@:
                urls:
                  - json://localhost
        """)
        load_config(_logger, f)
    f = StringIO("""
        configs:
          user@example.com:
            urls:
              - json://localhost
    """)
    mrise = load_config(_logger, f)
    assert len(mrise.senders) == 1
    key = Key(user='user', domain='example.com')
    assert key in mrise.senders
