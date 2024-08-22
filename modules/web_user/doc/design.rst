******
Design
******

The *Web User Module* introduces some new concepts.

.. _model-web.user:

Web User
========

The *Web User* concept stores the details of user accounts for people who
interact with Tryton from a website.
Each user is identified by their email address which must be unique.
The email address is used when logging a user in, along with other
authentication information, such as their password.

Users can be linked to a `Party <party:model-party.party>` which represents the
user in the system.
They may also have a list of `Secondary Parties <party:model-party.party>` in
the name of which the user may also operate as.

.. seealso::

   A list of web users is found by opening the main menu item:

      |Administration --> Users --> Web Users|__

      .. |Administration --> Users --> Web Users| replace:: :menuselection:`Administration --> Users --> Web Users`
      __ https://demo.tryton.org/model/web.user

Reports
-------

.. _report-web.user.email_validation:

Email Validation
^^^^^^^^^^^^^^^^

The *Email Validation* report provides the contents of the email that is sent
to `Web Users <model-web.user>` when validation of a user's email address is
required.
It contains a link the user can click on to confirm that the email address is
actually valid.

.. _report-web.user.email_reset_password:

Email Reset Password
^^^^^^^^^^^^^^^^^^^^

The *Email Reset Password* report provides the contents of the email that is
sent to `Web Users <model-web.user>` when a request to reset their password is
received.
It provides information about how they can go about setting a new password.
