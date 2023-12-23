******
Design
******

The *Marketing Automation Module* introduces the following concepts:

.. _model-marketing.automation.scenario:

Scenario
========

A *Scenario* provides the entry point for records into an automated marketing
campaign.
Each selected record can only enter a scenario once and follow the `Activities
<model-marketing.automation.activity>`.

.. seealso::

   Scenarios can be found by opening the main menu item:

      |Marketing --> Scenarios|__

      .. |Marketing --> Scenarios| replace:: :menuselection:`Marketing --> Scenarios`
      __ https://demo.tryton.org/model/marketing.automation.scenario

.. _model-marketing.automation.reporting.scenario:

Scenario Reporting
------------------

The *Scenario Reporting* computes per period the number of `Records
<model-marketing.automation.record>` entering the `Scenario
<model-marketing.automation.scenario>` and being blocked.

.. _model-marketing.automation.activity:

Activity
========

An *Activity* defines the action to execute when a record matches the condition
and the event has been triggered by the parent activity.

Actions
-------

The available actions are:

Send E-Mail
^^^^^^^^^^^

The E-mail is composed using an HTML `Genshi <https://genshi.edgewall.org/>`_
template with ``record`` in the evaluation context.
All ``<a>`` elements have their ``href`` replaced by a shortened version used
to trigger children activities.
If the ``href`` value is ``unsubscribe``, it is replaced by the URL which
allows the recipient to block their record for the scenario.
A empty image is automatically added at the end of the ``<body>`` to track when
emails are opened.

.. _model-marketing.automation.reporting.activity:

Activity Reporting
------------------

The *Activity Reporting* computes per period the number of `Record Activity
<model-marketing.automation.record.activity>` entering the `Activity
<model-marketing.automation.activity>` and being blocked.

Reports
-------

.. _report-marketing.automation.unsubscribe:

Unsubscribe
^^^^^^^^^^^

The *Unsubscribe Report* is an HTML page displayed when a recipient click on
the unsubscribe link.

.. _model-marketing.automation.record:

Record
======

A *Record* keeps track of the records entered in each scenario.
The record can be blocked such that no `Activity
<model-marketing.automation.activity>` will be triggered for it.

.. _model-marketing.automation.record.activity:

Record Activity
===============

A *Record Activity* the state and the due date of a record for an `Activity
<model-marketing.automation.activity>` of a `Scenario
<model-marketing.automation.scenario>`.
