******
Design
******

The *Account Dunning Email Module* extends the following concepts:

.. _model-account.dunning.level:

Dunning Level
=============

The *Dunning Level* is extended with the ability to send an email when the
*Dunning Level* is processed.
The email is based on a `Report <trytond:model-ir.action.report>` that uses the
`Dunning <account_dunning:model-account.dunning>` record in the template.

.. seealso::

   The `Dunning Level <account_dunning:model-account.dunning.level>` concept is
   introduced by the :doc:`Account Dunning Module <account_dunning:index>`.

.. _model-account.configuration:

Account Configuration
=====================

When the *Account Dunning Email Module* is activated, a fall-back `User
<trytond:model-res.user>` can be set in the *Account Configuration*.
The dunning emails will be sent to this *User* if no other e-mail is found.

.. seealso::

   The `Account Configuration <account:model-account.configuration>` concept is
   introduced by the :doc:`Account Module <account:index>`.
