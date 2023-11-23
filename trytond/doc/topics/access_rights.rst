.. _topics-access_rights:

=============
Access Rights
=============

There are 5 levels of access rights: `Model`_ , `Actions`_, `Field`_, `Button`_
and `Record Rule`_. They are based on the user's group membership.
If any of those levels are violated, an error is raised.

The access rights are checked if the :attr:`Transaction.context
<trytond.transaction.Transaction.context>` has the key ``_check_access`` set to
``True`` (set by default by :attr:`RPC.check_access
<trytond.rpc.RPC.check_access>`) and if the
:attr:`~trytond.transaction.Transaction.user` is not ``root``.

Model
=====

They are defined by records of ``ir.model.access`` which define for each couple
of model and group, the ``read``, ``write``, ``create`` and ``delete``
permission. The permissions are related to the
:class:`~trytond.model.ModelStorage` methods with the same name and on
:meth:`~trytond.model.ModelStorage.search` using the ``read`` permission.

If any group the user belongs to has the checked permission activated, then the
user is granted this permission.

If there is no record for the model, then access is granted to all users.

.. note::
    Relation fields for which the user has no read access are automatically
    removed from the :ref:`views <topics-views>`.

Actions
=======

Each ``ir.action`` has a ``groups`` field which contains a list of user groups
that are allowed to see and launch it.

There is a special case for :ref:`wizard <topics-wizard>` for which the read
access on the model is also checked and also the write access if there is no
groups linked.

Field
=====

They are defined by records of ``ir.model.field.access`` and work like those
for `Model`_ but are applied to :ref:`fields <ref-models-fields>`.

.. note::
    Fields for which the user has no read access are automatically removed from
    the :ref:`views <topics-views>`.

Button
======

For each button of a model the records of ``ir.model.button`` define the list of
groups that are allowed to call it. The user only needs to belong to one of the
groups to be granted the permission to use it.

If no group is defined for a button, the ``write`` permission to the model is
checked instead.

The ``read`` permission to the model is always enforced.

.. note::
    Buttons for which the user has no access are marked readonly.

Button Rule
-----------

The ``ir.model.button`` can contain a list of rules which define how many
different users must click on the button.  Each rule, for which the condition
is met, must be passed to actually trigger the action. The counter can be reset
when another defined button is clicked.

Record Rule
===========

The record rules are conditions that records must meet for the user to be
granted permission to use them.
They are defined by records of ``ir.rule.group`` which contains:

    - The model the rule applies to.
    - The type of permissions to be granted.
    - A set of user groups to which the rule applies.
    - A global flag to always enforce the rule even if there are other rules
      that are less restrictive.
    - A default flag to apply the rule, by default, to all users.
      This then allows other less restrictive rules, that apply to the user,
      to grant them additional permissions.
    - A list of ``ir.rule`` records, each with a :ref:`domain <topics-domain>`
      that is used to select the records to which the rule applies.

A rule group matches a record if the record is validated by at least one of the
domains.
Access is only granted to a record:

    - if the user belongs to a group which has at least one matching rule group
      that has the permission,

    - or if there is a default matching rule group with the permission,

    - or if there is a global matching rule group with the permission.

    - or if there are no matching rule groups and no global rule groups for
      the model.


.. note::
    Records for which the user has no ``read`` access are filtered out from the
    :meth:`~trytond.model.ModelStorage.search` result.
