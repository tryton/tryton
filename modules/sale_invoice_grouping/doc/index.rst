Sale Invoice Grouping Module
############################

The ``sale_invoice_grouping`` module adds an option to define how invoice lines
generated from sales will be grouped.

A field is added to the *Party*:

- *Sale Invoice Grouping Method*: The method used when grouping invoice lines.

If the Standard method is used, invoice lines generated will be added to the
first matching invoice found. If no invoice matches sale attributes then a new
one will be created. Invoices not created by the sale process are not taken
into account when looking for a candidate invoice to add invoice lines to.
