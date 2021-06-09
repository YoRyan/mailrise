========
mailrise
========


An SMTP gateway for Apprise notifications.


Description
===========

Mailrise is an SMTP server that converts the emails it receives into
`Apprise <https://github.com/caronc/apprise>`_ notifications.  The intended use
case is as an email relay for a home lab or network. By accepting ordinary
email, Mailrise enables Linux servers, Internet of Things devices, surveillance
systems, and outdated software to gain access to the full suite of 60+
notification services supported by Apprise.

A Mailrise daemon is configured with a list of Apprise
`configuration files <https://github.com/caronc/apprise/wiki/config_yaml>`_.
Email senders encode the name of the desired configuration file into the
recipient address. Mailrise then constructs the resulting Apprise
notification(s) using the selected configuration.

A minimalist Mailrise configuration, for example, might contain a single Apprise
configuration for Pushover::

    configs:
      pushover:
        urls:
          - pover://[...]

And email senders would be able to select this configuration by using the
recipient address::

    pushover@mailrise.xyz

It is also possible to specify one of the four Apprise
`notification types <https://github.com/caronc/apprise/wiki/Development_API#message-types-and-themes>`_::

    pushover.failure@mailrise.xyz

Email attachments will also pass through to Apprise if the addressed
notification service(s) support attachments.

Mailrise is the sucessor to
`SMTP Translator <https://github.com/YoRyan/smtp-translator>`_, a previous
project of mine that articulated a similar concept but was designed solely for
Pushover.


Installation
============

As a systemd service
--------------------

Here is the suggested systemd unit file::

    [Unit]
    Description=Mailrise SMTP notification relay
    
    [Service]
    ExecStart=/usr/local/bin/mailrise /etc/mailrise.conf
    
    [Install]
    WantedBy=multi-user.target


Configuration
=============

The ``mailrise`` program accepts a path to a YAML configuration file that
encapsulates the daemon's entire configuration. The root node of this file should
be a dictionary. Mailrise accepts the following keys (periods denote
sub-dictionaries):

============= ========== ========================================================
Key           Type       Value
============= ========== ========================================================
configs       dictionary Contains the Apprise configurations. The key is the
                         name of the configuration and the value is the
                         `YAML configuration <https://github.com/caronc/apprise/wiki/config_yaml>`_
                         itself, exactly as it would be specified in a standalone
                         file for Apprise.
listen.host   string     Specifies the network address to listen on.

                         Defaults to all interfaces.
listen.port   number     Specifies the network port to listen on.

                         Defaults to 8025.
tls.mode      string     Selects the operating mode for TLS encryption. Must be
                         ``off``, ``onconnect``, ``starttls``, or
                         ``starttlsrequire``.

                         Defaults to off.
tls.certfile  string     If TLS is enabled, specifies the path to the certificate
                         chain file. This file must be unencrypted and in PEM
                         format.
tls.keyfile   string     If TLS is enabled, specifies the path to the key file.
                         This file must be unencrypted and in PEM format.
smtp.hostname string     Specifies the hostname used in any SMTP EHLO replies.

                         Defaults to the system FQDN.
============= ========== ========================================================


.. _pyscaffold-notes:

Note
====

This project has been set up using PyScaffold 4.0.2. For details and usage
information on PyScaffold see https://pyscaffold.org/.
