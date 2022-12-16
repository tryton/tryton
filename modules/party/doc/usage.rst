*****
Usage
*****

The items found under the [:menuselection:`Party`] main menu item allow you to
see and manage the parties on your system in a variety of different ways.

.. tip::

   A `Party <model-party.party>` is often referred to from documents generated
   in other parts of your Tryton system, from a party you can
   :guilabel:`Open related records` to quickly find documents related to that
   party.

.. _Categorising parties:

Categorising parties
====================

It can be a good idea to organise the `Parties <model-party.party>` on Tryton
into groups.
This is especially important if you have a lot of parties on your system,
as it helps you find and manage them effectively.

To do this you use party `Categories <model-party.category>`.
You can create categories with any name you like, and then add the appropriate
categories to each party.
These categories can also be organised into a structure, with each category
containing one or more subcategories.
This can help you classify the parties more finely.

For example::

   Haulier
      Local
      National
      International

In this example hauliers that only deliver goods locally are added to the
``Haulier / Local`` category.
A haulier that delivers to anywhere in the country is added to both the
``Haulier / Local`` and ``Haulier / National`` categories.

.. tip::

   Opening a category from the tree view will show a list of the parties
   that are a member of that category, or any of its subcategories.

.. _Manually assigning party codes:

Manually assigning party codes
==============================

Each `Party <model-party.party>` that gets entered onto the system needs a
unique code.
By default Tryton will automatically generate a code for each new party using
the *Sequence* defined in the party `Configuration
<model-party.configuration>`.

There are times when you want to manually allocate codes to parties.
Perhaps you have a policy of coding parties based on part of their name, or
maybe you have some other reason for needing to give each party a specific
code.
In these cases you need to clear out the :guilabel:`Party Sequence` defined in
the party *Configuration*.
Once you have done this, as you create the parties, you must fill in the party
code manually.

.. _Setting a default party language:

Setting a default party language
================================

When a new `Party <model-party.party>` is created the default language for the
party is taken from the party `Configuration <model-party.configuration>`.
Providing a default language for parties can help reduce data entry, and ensure
that new parties are given a language.
This, in turn, can be important as Tryton will automatically generate reports,
such as invoices and delivery notes, in the correct language for each party.

.. _Checking VAT numbers are valid:

Checking VAT numbers are valid
==============================

If the `Party <model-party.party>` is in the European Union you can use the
`Check VIES <wizard-party.check_vies>` on it to check whether its VAT number
is valid or not.

.. _Merging duplicate parties together:

Merging duplicate parties together
==================================

Even when you have checks in place to try and avoid creating duplicate
`Parties <model-party.party>` it is quite common to find this has accidentally
happened.

If you do find some duplicates you will first need to decide which of them
you want to use from now on.

Then, with the list of parties open, you should select all of the duplicates,
apart from the one you want to keep, and then run the
`Replace <wizard-party.replace>` party wizard.
Here, you will be able to enter which party you want to keep and get Tryton to
replace the duplicates with it.

.. _Erasing a party's personal data:

Erasing a party's personal data
===============================

In order to help you comply with privacy legislation, personal data about a
person or business can be erased from the system by using the
`Erase <wizard-party.erase>` party wizard.

.. tip::

   Tryton will stop you from accidental erasing a party that has pending
   operations.
