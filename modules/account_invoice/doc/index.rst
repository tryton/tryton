Account Invoice Module
######################

The account_invoice module adds the invoice, payment term.

Invoice
*******

There are 4 types of invoice: *Invoice*, *Supplier Invoice*, *Credit Note* and
*Supplier Credit Note*. An invoice can be in *Draft*, *Validated*, *Posted*,
*Paid* or *Cancelled*.

- Company: The company for which the invoice is created.
- Tax Identifier: The tax identifier that will be printed on the invoice
  (By default the first tax identifier of the company).
- Number: The invoice number set on validation for supplier invoices and on
  posting for others using the sequence defined on the fiscalyear.
- Reference: The optional external reference of the invoice.
- Party: The party for which or from which the invoice is issued.
- Invoice Address: The address of the party.
- Party Tax Identifier: The tax identifier of the party.
- Description: An optional description of the invoice.
- Comment: A text fields to add custom comments.
- Invoice Date: The date of the invoice. It is set on posting the invoice if not.
- Accounting Date: The date to use for accounting if set otherwise it is the
  invoice date.
- Currency: The currency of the invoice.
- Journal: The journal on which the accounting must be booked.
- Account: The payable or receivable account.
- Payment Term: The payment term to apply for the invoice
  (default value comes from the party).
- Lines: The lines invoiced.
- Taxes: The taxes related to the lines.
- Untaxed, Tax, Total Amount: The amounts computed by the invoice.
- Move: The accounting move created by the invoice on validation for supplier
  invoices and on posting for others.
- Cancel Move: The accounting move created to cancel a posted invoice.

The *Invoice* report is stored when the invoice is posted and thus it is always
the same that is returned for consistency.

A wizard allow to register a cash payment directly on the invoice. The payment
could be partial or with write-off.

An other wizard allow to create a credit note from the invoice. If the option
to refund is checked, the original invoice will be cancelled by the credit note.

Invoice Line
************

There are 4 types of lines: *Line*, *Subtotal*, *Title*, *Comment*.
The *Line* are composed of:

- Product: An optional reference to the product to invoice.
- Account: The account to book the expense or revenue.
- Quantity: The quantity invoiced.
- Unit: The unit of measure in which is expressed the quantity.
- Unit Price: The unit price of the quantity in the currency of the invoice.
- Amount: The amount of the line (Unit Price multiplied by Quantity).
- Description: The description of the product or the line.
- Note: A text fields to add custom comments.
- Taxes: The taxes to apply to the amount of the line.

Invoice Tax
***********

It groups the taxes of all the lines.
The rounding of the taxes is defined in the accounting configuration and can
be: *Per Document* or *Per Line*.

- Description: The description of the tax.
- Account: The account on which the tax is booked.
- Base: The base amount on which the tax is computed.
- Base Code: The *Tax Code* to record the base amount.
- Base Sign: The sign used to record the base amount on the tax code.
- Amount: The amount of the tax.
- Tax Code: The *Tax Code* to record the tax amount.
- Tax Sing: The sign used to record the tax amount on the tax code.
- Tax: The tax used for computation.
- Manual: A boolean to define manual tax
  (which is not linked to an invoice line).

Payment Term
************

It defines the maximum dates of how an due amount should be paid.

- Name: The name of the term.
- Description: The long description of the term.
- Lines:

  - Relative Deltas:

    - Day: The day of the month.
    - Month: The month of the year.
    - Day of the Week: One of the week day.
    - Months: The number of months to add.
    - Weeks: The number of weeks to add.
    - Days: The number of days to add.

  - Type:

    - *Fixed*:

      - Amount: The maximum fixed amount to pay at this date.
      - Currency: The currency of the amount.

    - *Percentage on Remainder*:

      - Ratio: The ratio to use on the remainder amount.
      - Divisor: The reversed ratio.

    - *Percentage on Total*:

      - Ratio: The ratio to use on the total amount.
      - Divisor: The reversed ratio.

    - *Remainder*

The computation of relative delta is based on the `python-dateutil library`_.
The payment term create a term for each line as far as there is still a
remainder amount.

A wizard is provided to test the behaviour of the payment term. It display
computed terms base on an amount and a date.

.. note:: The last line of payment term must be a remainder.


Payment Method
**************

The payment options available when paying an invoice. It has the following
fields:

- Name
- Company
- Journal: Will be used for creating the payment move
- Credit Account and Debit Account: The accounts used for the payment move
  depending on the amount sign.
- Active: A checkbox that allow to disable the payment method.


Fiscal Year Sequences
*********************

The sequence used to compute the invoice number is retrieved from the
fiscalyear sequences model. At least one record must be defined for each
fiscalyear. Additional criteria can be used like:

* By period


Configuration
*************

The account_invoice module uses the section `account_invoice` to retrieve some
parameters:

- `filestore`: a boolean value to store invoice report cache in the FileStore.
  The default value is `False`.

- `store_prefix`: the prefix to use with the FileStore. The default value is
  `None`.

.. _`python-dateutil library`: http://labix.org/python-dateutil#head-72c4689ec5608067d118b9143cef6bdffb6dad4e
