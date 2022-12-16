.. _model-stock.move:

Move
====

In Tryton a stock *Move* represents the transfer of a given amount of a
`Product <concept-product>` between two different
`Stock Locations <model-stock.location>`.
Often stock moves will be grouped together into a
`Shipment <concept-stock.shipment>`.

.. note::

   Service products have no physical presence, so are not available for
   use in stock moves.

A stock move has some properties that record the planned date for the stock
move and also its effective date, which is when the move actually happened.

Some stock moves are also associated with unit and cost prices.
These allow the value of stock to be calculated at any time, and for products'
cost prices to be updated based on the stock moves.

Each `Company <company:model-company.company>` has its own stock moves which
are kept separate from other company's stock moves.

.. seealso::

   The stock moves can be listed by opening the main menu item:

      |Inventory & Stock --> Moves|__

      .. |Inventory & Stock --> Moves| replace:: :menuselection:`Inventory & Stock --> Moves`
      __ https://demo.tryton.org/model/stock.move

.. _concept-stock.move.assign:

Assign Concept
--------------

A stock move is assigned when the stock for the stock move has been found
and reserved and cannot be assigned by any other stock move.

When attempting to assign a stock move Tryton looks at the stock move's source
locations and their sub-locations, and searches for the stock that is needed
to complete the stock moves.
If stock is found then the source location of the stock move is changed,
or the stock move is split up into several stock moves, each of which may
take stock from a different sub-location.

If there is not enough stock available to fully assign the stock move then the
remainder is left in a stock move that is not assigned.

.. note::

   Consumable products always get assigned even when there is not enough
   stock available for the stock move.
   This is the key difference between goods and consumable products.
