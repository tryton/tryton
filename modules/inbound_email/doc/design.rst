******
Design
******

The *Inbound Email Module* introduces the following concepts:

.. _model-inbound.email.inbox:

Inbox
=====

The *Inbox* contains the endpoint and the rules that defines which action to
apply on received email.

The rules define the criteria like the destination email or the subject of the
email for which the action must be run.


.. seealso::

   Inboxes can be found by opening the main menu item:

      |Administration --> Inbound Email --> Inbox|__

      .. |Administration --> Inbound Email --> Inbox| replace:: :menuselection:`Administration --> Inbound Email --> Inbox`
      __ https://demo.tryton.org/model/inbound.email.inbox

.. _model-inbound.email:

Email
=====

The *Email* stores the email received by the endpoint.

It stores also the rule and the result of the action.

If no rule has matched, the process can be applied again until a rule matches.
