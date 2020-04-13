Sale Supply Production Module
#############################

The Sale Supply Production module adds a "supply on sale" option to producible
products.
If checked, it will generate a production request for each sale line of this
product regardless of the stock levels. Once the products are produced they are
assigned to the customer shipments.
If the production request is cancelled, the sale goes back to the default
supply method.

.. warning::
    If the shiment method is *On Invoice Paid*, the production request will be
    created only when all the invoice lines are paid.
..
