.. _model-ir.action:

Action
======

The *Action* concept contains common user interface behavior properties.
The list of keywords specifies where the action is available and for which
`Model <model-ir.model>`.
If any `Groups <model-res.group>` are added to the action, then only members of
at least one of these groups will have access to the action.

.. seealso::

   The Actions can be found by opening the main menu item:

      |Administration --> User Interface --> Actions --> Actions|__

      .. |Administration --> User Interface --> Actions --> Actions| replace:: :menuselection:`Administration --> User Interface --> Actions --> Actions`
      __ https://demo.tryton.org/model/ir.action

.. _model-ir.action.report:

Report Action
=============

The *Report Action* stores the properties needed to execute the named
:class:`~trytond.report.Report`.

.. seealso::

   The Report Actions can be found by opening the main menu item:

      |Administration --> User Interface --> Actions --> Reports|__

      .. |Administration --> User Interface --> Actions --> Reports| replace:: :menuselection:`Administration --> User Interface --> Actions --> Reports`
      __ https://demo.tryton.org/model/ir.action.report

.. _model-ir.action.act_window:

Window Action
=============

The *Window Action* stores the properties necessary for the client to open a
tab for a :class:`~trytond.model.ModelStorage`.
It consists of a list of `Views <model-ir.ui.view>` and domains.

.. seealso::

   The Window Actions can be found by opening the main menu item:

      |Administration --> User Interface --> Actions --> Window Actions|__

      .. |Administration --> User Interface --> Actions --> Window Actions| replace:: :menuselection:`Administration --> User Interface --> Actions --> Window Actions`
      __ https://demo.tryton.org/model/ir.action.act_window

.. _model-ir.action.wizard:

Wizard Action
=============

The *Wizard Action* defines how the client should run the named
:class:`~trytond.wizard.Wizard`.

.. seealso::

   The Wizard Actions can be found by opening the main menu item:

      |Administration --> User Interface --> Actions --> Wizards|__

      .. |Administration --> User Interface --> Actions --> Wizards| replace:: :menuselection:`Administration --> User Interface --> Actions --> Wizards`
      __ https://demo.tryton.org/model/ir.action.wizard

.. _model-ir.action.url:

URL Action
==========

Each *URL Action* stores a `URL <https://en.wikipedia.org/wiki/URL>`_ to open.

.. seealso::

   The URL Actions can be found by opening the main menu item:

      |Administration --> User Interface --> Actions --> URLs|__

      .. |Administration --> User Interface --> Actions --> URLs| replace:: :menuselection:`Administration --> User Interface --> Actions --> URLs`
      __ https://demo.tryton.org/model/ir.action.url
