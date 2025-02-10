:orphan:

.. _index-migration:

Migration
=========

Here are listed the manual actions you need to take before and after upgrading
a database from another series.

.. note::
   If you skip a series, all actions between them must be performed.

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

5.6
---

Before
~~~~~~

* If ``project`` module is activated, update project status based on previous
  state:

  .. code-block:: SQL

     UPDATE "project_work" SET "status" = "db_id" FROM "ir_model_data" WHERE "module" = 'project' AND "fs_id" = 'work_open_status' AND "state" = 'opened';
     UPDATE "project_work" SET "status" = "db_id" FROM "ir_model_data" WHERE "module" = 'project' and "fs_id" = 'work_done_status' AND "state" = 'done';

* If ``sale_amendment`` module is activated, the foreign key of shipment_party
  of sale amendment must be recreated:

  .. code-block:: SQL

     ALTER TABLE IF EXISTS "sale_amendment_line" DROP CONSTRAINT IF EXISTS "sale_amendment_line_shipment_party_fkey";

5.4
---

Before
~~~~~~

* If ``account_payment_sepa`` module is activated, replace
  ``account_payment_sepa_message`` from ``TEXT`` to ``BYTEA``:

  .. code-block:: SQL

     ALTER TABLE IF EXISTS "account_payment_sepa_message" ALTER COLUMN IF EXISTS "message" TYPE BYTEA USING "message"::BYTEA;

5.2
---

Before
~~~~~~

* Remove ``src_md5`` from ``ir.translation``:

  .. code-block:: SQL

     ALTER TABLE "ir_translation" DROP CONSTRAINT IF EXISTS "ir_translation_translation_md5_uniq";
     ALTER TABLE "ir_translation" DROP COLUMN IF EXISTS "src_md5";

After
~~~~~

* Remove error translations:

  .. code-block:: SQL

     DELETE FROM "ir_translation" WHERE "type" = 'error';

* Remove old users:

  .. code-block:: SQL

     DELETE FROM "ir_model_data" WHERE "model" = 'res.user' AND "fs_id" = 'user_chorus' AND "module" = 'account_fr_chorus';
     DELETE FROM "ir_model_data" WHERE "model" = 'res.user' AND "fs_id" = 'user_post_clearing_moves' AND "module" = 'account_payment_clearing';
     DELETE FROM "ir_model_data" WHERE "model" = 'res.user' AND "fs_id" = 'user_stripe' AND "module" = 'account_payment_stripe';
     DELETE FROM "ir_model_data" WHERE "model" = 'res.user' AND "fs_id" = 'user_marketing_automation' AND "module" = 'marketing_automation';
     DELETE FROM "ir_model_data" WHERE "model" = 'res.user' AND "fs_id" = 'user_generate_line_consumption' AND "module" = 'sale_subscription';
     DELETE FROM "ir_model_data" WHERE "model" = 'res.user' AND "fs_id" = 'user_generate_line_consumption' AND "module" = 'sale_subscription';
     DELETE FROM "ir_model_data" WHERE "model" = 'res.user' AND "fs_id" = 'user_generate_invoice' AND "module" = 'sale_subscription';
     DELETE FROM "ir_model_data" WHERE "model" = 'res.user' AND "fs_id" = 'user_role' AND "module" = 'user_role';
     DELETE FROM "ir_model_data" WHERE "model" = 'res.user' AND "fs_id" = 'user_trigger' AND "module" = 'res';

5.0
---

Before
~~~~~~

* If ``account_product`` module is activated, set an accounting category to all
  products which have accounts and taxes defined (see `#3805
  <https://bugs.tryton.org/3805>`_).

After
~~~~~

* Remove old users:

  .. code-block:: SQL

     DELETE FROM "ir_model_data" WHERE "model" = 'res.user' AND "fs_id" = 'user_process_sale' AND "module" = 'sale';
     DELETE FROM "ir_model_data" WHERE "model" = 'res.user' AND "fs_id" = 'user_process_purchase' AND "module" = 'purchase';

* If ``account`` module is activated, clean ``account.journal.type`` data:

  .. code-block:: SQL

     DELETE FROM "ir_model_data" WHERE "model" = 'account.journal.type';

4.8
---

Before
~~~~~~

* Assign any record rules linked to users to a group.

* Add parent language:

  .. code-block:: SQL

     ALTER TABLE IF EXISTS "ir_lang" ADD COLUMN IF NOT EXISTS "parent" VARCHAR;

* If ``account`` module is activated, update tax line sign:

  .. code-block:: SQL

     UPDATE "account_tax_line" SET "amount" = -"amount" WHERE "id" IN (SELECT "tl"."id" FROM "account_tax_line" AS "tl" JOIN "account_move_line" AS "ml" ON "tl"."move_line" = "ml"."id" JOIN "account_move" AS "m" ON "ml"."move" = "m"."id" JOIN "account_invoice" AS "i" ON "i"."id" = CAST(SUBSTRING("m"."origin", 17) AS INTEGER) AND "m"."origin" like 'account.invoice,%' WHERE "tl"."amount" > 0 AND "ml"."credit" > 0 AND "i"."type" = 'in');
     UPDATE "account_tax_line" SET "amount" = -"amount" WHERE "id" IN (SELECT "tl"."id" FROM "account_tax_line" AS "tl" JOIN "account_move_line" AS "ml" ON "tl"."move_line" = "ml"."id" JOIN "account_move" AS "m" ON "ml"."move" = "m"."id" JOIN "account_invoice" AS "i" ON "i"."id" = CAST(SUBSTRING("m"."origin", 17) AS INTEGER) AND "m"."origin" like 'account.invoice,%' WHERE "tl"."amount" > 0 AND "ml"."debit" > 0 AND "i"."type" = 'out');


After
~~~~~

* If ``account`` module is activated, update tax lines of inactive tax to their
  parent:

  .. code-block:: SQL

     UPDATE "account_tax_line" as "l" SET "tax" = (SELECT "parent" FROM "account_tax" WHERE "account_tax"."id" = "tax") FROM "account_tax" as "t" WHERE "l"."tax" = "t"."id" AND "t"."active" = false;

* If ``account`` module is activated, delete duplicate tax lines:

  .. code-block:: SQL

      DELETE FROM "account_tax_line" WHERE "id" IN (SELECT MAX("id") FROM "account_tax_line" GROUP BY "tax", "amount", "type", "move_line" HAVING count(*) > 1);

  .. note:: Run multiple times until no record are deleted.

* Check taxes and tax codes definitions (inactivate old children taxes and add
  them to the right codes)

4.6
---

Before
~~~~~~

* If ``web_user`` module is activated, update to lower case email of web users:

  .. code-block:: SQL

      UPDATE "web_user" SET "email" = LOWER("email");

4.4
---

Before
~~~~~~

* Remove deprecated modules:

  .. code-block:: SQL

     DELETE FROM "ir_module" WHERE "name" IN ('webdav', 'calendar', 'calendar_todo', 'calendar_scheduling', 'calendar_classification', 'party_vcarddav');
     DELETE FROM "ir_ui_view" WHERE "module" IN ('webdav', 'calendar', 'calendar_todo', 'calendar_scheduling', 'calendar_classification', 'party_vcarddav');

* If ``party`` module is activated, update address formats:

  .. code-block:: SQL

     UPDATE "party_address_format" SET "format_" = REPLACE("format_", '${district}', '${subdivision}');

* If ``purchase`` module is activated, delete relation between purchase and invoice_line:

  .. code-block:: SQL

     DROP TABLE IF EXISTS "purchase_invoice_line_rel";

After
~~~~~

* If ``account_asset`` module is activated, the depreciation duration of the
  products must be checked for all assets as previous value could not be
  migrated (see `#6395 <https://bugs.tryton.org/6395>`_).

* After property migration old model data should be cleared:

  .. code-block:: SQL

     DELETE FROM "ir_model_data" WHERE "model" = 'ir.property';

4.2
---

Before
~~~~~~

* Language codes have been simplified.
  If you want to keep custom translation you must update translation code to
  match the new code.
  Here is an example for the code change from ``en_US`` to ``en``:

  .. code-block:: SQL

     UPDATE "ir_translation" SET "lang" = 'en' WHERE "lang" = 'en_US';
     UPDATE "ir_configuration" SET "language" = 'en' WHERE "language" = 'en_US';

4.0
---

Before
~~~~~~

* If ``account`` module is activated, change tax sign for credit note:

  .. code-block:: SQL

     UPDATE "account_tax_template" SET "credit_note_base_sign" = "credit_note_base_sign" * -1, "credit_note_tax_sign" = "credit_note_tax_sign" * -1;
     UPDATE "account_tax" SET "credit_note_base_sign" = "credit_note_base_sign" * -1, "credit_note_tax_sign" = "credit_note_tax_sign" * -1;

* If ``project`` module is activated, drop the foreign key constraint
  ``project_work_work_fkey``:

  .. code-block:: SQL

     ALTER TABLE IF EXISTS "project_work" DROP CONSTRAINT IF EXISTS "project_work_work_fkey";

After
~~~~~

* If ``product`` module is activated, drop column ``category`` from
  ``product.template``:

  .. code-block:: SQL

     ALTER TABLE "product_template" DROP COLUMN IF EXISTS "category";


3.6
---

Before
~~~~~~

* If ``account`` module is activated, update amount second currency with:

  .. code-block:: SQL

     UPDATE "account_move_line" SET "amount_second_currency" = ("amount_second_currency" * -1) WHERE "amount_second_currency" IS NOT NULL AND SIGN("amount_second_currency") != SIGN("debit" - "credit");
