.. _ref-sendmail:
.. module:: trytond.sendmail

========
Sendmail
========

.. method:: sendmail_transactional(from_addr, to_addrs, msg[, transaction[, datamanager]])

Send email message only if the current transaction is successfully committed.
The required arguments are an `RFC 822`_ from-address string, a list of `RFC
822`_ to-address strings (a bare string will be treated as a list with 1
address), and an email message.
The caller may pass a :class:`Transaction` instance to join otherwise the
current one will be joined. A specific data manager can be specified otherwise
the default :class:`SMTPDataManager` will be used for sending email.

.. warning::

    An SMTP failure will be only logged without raising any exception.

.. method:: sendmail(from_addr, to_addrs, msg[, server])

Send email message like :meth:`sendmail_transactional` but directly without
caring about the transaction.
The caller may pass a server instance from `smtplib`_.

.. method:: get_smtp_server([uri[, strict]])

Return a SMTP instance from `smtplib`_ using the `uri` or the one defined in
the `email` section of the :ref:`configuration <topics-configuration>`.
If strict is `True`, an exception is raised if it is not possible to connect to
the server.


.. class:: SMTPDataManager([uri[, strict]])

A :class:`SMTPDataManager` implements a data manager which send queued email at
commit. An option optional `uri` can be passed to configure the SMTP connection.
If strict is `True`, the data manager prevents the transaction if it fails to
send the emails.

.. method:: SMTPDataManager.put(from_addr, to_addrs, msg)

    Queue the email message to send.

.. _`RFC 822`: https://tools.ietf.org/html/rfc822.html
.. _`smtplib`: https://docs.python.org/2/library/smtplib.html
