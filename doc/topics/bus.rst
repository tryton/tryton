.. _topics-notification:

=====================
Sending notifications
=====================

Tryton embeds a bus system allowing the system to send text messages to clients
logged in the system.

It allows the server to warn quickly the client user about some events using
the :meth:`trytond.bus.notify` function. Sending the notifications is done in a
transactional way and will occur at then end of the transaction.

For example, we warn the user of low stock level when selecting a product::

    from trytond.bus import notify

    class SaleLine:
        __name__ = 'sale.line'

        def on_change_product(self):
            super().on_change_product()

            # compute the product current stock
            stock = …

            if stock < 0:
                notify('Not enough stock', priority=3)
