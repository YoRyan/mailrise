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

Mailrise offers the ability to encrypt any received SMTP message using the cryptography 
library. No matter what receiving service from Apprise notification service, any SMTP 
message can encrypt. Mailrise offers a decryption companion to allow message decryption. 
The decrypt.html is editable for a different look.

A sample_mailrise.yaml file is in the root directory. This file can be renamed to 
mailrise.yaml and edited.

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

=============================================== ========== ==========================================================================
Key                                             Type       Value
=============================================== ========== ==========================================================================
configs.<name>                                  dictionary ``<name>`` denotes the name of the configuration. It must *not* contain a
                                                           period. Senders select this configuration by addressing their emails to
                                                           ``<name>@mailrise.xyz``.

                                                           It is also possible to use a full email address, such as
                                                           ``mail@example.com``, as a name, in which case senders must use the entire
                                                           address as their recipient address to select this configuration.

                                                           The dictionary value is the Apprise
                                                           `YAML configuration <https://github.com/caronc/apprise/wiki/config_yaml>`_
                                                           itself, exactly as it would be specified in a standalone file for Apprise.

                                                           In addition to the Apprise configuration, some Mailrise-exclusive options
                                                           can be specified under this key. See the ``mailrise`` options below.
configs.<name>.mailrise.title_template          string     The template string used to create notification titles. See "Template
                                                           strings" below.

                                                           Defaults to ``$subject ($from)``.
configs.<name>.mailrise.body_template           string     The template string used to create notification body texts. See "Template
                                                           strings" below.

                                                           Defaults to ``$body``.
configs.<name>.mailrise.body_format             string     Sets the data type for notification body texts. Must be ``text``,
                                                           ``html``, or ``markdown``. Apprise
                                                           `uses <https://github.com/caronc/apprise/wiki/Development_API#notify--send-notifications>`_
                                                           this information to determine whether or not the upstream notification
                                                           service can handle the provided content.

														   If not specified here, the data type is inferred from the body part of the
                                                           email message. So if you have your body template set to anything but the
                                                           default value of ``$body``, you might want to set a data type here.
configs.<name>.mailrise.html_conversion         string     The HTML conversion string is used to convert HTML messages to text format. The original 
                                                           formatting is kept the best it can be when converting.

                                                           Defaults to ``None``.
configs.<name>.mailrise.send_message_encrypted    bool     The HTML conversion string is used to convert HTML messages to text format. The original 
                                                           formatting is kept the best it can be when converting.
                                                           
                                                           Defaults to ``None``.
														   
listen.host                                     string     Specifies the network address to listen on.

                                                           Defaults to all interfaces.
listen.port                                     number     Specifies the network port to listen on.

                                                           Defaults to 8025.
listen.decryptor_companion_port                 number     Specifies the decryptor companion port to listen on.

                                                           Defaults to 5000.
tls.mode                                        string     Selects the operating mode for TLS encryption. Must be ``off``,
                                                           ``onconnect``, ``starttls``, or ``starttlsrequire``.

                                                           Defaults to off.
tls.certfile                                    string     If TLS is enabled, specifies the path to the certificate chain file. This
                                                           file must be unencrypted and in PEM format.
tls.keyfile                                     string     If TLS is enabled, specifies the path to the key file. This file must be
                                                           unencrypted and in PEM format.
smtp.hostname                                   string     Specifies the hostname used when responding to the EHLO command.

                                                           Defaults to the system FQDN.
encryption.encryption_password                  string     Specifies the encryption password used to encrypt the SMTP message.
                                                           
                                                           Defaults to ``None``.
encryption.encryption_random_salt               bytes      Specifies the encryption random salt used to encrypt the SMTP message.
                                                           
                                                           Defaults to ``None``.
website.enable_decryptor_companion              bool       Enables the decryptor companion website.
                                                           
                                                           Defaults to ``False``.
website.decryptor_companion_url                 string     The decryptor URL to listen on. This is used for the message link. Can use URL or hosted Mailrise host IP address.
                                                           
                                                           Defaults to ``None``.
=============================================== ========== ==========================================================================

.. _template-strings:

Template strings
----------------

You can use Python's `template strings
<https://docs.python.org/3/library/string.html#template-strings>`_ to specify
custom templates that Mailrise will construct your notifications from. Templates
make use of variables that communicate information about the email message. Use
dollar signs (``$``) to insert variables.

The following variables are available for both title and body templates:

========== ====================================================================================
Identifier Value
========== ====================================================================================
subject    The email subject.
from       The sender's full address.
body       The full contents of the email body.
to         The full email address of the selected Apprise configuration.
config     The name of the selected Apprise configuration, unless it uses a custom domain, in
           which case this is equivalent to the "to" variable.
type       The class of Apprise notification. This is "info", "success", "warning", or
           "failure".
========== ====================================================================================


.. _pyscaffold-notes:

Note
====

This project has been set up using PyScaffold 4.0.2. For details and usage
information on PyScaffold see https://pyscaffold.org/.
