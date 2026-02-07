******
Design
******

The stock package module introduces or extends the following concepts.

.. _model-stock.package:

Package
=======

A *package* represents a physical container that groups `stock moves
<stock:model-stock.move>` from the same `shipment
<stock:concept-stock.shipment>`.
The packages are numbered using the `sequence <trytond:model-ir.sequence>` set
in the `Stock Configuration <stock:model-stock.configuration>`.

Wizards
-------

.. _wizard-stock.package.pack:

Pack Package
^^^^^^^^^^^^

The *Pack Package* wizard is used to put a defined quantity of a selected
`stock move <stock:model-stock.move>` into a package.

.. _model-stock.package.type:

Package Type
============

A *Package Type* stores common properties of `packages <model-stock.package>`.

.. seealso::

   The package types can be found by opening the main menu item:

      |Inventory & Stock --> Configuration --> Package Types|__

      .. |Inventory & Stock --> Configuration --> Package Types| replace:: :menuselection:`Inventory & Stock --> Configuration --> Package Types`
      __ https://demo.tryton.org/model/stock.package.type

.. _concept-stock.shipment:

Shipment
========

When the *Stock Package Module* is activated, the `customer shipmment
<stock:model-stock.shipment.out>`, `supplier return shipment
<stock:model-stock.shipment.in.return>` and `internal shipment
<stock:model-stock.shipment.internal>` concepts gain properties to manage
`packages <model-stock.package>`.

Wizards
-------

.. _wizard-stock.shipment.pack:

Pack Shipment
^^^^^^^^^^^^^

The *Pack Shipment* wizard is used to create `package <model-stock.package>`
for a shipment.
The created package can be put inside another package or can include other
packages.
