Purchase Module
###############

The purchase module defines the Purchase model.


Purchase
********

The purchase is mainly defined by a party from which the products will
be purchased and a list of purchase lines, each one containing a
product and a quantity. Here is the extensive list of the fields, most
of them are optional or completed with sensible default values:

- Party: The supplier.
- Invoice Address: The invoice address of the supplier.
- Supplier Reference: Allow to keep track of the supplier reference
  for this order.
- Description: An optional description for the order.
- Number: The internal reference of the purchase (will be generated
  automatically on confirmation).
- Reference: The optional external reference of the order.
- Purchase Date: The date the purchase is made.
- Payment Term: Define which payment term will be use for the future
  invoice.
- Warehouse: Define the warehouse where the shipment will be made.
- Currency: define the currency to use for this purchase. All product
  prices will be computed accordingly.
- Purchase Lines:

  - Type: The type of the line. The default value is *Line* which
    means that the current purchase line contains the fields defined
    hereunder. The other values of Type (*Comment*, *Subtotal*,
    *Title*) are used to add extra lines that will appear on the
    report, thus allowing to easily customise it.
  - Sequence: Allow to order lines. The value of this field is also
    updated with a drag and drop between the lines.
  - Product: An optional reference to the product to purchase.
  - Description: The description of the product to purchase.
  - Quantity: The quantity to purchase.
  - Unit: The unit of measure in which is expressed the quantity.
  - Unit Price: The unit price of the product expressed in the
    currency of the purchase.
  - Amount: The amount of the current line (Unit Price multiplied by
    Quantity).
  - Delivery Date: The computed date at which the product is expected to be
    delivered.
  - Taxes: The list of taxes that will be applied to the current line.

- Invoice State: The state of the invoice related to the purchase.
- Shipment State: The state of the shipment related to the purchase.
- Untaxed: The untaxed amount.
- Tax: The tax amount.
- Total: The total amount.
- State: The state of the purchase. May take one of the following
  values: Draft, Quotation, Confirmed, Cancelled.
- Company: The company which issue the purchase order.
- Invoice Method: May take one of the following values:

  - Base on order: The invoice is created when the purchase order is confirmed.
  - Base on shipment: The invoice is created when the shipment is
    received and will contains the shipped quantities. If there are
    several shipments for the same purchase, several invoices will be
    created.
  - Manual: Tryton doesn't create any invoice automatically.

- Comments: A text fields to add custom comments.
- Invoices: The list of related invoices.
- Moves: The list of related stock moves.
- Shipments: The list of related shipments.
- Return Shipments: The list of the related shipment returns. If a Supplier
  Return location is defined on warehouse it will be used on return shipments
  as origin location. Otherwise the warehouse storage location will be used.

The *Purchase* report allow to print the purchase orders or to send
them by mail.
