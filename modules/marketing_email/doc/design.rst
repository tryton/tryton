******
Design
******

The *Marketing Email Module* introduces the following concepts:

.. _model-marketing.email:

Email
=====

The *Email* store the addresses subscribed to a `Mailing List <model-marketing.email.list>`.

.. seealso::

   The *Emails* can be found by opening the relate menu entry
   :guilabel:`Emails` from the `Mailing List <model-marketing.email.list>`.

Reports
-------

.. _report-marketing.email.subscribe:

Subscribe
^^^^^^^^^

The *Subscribe* report renders the :abbr:`HTML (Hypertext Markup Language)`
content of the email sent to confirm the subscription.

.. _report-marketing.email.unsubscribe:

Unsubscribe
^^^^^^^^^^^

The *Unsubscribe* report renders the :abbr:`HTML (Hypertext Markup Language)`
content of the email sent to confirm the unsubscription.

.. _model-marketing.email.list:

Mailing List
============

The *Mailing List* groups `Email <model-marketing.email>` addresses under a
name and a `Language <trytond:model-ir.lang>`.

.. seealso::

   The *Mailing Lists* can be found by opening the main menu item:

   |Marketing --> Mailing Lists|__

   .. |Marketing --> Mailing Lists| replace:: :menuselection:`Marketing --> Mailing Lists`
   __ https://demo.tryton.org/model/marketing.email.list

.. _model-marketing.email.message:

Message
=======

The *Message* stores the content and title of the emails to be sent to all the
addresses of a `Mailing List <model-marketing.email.list>`.

.. seealso::

   The *Messages* can be found by opening the relate menu entry
   :guilabel:`Messages` from the `Mailing List <model-marketing.email.list>`.

Wizards
-------

.. _wizard-marketing.email.send_test:

Send Test
^^^^^^^^^

The *Send Test* wizard allows to send the *Message* to a unique email address
from the mailing list for testing purpose.
