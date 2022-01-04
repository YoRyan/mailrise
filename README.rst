.. image:: https://raw.githubusercontent.com/YoRyan/mailrise/main/src/mailrise/asset/mailrise-logo.png
  :alt: Mailrise logo


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
notification services supported by Apprise, from Matrix to Nextcloud to your
desktop or mobile device.

Just as email brought written messages into the 21st century, Mailrise
brings email notifications into the year 2021 and beyond. Compared to a
conventional SMTP server, it's more secure, too—no more replicating your Gmail
password to each of your Linux boxes!

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

As a Docker container
---------------------

An official Docker image is available
`from Docker Hub <https://hub.docker.com/r/yoryan/mailrise>`_. To use it, you
must bind mount a configuration file to ``/etc/mailrise.conf``.

From PyPI
---------

You can find Mailrise `on PyPI <https://pypi.org/project/mailrise/>`_.

Once installed, you should write a configuration file and then configure Mailrise
to run as a service. Here is the suggested systemd unit file::

    [Unit]
    Description=Mailrise SMTP notification relay
    
    [Service]
    ExecStart=/usr/local/bin/mailrise /etc/mailrise.conf
    
    [Install]
    WantedBy=multi-user.target

From source
-----------

This repository is structured like any other Python package. To install it in
editable mode for development or debugging purposes, use::

    pip install -e .

To build a wheel, use::

    tox -e build

Configuration
=============

The ``mailrise`` program accepts a path to a YAML configuration file that
encapsulates the daemon's entire configuration. The root node of this file should
be a dictionary. Mailrise accepts the following keys (periods denote
sub-dictionaries):

====================================== ========== ==========================================================================
Key                                    Type       Value
====================================== ========== ==========================================================================
configs.<name>                         dictionary ``<name>`` denotes the name of the configuration. It must *not* contain a
                                                  period. Senders select this configuration by addressing their emails to
                                                  ``<name>@mailrise.xyz``.
