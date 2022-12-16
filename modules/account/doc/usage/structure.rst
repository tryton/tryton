.. _Making changes to the accounts structure:

Making changes to the accounts structure
========================================

When you've created your `Company's <company:model-company.company>` accounts
structure from a template you can extend it without needing to do anything
special.

If you want to change any of the `Accounts <model-account.account>`,
`Account Types <model-account.account.type>`,
`Taxes <model-account.tax>`, `Tax Codes <model-account.tax.code>`, and
`Tax Rules <model-account.tax.rule>` that were created from the
`Template <concept-account.template>` then you need to use the
:guilabel:`Override Template` option on the items you want to change.

.. note::

   Items where you have overridden the template will not be changed when you
   are `Updating the accounts structure`.

.. _Updating the accounts structure:

Updating the accounts structure
===============================

If you created your `Company's <company:model-company.company>` accounts
structure from a template you will find that the template is occasionally
updated or improved to match any updated accounting requirements.

To bring these changes into your accounts structure you use the
`Update Chart <wizard-account.update_chart>` wizard.

.. note::

   Any items where you have overridden the template will not be changed.
