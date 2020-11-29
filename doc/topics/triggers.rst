.. _topics-triggers:

========
Triggers
========

Triggers allow to define methods of :class:`trytond.model.model.Model` that are
called at the end of the transaction when one of those events happen to a
record:

* On Creation
* On Modification
* On Deletions
* On Time: When a condition changes over time.

The method signature is::

    <method name>(cls, records, trigger)

Where ``records`` is the list of records that triggered the event and
``trigger`` is the ``ir.trigger`` instance which is triggered.

Triggers are defined by records of ``ir.trigger``. Each record must define a
pyson condition which will be evaluated when the event occurs. Only those
records for which the condition is evaluated to true will be processed by the
trigger with the exception of modification triggers which will only process the
records for which the condition is evaluated to false before and evaluated to
true after the modification.
