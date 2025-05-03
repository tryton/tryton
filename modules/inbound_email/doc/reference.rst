*************
API Reference
*************

.. _Post inbound email:

Post inbound email
==================

The *Inbound Email Module* defines a route for each `Inbox <model-inbound.email.inbox>`:

   - ``POST`` ``/<database_name>/inbound_email/inbox/<identifier>``:
     Create an `Email <model-inbound.email>` for the identified inbox using the
     data of the request.

     The request parameter ``type`` define which data type to apply by default
     it is ``raw`` which expect the bytes of a :rfc:`822` message.

     Other available types:

     * ``mailchimp`` for `Mailchimp
       <https://mailchimp.com/developer/transactional/guides/set-up-inbound-email-processing/>`_.

     * ``mailpace`` for `MailPace <https://docs.mailpace.com/guide/inbound>`_.

     * ``postmark`` for `Postmark
       <https://postmarkapp.com/developer/user-guide/inbound/inbound-domain-forwarding>`_.

     * ``sendgrid`` for `SendGrid
       <https://docs.sendgrid.com/for-developers/parsing-email/setting-up-the-inbound-parse-webhook>`_.
       :guilabel:`Send Raw` must be checked.
