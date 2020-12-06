Account Stock Continental Module
################################

The account_stock_continental module adds continental accounting model for
stock valuation.

A new configuration field for accounting is added:

- Journal Stock: The journal used for stock move.

Three new fields are added to Accounting categories:

- Account Stock: The account which is used to record stock value.
- Account Stock IN: The counter part account for incomming stock moves.
- Account Stock OUT: The counter part account for outgoing stock moves.

An Account Move is created for each Stock Move done under a fiscal year with
the account stock method set and for which one Stock Location has the type
"Storage" and an the other has the type "Supplier", "Customer", "Production" or
"Lost and Found".

When the stock enters the warehouse the Account Stock of the Product is
debited and the Account Stock IN of the Product is credited.
The amount used is the Unit Price of the move or the Cost Price of the Product
if it uses the "fixed" method.
The account move uses the Account Stock OUT when the products leave the
warehouse.
