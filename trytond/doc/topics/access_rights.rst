.. _topics-access_rights:

=============
Access Rights
=============

There are 5 levels of access rights: model, actions, field, button and record.
Every access right is based on the groups of the user.
The model and field access rights are checked for every RPC call for which
:attr:`trytond.rpc.RPC.check_access` is set. The others are always enforced.

Model Access
============

They are defined by records of `ir.model.access` which define for each couple
of model and group, the read, write, create and delete permission. If any group
of the user has the permission activated, then the user is granted this
permission.

Actions Access
==============

Each action define a list of groups that are allowed to use it.
There is a special case for :ref:`wizard <topics-wizard>` for which the read
access on the model is also checked and also the write access if there is no
groups linked.

Field Access
============

Same as for model access but applied on the field. It uses records of
`ir.model.field.access`.

Button
======

For each button of a model the records of `ir.model.button` define the list of
groups that are allowed to call it.

Button Rule
===========

The `ir.model.button` could contain a list of rules which define how much
different users must click on the button. Each rule must be passed to actually
trigger the action. The counter can be reset when another defined button is
clicked.

Record Rule
===========

They are defined by records of `ir.rule.group` which contains a list of
`ir.rule` domain to which the rule applies. The group are selected by groups or
users. The access is granted for a record:

    - if the user is in at least one group that has the permission activated,

    - or if the user is in no group by there is a default group with the
      permission,

    - or if there is a global group with the permission.
