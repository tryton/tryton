Sale Payment Module
###################

The sale_payment module extends *Sale* to allow payments prior to the creation
of any invoice.

A field *Payments* is added on the sale which can be filled in quotation state.
The sale can not be reset to draft or cancelled if there are no failed payment
linked.

The payment authorization of the full sale amount is used as confirmation of
the sale.

When an invoice from a sale is posted, its payments are used to pay invoice's
*Lines to Pay*.
