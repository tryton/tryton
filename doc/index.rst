Currency Module
###############

The currency module defines the concepts of currency and rate.


Currency
********

A currency is defined by a name, a symbol, a code, a list of rates, a
rounding factor and some formatting properties: the digits to be
displayed after the decimal separator, the way the numbers should be
grouped, the thousands separator, the decimal separator, the positive
and negative signs and their positions, the currency symbol position
and if it should be separated from the number by a space.


Rate
****

A rate is defined by a date and a numeric value. The date gives the
time from which this rate is correct. All rates are defined implicitly
with respect to the same currency (the one whose rate is 1).

Scripts
*******

There is a scripts:

    * `trytond_import_currencies` to create and update currencies from the ISO
      database.
