Sale Module
###########

The sale module defines the Sale model.


Sale
****

The sale is mainly defined by a party to which the products will be
sold and a list of sale lines, each one containing a product and a
quantity. Here is the extensive list of the fields, most of them are
optional or completed with sensible default values:

- Party: The customer.
- Invoice Address: The invoice address of the customer.
- Shipment Party: An optional different party where the shipment will be sent.
- Shipment Address: The address where the shipment will be sent.
- Description: An optional description for the order.
- Reference: The internal reference of the sale (will be generated
  automatically on confirmation).
- Sale Date: The date the sale is made.
- Payment Term: Define which payment term will be use for the future
  invoice.
- Warehouse: Define the warehouse from which the goods will be sent.
- Currency: define the currency to use for this sale. All product
  prices will be computed accordingly.
- Sale Lines:

  - Type: The type of the line. The default value is *Line* which
    means that the current sale line contains the fields defined
    hereunder. The other values of Type (*Comment*, *Subtotal*,
    *Title*) are used to add extra lines that will appear on the
    report, thus allowing to easily customise it.
  - Sequence: Allow to order lines. The value of this field is also
    updated with a drag and drop between the lines.
  - Product: An optional reference to the product to sale.
  - Description: The description of the product to sale.
  - Quantity: The quantity to sale.
  - Unit: The unit of measure in which is expressed the quantity.
  - Unit Price: The unit price of the product expressed in the
    currency of the sale.
  - Amount: The amount of the current line (Unit Price multiplied by
    Quantity).
  - Taxes: The list of taxes that will be applied to the current line.

- Invoice State: The state of the invoice related to the sale.
- Shipment State: The state of the shipment related to the sale.
- Untaxed: The untaxed amount.
- Tax: The tax amount.
- Total: The total amount.
- State: The state of the sale. May take one of the following
  values: Draft, Quotation, Confirmed, Processing, Cancelled.
- Company: The company which issue the sale order.
- Invoice Method: May take one of the following values:

  - On Order Processed: The invoice is created when the sale order is
    processed.
  - On Shipment Sent: The invoice is created when the shipment is sent
    and will contains the shipped quantities. If there are several
    shipments for the same sale, several invoices will be created.
  - Manual: Tryton doesn't create any invoice automatically.

- Shipment Method: May take one of the following values:

  - On Order Processed: The customer shipment is created when the sale
    order is processed.
  - On Invoice Paid: The customer shipment is created when the invoice
    is paid.
  - Manual: Tryton doesn't create any shipment automatically.

  One should note that choosing *On Shipment Sent* for the Invoice
  Method and *On Invoice Paid* for the Shipment Method is an invalid
  combination.

- Comments: A text fields to add custom comments.
- Invoices: The list of related invoices.
- Moves: The list of related stock moves.
- Shipments: The list of related shipments.
- Return Shipments: The list of related shipments return.

The *Sale* report allow to print the sale orders or to send
them by mail.
