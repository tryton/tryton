******
Design
******

The *Commission Module* introduces and extends the following concepts:

.. _model-commission.agent:

Agent
=====

An *Agent* links a party to a `Plan <model-commission.plan>`.
An *Agent* can be either an agent or a principal of the `Company
<company:model-company.company>`.

.. seealso::

   Agents are found by opening the main menu item:

      |Commission --> Agents|__

      .. |Commission --> Agents| replace:: :menuselection:`Commission --> Agents`
      __ https://demo.tryton.org/model/commission.agent

.. _model-commission.agent.selection:

Agent Selection
================

The *Agent Selection* contains a sets of rules to assign automatically an
`Agent <model-commission.agent>` to sales based on criteria.

.. _model-commission.plan:

Plan
====

A *Plan* defines how the `Commission <model-commission>` of an `Agent
<model-commission.agent>` is computed using a list of formula with criteria.

.. seealso::

   Plans are found by opening the main menu item:

      |Commission -> Configuration --> Plans|__

      .. |Commission -> Configuration --> Plans| replace:: :menuselection:`Commission -> Configuration --> Plans`
      __ https://demo.tryton.org/model/commission.plan

.. _model-commission:

Commission
==========

The *Commission* concept is used to register the amount that is due to an agent
or to receive from a principal.

An `Invoice <account_invoice:model-account.invoice>` can be generated using the
*Invoice* button.
The commissions invoiced together are grouped by `Agent
<model-commission.agent>`.

.. seealso::

   Commissions are found by opening the main menu item:

      |Commission --> Commissions|__

      .. |Commission --> Commissions| replace:: :menuselection:`Commission --> Commissions`
      __ https://demo.tryton.org/model/commission

Wizards
-------

.. _wizard-commission.create_invoice:

Create Commission Invoice
^^^^^^^^^^^^^^^^^^^^^^^^^

The *Create Commission Invoice* wizard helps the user to invoice all the
pending `Commission <model-commission>` based on search criteria like the date
period or the `Agent <model-commission.agent>`.

.. _model.commission.reporting.agent:

Commission Reporting Agent
==========================

The *Commission Reporting Agent* sums the commission amounts per `Agent
<model-commission.agent>` for the selected period from the ``Context``.

.. _concept-product:

Product
=======

The *Product* concept is extended to store the principals who pay a commission
when the product is sold.

.. seealso::

   The `Product <product:concept-product>` concept is introduced by the
   :doc:`Product Module <product:index>`.

.. _model-party.party:

Party
=====

The *Party* is extended to store its `Agent Selection
<model-commission.agent.selection>`.

.. seealso::

   The `Party <party:model-party.party>` concept is introduced by the
   :doc:`Party Module <party:index>`.

.. _model-sale.sale:

Sale
====

The *Sale* is extended to store an `Agent <model-commission.agent>` on the
header and `Principal <model-commission.agent>` on the lines.
Those values are copied to the generated `Invoice
<account_invoice:model-account.invoice>`.

When a `Product <product:concept-product>` is selected, its principal is copied
on the line.
When the *Sale* is quoted and if there is no *Agent* filled, one is computed
using the `Agent Selection <model-commission.agent.selection>`.

.. seealso::

   The `Sale <sale:model-sale.sale>` concept is introduced by the :doc:`Sale
   Module <sale:index>`.

.. _model-account.invoice:

Invoice
========

The *Invoice* concept is extended to store an `Agent <model-commission.agent>`
on the header and `Principal <model-commission.agent>` on the lines.

When the *Invoice* is posted the corresponding `Commissions <model-commission>`
are created.
Its due date is set later depending on the commission method.

.. seealso::

   The `Invoice <account_invoice:model-account.invoice>` concept is introduced
   by the :doc:`Account Invoice Module <account_invoice:index>`.
