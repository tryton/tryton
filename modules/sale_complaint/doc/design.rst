******
Design
******

The *Sale Complaint Module* introduces or extends the following concepts:

.. _model-sale.complaint:

Complaint
=========

A complaint is a customer issue relating to a `sale <sale:model-sale.sale>` or
`invoice <account_invoice:model-account.invoice>`.
Each complaint, at any time, can be in one of several different states.
A complaint progresses through these states until it is either done or gets
cancelled.
When a state change occurs, the `Employee <company:model-company.employee>`
that triggered the change is also recorded.

Each complaint contains details of the `Customer <party:model-party.party>` and
either the sale, the sale line, the customer invoice or the customer invoice
line.
Actions can be registered such as creating a sale return or a credit note,
which will be processed if the complaint is approved.

.. seealso::

   The list of *Complaints* can be found by opening the main menu item:

      |Sales --> Complaints|__

      .. |Sales --> Complaints| replace:: :menuselection:`Sales --> Complaints`
      __ https://demo.tryton.org/model/sale.complaint

.. _model-sale.complaint.type:

Complaint Type
==============

The *Complaint Type* categorises the `complaints <model-sale.complaint>`.

.. seealso::

   The *Complaint Types* can be found by opening the main menu item:

      |Sales --> Configuration --> Customer Complaint --> Types|__

      .. |Sales --> Configuration --> Customer Complaint --> Types| replace:: :menuselection:`Sales --> Configuration --> Customer Complaint --> Types`
      __ https://demo.tryton.org/model/sale.complaint.type

.. _model-sale.configuration:

Sale Configuration
==================

When the *Sale Complaint Module* is activated, the sale configuration gains a
new property to set up the numbering `sequence <trytond:model-ir.sequence>` of
`complaints <model-sale.complaint>`.

.. seealso::

   The `Sale Configuration <sale:model-sale.configuration>` concept is
   introduced by the :doc:`Sale Module <sale:index>`.
