Account Stock Anglo-Saxon Module
################################

The account_stock_anglo_saxon module adds anglo-saxon accounting model for
stock valuation.

A new field is added to Accounting categories:

- Account Cost of Goods Sold: The account which is used to record cost of goods
  sold.

The Account Moves of Invoices are modified for fiscal year with the account
stock method set.

On Supplier Invoice, the cost of the Product at reception is debited on the
Account Stock IN and only the difference is debited to the Account
Expense.
If the reception is not yet done then the cost is the amount on the invoice.
The opposite is done on Supplier Credit Note.

On Invoice, the cost of the Product at delivery is credited from the Account
Stock OUT and is debited to the Account Cost of Goods Sold.
If the delivery is not yet done then the current cost is used.
The opposite is done on Credit Note.
