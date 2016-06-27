Web User Module
###############

The web_user module provides facilities to manage external user accessing from
the web.

User
****

A user is uniquely identified by an email and he is authenticated using a
hashed password. The user can be linked to a Party.

Two actions are available:

- The *Validate E-mail* which sent an e-mail to the user with a link to an URL
  that ensures the address exists.
- The *Reset Password* which sent an e-mail to the user with a link to an URL
  to set a new password.

Configuration
*************

The web_user module uses parameters from different sections:

- `web`:

    - `reset_password_url`: the URL to reset the password to which the
      parameters `email` and `token` will be added.

    - `email_validation_url`: the URL for email validation to which the
      parameter `token` will be added.

- `email`:

    - `from`: the origin address to send emails.

- `session`:

    - `web_timeout`: defines in seconds the validity of the web session.
      Default: 30 days.

    - `web_timeout_reset`: in seconds the validity of the reset password token.
      Default: 1 day.
