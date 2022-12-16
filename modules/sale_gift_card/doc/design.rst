******
Design
******

The *Sale Gift Card Module* introduces or extends the following concepts.

.. _concept-product:

Product
=======

When the *Sale Gift Card Module* is activated, services and goods can be
defined as gift cards.

.. seealso::

   The `Product <product:concept-product>` concept is introduced by the
   :doc:`Product Module <product:index>`.

.. _model-sale.gift_card:

Gift Card
=========

The *Gift Card* concept stores the unique number and value for each gift card.

.. seealso::

   Gift cards can be seen by opening the main menu item:

      |Sales --> Gift Cards|__

      .. |Sales --> Gift Cards| replace:: :menuselection:`Sales --> Gift Cards`
      __ https://demo.tryton.org/model/sale.gift_card

.. _model-sale.sale:

Sale
====

The *Sale* concept is extended to allow `Gift Cards <model-sale.gift_card>`
presented by customers to be redeemed.
On quotation these gift cards are deducted from the total.

For *Sale Lines* that are for gift cards represented by service products an
optional email address can be provided.
This email address is then used to send the gift card to the customer by email.

.. seealso::

   The `Sale <sale:model-sale.sale>` concept is introduced by the :doc:`Sale
   Module <sale:index>`.


.. _model-stock.move:

Stock Move
==========

The *Stock Move* concept is extended to record the `Gift Cards
<model-sale.gift_card>` shipped to customers.


.. seealso::

   The `Move <stock:model-stock.move>` concept is introduced by the :doc:`Stock
   Module <stock:index>`.
