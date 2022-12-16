******
Design
******

The *Purchase Blanket Agreement Module* introduces the following concepts:

.. _model-purchase.blanket_agreement:

Purchase Blanket Agreement
==========================

The *Purchase Blanket Agreement* is used to manage the agreements between the
`Company <company:model-company.company>` and its suppliers.

Each agreement progresses through multiple states: 'draft' as default when
created, 'running' when operational then 'done' or 'cancelled' as final step.
A warning is displayed if the user tries to close an agreement with remaining
quantities.

An agreement is identified by a unique number that is generated automatically
from the configured *Sequence* and may also have other general information such
a validity period, a description, or a reference provided by the supplier.

Each agreement is made up from one or more lines.
Each line on an agreement provides information about which `Product
<product:concept-product>`, the price, the agreed quantity, the processed
quantity and the remaining quantity.

.. seealso::

   Purchase Blanket Agreements can be found by opening the main menu item:

      |Purchases --> Blanket Agreements|__ menu item.

      .. |Purchases --> Blanket Agreements| replace:: :menuselection:`Purchases --> Blanket Agreements`
      __ https://demo.tryton.org/model/purchase.blanket_agreement

Wizard
------

.. _wizard-purchase.blanket_agreement.create_purchase:

Create Purchase
^^^^^^^^^^^^^^^

The *Create Purchase* wizard helps the user to create a purchase from an
blanket agreement.
A specific form allows the user to select the blanket agreement lines that will
compose the purchase with their remaining quantities.
