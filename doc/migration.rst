:orphan:

.. _index-migration:

Migration
=========

Here are listed the manual actions you need to take before and after upgrading
a database from another series.

.. note::
   If you skip a series, all actions between them must be performed.

.. warning::
   You cannot skip more than 2 series ending with ``.0``.

7.8
---

After
~~~~~

* If ``account_payment_sepa`` module is activated, fill the address of
  validated mandates with default value with the ``trytond-console``:

  .. code-block:: python

     Mandate = pool.get('account.payment.sepa.mandate')
     mandates = Mandate.search([
         ('state', '=', 'validated'),
         ('address', '=', None),
         ])
     for mandate in mandates:
         mandate.address = mandate.on_change_party()
     Mandate.save(mandates)

7.6
---

Before
~~~~~~

* Rename columns of ``ir.model`` and ``ir.model.field``:

  .. code-block:: SQL

     ALTER TABLE IF EXISTS "ir_model" RENAME COLUMN "name" TO "string";
     ALTER TABLE IF EXISTS "ir_model" RENAME COLUMN "model" TO "name";
     ALTER TABLE IF EXISTS "ir_model_field" RENAME COLUMN "field_description" TO "string";

* ``pbkdf2_sha512`` and ``scrypt`` password hashes are no more supported.
  Make sure to enable ``argon2`` and update old passwords by logging in.

After
~~~~~

* If ``stock`` module is activated with internal shipment using transit
  location, fill the internal transit location with the ``trytond-console``:

  .. code-block:: python

     Shipment = pool.get('stock.shipment.internal')
     shipments = Shipment.search([('state', 'not in', ['request', 'draft'])])
     for shipment in shipments:
         state = shipment.state
         shipment.state = 'draft'
         shipment.internal_transit_location = shipment.transit_location
         shipment.state = state
     Shipment.save(shipments)
     transaction.commit()

* If ``account_budget`` module is activated, invert amount sign:

   .. code-block:: SQL

      UPDATE "account_budget_line" SET amount = -amount;

* If ``analytic_budget`` module is activated, invert amount sign:

   .. code-block:: SQL

      UPDATE "analytic_account_budget_line" SET amount = -amount;

7.4
---

Before
~~~~~~

* If ``product_price_list`` and ``product_price_list_dates`` are activated,
  remove ``open_lines`` button:

  .. code-block:: SQL

     DELETE FROM "ir_model_button" WHERE "name" = 'open_lines' AND "model" = 'product.price_list';

7.2
---

Before
~~~~~~

* Use NULL value for empty foreign key with:

  .. code-block:: SQL

     UPDATE "ir_ui_view" SET "model" = NULL WHERE "model" = '';
     UPDATE "ir_action_act_window" SET "res_model" = NULL WHERE "res_model" = '';
     UPDATE "ir_action_wizard" SET "model" = NULL WHERE "model" = '';
     UPDATE "ir_action_report" SET "model" = NULL WHERE "model" = '';
     UPDATE "ir_action_report" SET "module" = NULL WHERE "module" = '';
     UPDATE "ir_translation" SET "module" = NULL WHERE "module" = '';

7.0
---

Before
~~~~~~

* If ``account_payment`` module is activated, remove ``account`` if ``line`` is
  set:

  .. code-block:: SQL

     UPDATE "account_payment" SET "account" = NULL WHERE "line" IS NOT NULL;

After
~~~~~

* If ``account_invoice`` module is activated, fill the amount caches with the
  ``trytond-console``:

  .. code-block:: python

     Invoice = pool.get('account.invoice')
     invoices = Invoice.search([('state', 'in', ['posted', 'paid'])])
     for invoice in invoices:
         invoice.untaxed_amount_cache = invoice.untaxed_amount
         invoice.tax_amount_cache = invoice.tax_amount
         invoice.total_amount_cache = invoice.total_amount

     Invoice.save(invoices)
     transaction.commit()

  .. note::

     This process may take some time depending on the number of invoices on
     your database.

* If ``product_price_list`` module is activated, add a default price list line
  if price list does not have one and it was relying on the fallback price.

6.0
---

Before
~~~~~~

* Add access on field:

  .. code-block:: SQL

     ALTER TABLE IF EXISTS "ir_model_field" ADD COLUMN IF NOT EXISTS "access" BOOLEAN;

* If ``account_invoice`` module is activated, fix ``currency``,
  ``invoice_type`` and ``party`` on ``account.invoice.line``:

  .. code-block:: SQL

     UPDATE "account_invoice_line" SET "currency" = (SELECT "currency" FROM "account_invoice" WHERE "id" = "account_invoice_line"."invoice") WHERE "invoice" IS NOT NULL;
     UPDATE "account_invoice_line" SET "invoice_type" = (SELECT "type" FROM "account_invoice" WHERE "id" = "account_invoice_line"."invoice") WHERE "invoice_type" IS NOT NULL AND "invoice" IS NOT NULL;
     UPDATE "account_invoice_line" SET "party" = (SELECT "party" FROM "account_invoice" WHERE "id" = "account_invoice_line"."invoice") WHERE "party" IS NOT NULL AND "invoice" IS NOT NULL;

After
~~~~~

* Remove code column on ``ir.sequence.type``:

  .. code-block:: SQL

     ALTER TABLE IF EXISTS "ir_sequence_type" DROP COLUMN IF EXISTS "code";
