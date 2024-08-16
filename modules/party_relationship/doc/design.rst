******
Design
******

The *Party Relationship Module* introduces or extends the following concepts:

.. _model-party.relation.type:

Relation Type
=============

The *Relation Types* qualify the relation between two `Parties
<party:model-party.party>`.
An other *Relation Type* can be set to automatically create the
:guilabel:`Reverse Relation`.

.. note::
   The same *Relation Type* can be set as the reverse relation.

The :guilabel:`Usages` property can be set to limit the types when calculating
the distance between parties.

.. seealso::

   The *Relation Types* can be found by opening the main menu item:

   |Parties --> Configuration --> Relation Types|__

   .. |Parties --> Configuration --> Relation Types| replace:: :menuselection:`Parties --> Configuration --> Relation Types`
   __ https://demo.tryton.org/model/party.relation.type

.. _model-party.party:

Party
=====

When the *Party Relationship Module* is activated, the *Party* gains a new
property to store the relations with other parties.
The relations can be active only for a period of dates.

The calculation of the :guilabel:`Distance` property is extended to count the
number of relations separating the party from the contextual ``related_party``
key.

.. note::
   The *Relation Types* taking into account to compute the distance can be
   limited with the contextual ``relation_usages`` key.

.. seealso::

   The `Party <party:model-party.party>` concept is introduced by the
   :doc:`Party Module <party:index>`.
