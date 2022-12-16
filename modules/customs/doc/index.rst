Customs Module
##############

The customs module allows to define customs duty based on the tariff code.


Tarif Code
**********

It stores the `Harmonized System`_ that can be set on *Product*.

- The *Code* from the HS.
- The *Country* in case of a country specific code.
- The *Start* / *End* period of the year for which the code is valid.

.. _`Harmonized System`: http://en.wikipedia.org/wiki/Harmonized_System

Duty Rate
*********

It stores the rate of a *Tarif Code* for a country over a period.

- The *Tariff Code*.
- The *Country* for which the rate is.
- The *Type*: *Import* or *Export*
- The *Start* and *End* date of validity.
- The *Computation Type*:
    - *Amount*: fixed amount with currency.
    - *Quantity*: amount (in currency) per unit of measure.
