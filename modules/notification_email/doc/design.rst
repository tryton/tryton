******
Design
******

The *Notification Email Module* introduces the following concepts:

.. _model-notification.email:

Notification Email
==================

A *Notification Email* defines when and to whom emails should to be sent
automatically.
The content of an email is based on a report which defines also the
:class:`~trytond:trytond.model.ModelStorage` that will be the source.
The recipients are defined as field from this model or using a :ref:`user
<trytond:model-res.user>`.
The triggers specify the events and conditions that will trigger the sending of
the email.

.. seealso::

   Notification Emails can be found by opening the main menu item:

      |Administration --> Models --> Notification Emails|__

      .. |Administration --> Models --> Notification Emails| replace:: :menuselection:`Administration --> Models --> Notification Emails`
      __ https://demo.tryton.org/model/notification.email
