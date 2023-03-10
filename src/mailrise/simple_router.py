"""
This is the YAML-based router for Mailrise.
"""

from email.utils import parseaddr
from fnmatch import fnmatchcase
from logging import Logger
from string import Template
import re
import typing as typ

import apprise
import yaml

import mailrise.router as r


class _Key(typ.NamedTuple):
    """A unique identifier for a sender target.

    Attributes:
        user: The user portion of the recipient address.
        domain: The domain portion of the recipient address, which defaults
            to "mailrise.xyz".
    """
    user: str
    domain: str = 'mailrise.xyz'

    def __str__(self) -> str:
        return f'{self.user}@{self.domain}'

    def as_configured(self) -> str:
        """Drop the domain part of this identifier if it is 'mailrise.xyz'."""
        return self.user if self.domain == 'mailrise.xyz' else str(self)


class _Recipient(typ.NamedTuple):
    """The routing information encoded into a recipient address.

    Attributes:
        key: An index into the dictionary of senders.
        notify_type: The type of notification to send.
    """
    key: _Key
    notify_type: apprise.NotifyType


def _parsercpt(addr: str) -> _Recipient:
    _, rcpt = parseaddr(addr)
    user, domain = _parseaddrparts(rcpt)
    if not user or not domain:
        raise ValueError
    match = re.search(
        r'(.*)\.(info|success|warning|failure)$', user, re.IGNORECASE)
    ntype = apprise.NotifyType.INFO
    if match is not None:
        user = match.group(1)
        ntypes = match.group(2)
        if ntypes == 'info':
            pass
        elif ntypes == 'success':
            ntype = apprise.NotifyType.SUCCESS
        elif ntypes == 'warning':
            ntype = apprise.NotifyType.WARNING
        elif ntypes == 'failure':
            ntype = apprise.NotifyType.FAILURE
    return _Recipient(key=_Key(user=user, domain=domain.lower()), notify_type=ntype)


def _parseaddrparts(email: str) -> typ.Tuple[str, str]:
    """Parses an email address into its component user and domain parts."""
    match = re.search(r'(?:"([^"@]*)"|([^@]*))@([^@]*)$', email)
    if match is None:
        return '', ''
    quoted = match.group(1) is not None
    user = match.group(1) if quoted else match.group(2)
    domain = match.group(3)
    return user, domain


class _SimpleSender(typ.NamedTuple):
    """A configured target for Apprise notifications.

    Attributes:
        config_yaml: The YAML configuration for Apprise.
        title_template: The template string for notification title texts.
        body_template: The template string for notification body texts.
        body_format: The content type for notifications. If None, this will be
            auto-detected from the body parts of emails.
        body_pattern: A regular expression where text in the email body that
            matches this pattern will be used as the $body variable for
            body_template.

    """
    config_yaml: str
    title_template: Template
    body_template: Template
    body_format: typ.Optional[apprise.NotifyFormat]
    body_pattern: typ.Optional[str]


class SimpleRouter(r.Router):  # pylint: disable=too-few-public-methods
    """A router that uses the rules in the YAML configuration file.

    Attributes:
        senders: A list of notification targets, each with a [key, sender]
            tuple, where key contains username and domain patterns that can be
            matched by fnmatch and sender is the Sender instance itself.
    """
    senders: typ.List[typ.Tuple[_Key, _SimpleSender]]

    def __init__(self, senders: typ.List[typ.Tuple[_Key, _SimpleSender]]):
        super().__init__()
        self.senders = senders

    async def email_to_apprise(self, logger: Logger, email: r.EmailMessage) \
            -> typ.AsyncGenerator[r.AppriseNotification, None]:
        for addr in email.to:
            try:
                rcpt = _parsercpt(addr)
            except ValueError:
                logger.error('Not a valid Mailrise address: %s', addr)
                continue
            sender = self.get_sender(rcpt.key)
            if sender is None:
                logger.error('Recipient is not configured: %s', addr)
                continue

            email_body = email.body

            if sender.body_pattern is not None:
                matched_body = re.search(sender.body_pattern, email_body, re.IGNORECASE | re.MULTILINE)
                if matched_body is None:
                    raise ValueError("No matches found for pattern: " + sender.body_pattern)
                email_body = matched_body.group(0)

            mapping = {
                'subject': email.subject,
                'from': email.from_,
                'body': email_body,
                'to': str(rcpt.key),
                'config': rcpt.key.as_configured(),
                'type': rcpt.notify_type
            }
            yield r.AppriseNotification(
                config=sender.config_yaml,
                config_format='yaml',
                title=sender.title_template.safe_substitute(mapping),
                body=sender.body_template.safe_substitute(mapping),
                # Use the configuration body format if specified.
                body_format=sender.body_format or email.body_format,
                notify_type=rcpt.notify_type,
                attachments=email.attachments
            )

    def get_sender(self, key: _Key) -> _SimpleSender | None:
        """Find a sender by recipient key."""
        return next(
            (sender for (pattern_key, sender) in self.senders
             if fnmatchcase(key.user, pattern_key.user)
             and fnmatchcase(key.domain, pattern_key.domain)), None)


def load_from_yaml(logger: Logger, configs_node: dict[str, typ.Any]) -> SimpleRouter:
    """Load a simple router from the YAML configs node."""
    if not isinstance(configs_node, dict):
        raise r.ConfigFileError("'configs' node not a mapping")
    router = SimpleRouter(
        senders=[(_parse_simple_key(key), _load_simple_sender(config))
                 for key, config in configs_node.items()]
    )
    if len(router.senders) < 1:
        raise r.ConfigFileError('no Apprise targets configured')
    logger.info('Loaded configuration with %d recipient(s)', len(router.senders))
    return router


def _parse_simple_key(key: str) -> _Key:
    def err():
        return r.ConfigFileError(f"invalid config key '{key}'; should be a string or "
                                 "an email address without periods in the username")
    if '@' in key:
        user, domain = _parseaddrparts(key)
        if not user or not domain or '.' in user:
            raise err()
        return _Key(user=user, domain=domain.lower())
    if '.' in key:
        raise err()

    return _Key(user=key)


def _load_simple_sender(config: dict[str, typ.Any]) -> _SimpleSender:
    if not isinstance(config, dict):
        raise r.ConfigFileError("apprise config node not a mapping")

    # Extract Mailrise-specific values.
    mr_config = config.get('mailrise', {})
    config.pop('mailrise', None)
    title_template = mr_config.get('title_template', '$subject ($from)')
    body_template = mr_config.get('body_template', '$body')
    body_format = mr_config.get('body_format', None)
    body_pattern = mr_config.get('body_pattern', None)
    if not any(body_format == c for c in (None,
                                          apprise.NotifyFormat.TEXT,
                                          apprise.NotifyFormat.HTML,
                                          apprise.NotifyFormat.MARKDOWN)):
        raise r.ConfigFileError(f"invalid apprise notification format: {body_format}")

    return _SimpleSender(
        config_yaml=yaml.safe_dump(config),
        title_template=Template(title_template),
        body_template=Template(body_template),
        body_format=body_format,
        body_pattern=body_pattern
    )
