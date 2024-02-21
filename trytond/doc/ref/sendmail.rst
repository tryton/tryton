.. _ref-sendmail:
.. module:: trytond.sendmail

Sendmail
========

.. function:: sendmail_transactional(from_addr, to_addrs, msg[, transaction[, datamanager[, strict]]])

   Send email message only if the current transaction is successfully committed.

   The required arguments are an :rfc:`5322` from-address string, a list of
   :rfc:`5322` to-address strings (a bare string is treated as a list with 1
   address), and an :py:class:`email.message.Message`.
   The caller may pass a :class:`~trytond.transaction.Transaction` instance to
   join otherwise the current one is joined.
   A specific data manager can be specified otherwise the default
   :class:`SMTPDataManager` is used for sending email.
   The strict value is passed to instantiate the default :class:`SMTPDataManager`.

   .. warning::

      An SMTP failure is only logged without raising any exception.

.. function:: send_message_transactional(msg[, from_addr[, to_addrs[, transaction[, datamanager[, strict]]]]])

   It is a convenience method for calling :func:`sendmail_transactional`.
   If ``from_addr`` is ``None`` or ``to_addrs`` is ``None``, if fills those
   arguments with addresses extracted from the headers of ``msg``.

.. function:: sendmail(from_addr, to_addrs, msg[, server[, strict]])

   Send email message like :meth:`sendmail_transactional` but directly without
   caring about the transaction and return the ``server``.

   The caller may pass a server instance from `smtplib`_.
   It may return a new server instance if a reconnection was needed and if the
   instance comes from :meth:`get_smtp_server`.
   If strict is ``True``, an exception is raised if it is not possible to
   connect to the server.

.. function:: send_message(msg[, from_addr[, to_addrs[, server[, strict]]]])

   Same convenience method as :func:`send_message_transactional` but for
   calling :func:`sendmail`.

.. function:: get_smtp_server([uri[, strict]])

   Return a SMTP instance from `smtplib`_ using the ``uri`` or the one defined
   in the ``email`` section of the :ref:`configuration <topics-configuration>`.
   If strict is ``True``, an exception is raised if it is not possible to
   connect to the server.


.. class:: SMTPDataManager([uri[, strict]])

   Implement a data manager which send queued email at commit.

   An option optional ``uri`` can be passed to configure the SMTP connection.
   If strict is ``True``, the data manager prevents the transaction if it fails
   to send the emails.

.. method:: SMTPDataManager.put(from_addr, to_addrs, msg)

   Queue the email message to send.

.. _`smtplib`: https://docs.python.org/2/library/smtplib.html
