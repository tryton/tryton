.. _topics-access_rights:

=============
Access Rights
=============

There are 4 levels of access rights: model, field, button and record.
Every access right is based on the groups of the user.
The model and field access rights are checked for every RPC call for which
:attr:`trytond.rpc.RPC.check_access` is set. The others are always enforced.

Model Access
============

They are defined by records of `ir.model.access` which define for each couple
of model and group, the read, write, create and delete permission. If any group
of the user has the permission activated, then the user is granted this
permission.

Field Access
============

Same as for model access but applied on the field. It uses records of
`ir.model.field.access`.

Button
======

For each button of a model the records of `ir.model.button` define the list of
groups that are allowed to call it.

Record Rule
===========

They are defined by records of `ir.rule.group` which contains a list of
`ir.rule` domain to which the rule applies. The group are selected by groups or
users. The access is granted for a record:

    - if the user is in at least one group that has the permission activated,

    - or if the user is in no group by there is a default group with the
      permission,

    - or if there is a global group with the permission.
