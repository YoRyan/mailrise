=========
Changelog
=========

Version 1.3.0
=============

:Date: December 26, 2022

- FIX: Docker image not responding to stop signal
- Upgrade to Apprise v1.2.0
- Upgrade to aiosmtpd v1.4.3, which fixes broken STARTTLS
- Add support for multipart messages produced by Blue Iris
- Add basic authentication
- Add config name wildcarding with fnmatch
- Add more logging messages (-v/-vv) to ease troubleshooting
- Add !env_var directive to read configuration data from environment variables

Version 1.2.1
=============

:Date: February 5, 2022

- Upgrade to Apprise v0.9.7, which, notably, now converts HTML markup to plain text for notifications

Version 1.2.0
=============

:Date: August 28, 2021

- Add the ability to use a full email address as a sender target
- Upgrade to Apprise v0.9.4

Version 1.1.0
=============

:Date: July 16, 2021

- Add customizable template strings for the notification title and body

Version 1.0.1
=============

:Date: June 30, 2021

- FIX: Custom icons not working

Version 1.0.0
=============

:Date: June 30, 2021

- The first public release!
- Based on Apprise v0.9.3