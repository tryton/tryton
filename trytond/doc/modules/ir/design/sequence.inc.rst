.. _model-ir.sequence:

Sequence
========

The *Sequence* defines the properties to generate unique and sequential strings
with numbers.
A prefix and suffix can be added to the generated sequence string.
These support formatting that can include the current `Date <model-ir.date>`.

.. seealso::

   The Sequences can be found by opening the main menu item:

      |Administration --> Sequences --> Sequences|__

      .. |Administration --> Sequences --> Sequences| replace:: :menuselection:`Administration --> Sequences --> Sequences`
      __ https://demo.tryton.org/model/ir.sequence

.. _model.ir.sequence.strict:

Sequence Strict
===============

The *Sequence Strict* is similar to the `Sequence <model-ir.sequence>` but it
prevents any gaps in the generated numbers.

.. seealso::

   The Sequences Strict can be found by opening the main menu item:

      |Administration --> Sequences --> Sequences Strict|__

      .. |Administration --> Sequences --> Sequences Strict| replace:: :menuselection:`Administration --> Sequences --> Sequences Strict`
      __ https://demo.tryton.org/model/ir.sequence.strict

.. _model-ir.sequence.type:

Sequence Type
=============

The *Sequence Type* is used to categorize the `Sequences <model-ir.sequence>`
and defines the `Groups <model-res.group>` allowed to edit them.

.. seealso::

   The Sequence Types can be found by opening the main menu item:

      |Administration --> Sequences --> Types|__

      .. |Administration --> Sequences --> Types| replace:: :menuselection:`Administration --> Sequences --> Types`
      __ https://demo.tryton.org/model/ir.sequence.type
