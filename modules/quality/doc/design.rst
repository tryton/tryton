******
Design
******

The *Quality Module* introduces the following concepts:

.. _model-quality.control:

Control
=======

The *Control* concept contains a list of points to control and which criteria
trigger an inspection, such as the kind of operation, the product involved, etc.

.. seealso::

   Controls can be found by opening the main menu item:

      |Quality --> Configuration --> Controls|__

      .. |Quality --> Configuration --> Controls| replace:: :menuselection:`Quality --> Configuration --> Controls`
      __ https://demo.tryton.org/model/quality.control


.. _model-quality.inspection:

Inspection
==========

The *Inspection* concept stores the result of a quality control test performed
for an associated document.
When the inspection is processed it passes or fails based on the result of the
test and the allowed tolerance of the `Control's <model-quality.control>`
points.
When an inspection fails an `Alert <model-quality.alert>` is automatically
created and the linked document is blocked until all the alerts are resolved or
deferred.

.. seealso::

   Inspections can be found by opening the main menu item:

      |Quality --> Inspections|__

      .. |Quality --> Inspections| replace:: :menuselection:`Quality --> Inspections`
      __ https://demo.tryton.org/model/quality.inspection

Wizards
-------

.. _wizard-quality.inspect:

Inspect
^^^^^^^

The *Inspect* wizard creates and helps to enter in the
`Inspections <model-quality.inspection>` for a document.
It then loops over all the inspections and processes them.

.. _model-quality.alert:

Alert
=====

The *Alert* concept tracks a failing `Inspection <model-quality.inspection>`
through to its resolution.

.. seealso::

   Alerts can be found by opening the main menu item:

      |Quality --> Alerts|__

      .. |Quality --> Alerts| replace:: :menuselection:`Quality --> Alerts`
      __ https://demo.tryton.org/model/quality.alert

.. _model-quality.configuration:

Configuration
=============

The *Quality Configuration* concept is used to store the settings which affect
how the system behaves in relation to quality.

.. seealso::

   Configuration settings are found by opening the main menu item:

      |Quality --> Configuration --> Configuration|__

      .. |Quality --> Configuration --> Configuration| replace:: :menuselection:`Quality --> Configuration --> Configuration`
      __ https://demo.tryton.org/model/quality.configuration
