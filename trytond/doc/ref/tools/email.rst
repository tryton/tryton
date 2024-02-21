.. _ref-tools-email_:
.. module:: trytond.tools.email_

Email
=====

.. function:: set_from_header(message, sender, from\_)

   Fill email headers to appear at best from the address.

.. function:: has_rcpt(message)

   Return if the :py:class:`~email.message.Message` has any recipient.

.. function:: format_address(email[, name])

   Return a string suitable for an RFC 2822 From, To or Cc header.

.. function:: validate_email(email)

   Validate the email address.

.. function:: normalize_email(email)

   Return the email address normalized.

.. function:: convert_ascii_email(email):

   Return the equivalent email address in ASCII.
