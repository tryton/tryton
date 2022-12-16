******
Design
******

The *Sale Blanket Agreement Module* introduces the following concepts:

.. _model-sale.blanket_agreement:

Sale Blanket Agreement
======================

The *Sale Blanket Agreement* is used to manage the agreements between
the company and its customers.

Each agreement progresses through multiple states: 'draft' as default when
created, 'running' when operational then 'done' or 'cancelled' as final step.
A warning is displayed if the user tries to close an agreement with remaining
quantities.

An agreement is identified by a unique number that is generated automatically
from the configured *Sequence* and may also have other general information such
a validity period, a description, or a reference provided by the customer.

Each agreement is made up from one or more lines.
Each line on an agreement provides information about which `Products
<product:concept-product>`, the price, the agreed quantity, the processed
quantity and the remaining quantity.

.. seealso::

   Sale Blanket Agreements can be found by opening the main menu item:

      |Sales --> Blanket Agreements|__ menu item.

      .. |Sales --> Blanket Agreements| replace:: :menuselection:`Sales --> Blanket Agreements`
      __ https://demo.tryton.org/model/sale.blanket_agreement

Wizard
------

.. _wizard-sale.blanket_agreement.create_sale_wizard:

Create Sale
^^^^^^^^^^^

The *Create Sale* wizard helps the user to create a sale from an blanket
agreement.
A specific form allows the user to select the blanket agreement lines that will
compose the sale with their remaining quantities.
