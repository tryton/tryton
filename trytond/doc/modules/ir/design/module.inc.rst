.. _model-ir.module:

Module
======

Every Tryton `Module <topics-modules>` has one entry.
The *Module* keeps track of whether it is activated or not.

.. seealso::

   Modules are found by opening the main menu item:

      |Administration --> Modules --> Modules|__

      .. |Administration --> Modules --> Modules| replace:: :menuselection:`Administration --> Modules --> Modules`
      __ https://demo.tryton.org/model/ir.module

Wizards
-------

.. _wizard-ir.module.activate_upgrade:

Activate / Upgrade Module
^^^^^^^^^^^^^^^^^^^^^^^^^

The *Activate / Upgrade Module* wizard performs the activation or upgrade of
the `Modules <model-ir.module>` marked as "To Upgrade", "To Remove" and "To
Activate".
It then launches the `Config Module <wizard-ir.module.config_wizard>` wizard.

.. _model-ir.module.config_wizard.item:

Module Config Wizard Item
=========================

The *Module Config Wizard Item* keeps track of the configuration `Actions
<model-ir.action>` to be launched after the `Activate / Upgrade Module
<wizard-ir.module.activate_upgrade>` wizard.

.. seealso::

   Module Config Wizard Items are found by opening the main menu item:

      |Administration --> Modules --> Config Wizard Items|__

      .. |Administration --> Modules --> Config Wizard Items| replace:: :menuselection:`Administration --> Modules --> Config Wizard Items`
      __ https://demo.tryton.org/model/ir.module.config_wizard.item

Wizards
-------

.. _wizard-ir.module.config_wizard:

Config Modules
^^^^^^^^^^^^^^

The *Config Modules* wizard launches all the pending `Items
<model-ir.module.config_wizard.item>` sequentially.
