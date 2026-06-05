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

.. _migration-8.2:

8.2
---

.. _migration-8.2-after:

After
~~~~~

* If ``account`` module is activated, update the reconciliation date using
  maturity date:

  .. code-block:: SQL

      UPDATE "account_move_reconciliation" AS r SET date = (SELECT GREATEST(MAX(l.maturity_date), MAX(m.date)) FROM account_move_line AS l JOIN account_move AS m ON l.move = m.id WHERE l.reconciliation = r.id);

.. _migration-8.0:

8.0
---

.. _migration-8.0-before:

Before
~~~~~~

* Remove ``google_maps`` module:

   .. code-block:: SQL

      DELETE FROM "ir_module" WHERE name = 'google_maps';

* Remove ``account_es`` and ``account_es_sii`` modules if you are not
  installing external replacements:

   .. code-block:: SQL

      DELETE FROM "ir_module" WHERE name in ('account_es', 'account_es_sii');

* Remove ``account_de_skr03`` module if you are not installing external
  replacement:

   .. code-block:: SQL

      DELETE FROM "ir_module" WHERE name = 'account_de_skr03';

.. _migration-7.8:

7.8
---

.. _migration-7.8-before:

Before
~~~~~~

* If ``carrier_carriage`` module is activated, remove ``NOT NULL`` to
  ``before_carrier`` and ``after_carrier``:

  .. code-block:: SQL

     ALTER TABLE "incoterm_incoterm" ALTER COLUMN "before_carrier" DROP NOT NULL;
     ALTER TABLE "incoterm_incoterm" ALTER COLUMN "after_carrier" DROP NOT NULL;

.. _migration-7.8-after:

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

.. _migration-7.6:

7.6
---

.. _migration-7.6-before:

Before
~~~~~~

* Rename columns of ``ir.model`` and ``ir.model.field``:

  .. code-block:: SQL

     ALTER TABLE IF EXISTS "ir_model" RENAME COLUMN "name" TO "string";
     ALTER TABLE IF EXISTS "ir_model" RENAME COLUMN "model" TO "name";
     ALTER TABLE IF EXISTS "ir_model_field" RENAME COLUMN "field_description" TO "string";

* ``pbkdf2_sha512`` and ``scrypt`` password hashes are no more supported.
  Make sure to enable ``argon2`` and update old passwords by logging in.

.. _migration-7.6-after:

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

.. _migration-7.4:

7.4
---

.. _migration-7.4-before:

Before
~~~~~~

* If ``product_price_list`` and ``product_price_list_dates`` are activated,
  remove ``open_lines`` button:

  .. code-block:: SQL

     DELETE FROM "ir_model_button" WHERE "name" = 'open_lines' AND "model" = 'product.price_list';

.. _migration-7.2:

7.2
---

.. _migration-7.2-before:

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

.. _migration-7.0:

7.0
---

.. _migration-7.0-before:

Before
~~~~~~

* If ``account_payment_clearing`` module is activated, remove ``account`` if ``line`` is
  set:

  .. code-block:: SQL

     UPDATE "account_payment" SET "account" = NULL WHERE "line" IS NOT NULL;

.. _migration-7.0-after:

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

.. _migration-6.0:

6.0
---

.. _migration-6.0-before:

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

.. _migration-6.0-after:

After
~~~~~

* Remove code column on ``ir.sequence.type``:

  .. code-block:: SQL

     ALTER TABLE IF EXISTS "ir_sequence_type" DROP COLUMN IF EXISTS "code";
