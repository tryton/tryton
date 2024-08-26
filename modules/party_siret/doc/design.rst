******
Design
******

The *Party SIRET Module* extends the following concepts:

.. _model-party.party:

Party
=====

When the *Party SIRET Module* is activated, parties gain a property that
calculates the `SIREN code <https://en.wikipedia.org/wiki/SIREN_code>`_ based
on the `Identifier <party:model-party.identifier>` with the type
:guilabel:`French Company Identification Number`.

.. seealso::

   The `Party <party:model-party.party>` concept is introduced by the
   :doc:`Party Module <party:index>`.

.. _model-party.address:

Address
=======

When the *Party SIRET Module* is activated, addresses gain a property that
calculates the `SIRET code <https://en.wikipedia.org/wiki/SIRET_code>`_ based
on the `Identifier <party:model-party.identifier>` with the type
:guilabel:`French Company Establishment Identification Number`.

.. seealso::

   The `Address <party:model-party.address>` concept is introduced by the
   :doc:`Party Module <party:index>`.
