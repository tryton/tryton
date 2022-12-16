******
Design
******

The *Account Rule Module* introduces the following concepts:

.. _model-account.account.rule:

Account Rule
============

An *Account Rule* allows an account to be substituted for another based on a
set of criteria.
The substitution is determined by the first matching rule.
The account rule contains a set of properties, such as the original `Account
<account:model-account.account>`, the `Tax <account:model-account.tax>`, or a
date range.
These are used to work out if the account rule matches the account used.


.. seealso::

   The available account rules can be found by opening the main menu item:

      |Financial --> Configuration --> General Account --> Account Rules|__

      .. |Financial --> Configuration --> General Account --> Account Rules| replace:: :menuselection:`Financial --> Configuration --> General Account --> Account Rules`
      __ https://demo.tryton.org/model/account.account.rule
