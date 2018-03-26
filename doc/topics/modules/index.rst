.. _topics-modules:

=======
Modules
=======

The modules of Tryton extend the functionality of the platform. The server
comes by default with only a basic functionality included in these modules:
``ir``, ``res``.

Module Structure
================

A module is a directory in trytond/modules which contains at least two files:

   * ``__init__.py``: a Tryton module must be a Python module.

   * ``tryton.cfg``: a Configuration file that describes the Tryton module.

``__init__.py`` file
--------------------

It is the Python ``__init__.py`` to define a module. It must contains a method
named `register()` that must register to the pool all the objects of the module.


``tryton.cfg`` file
-------------------

It is a configuration file using the format of `ConfigParser`_ that must
contain `tryton` section with this following name:

   * ``version``: The version number of the module.

   * ``depends``: A one per line list of modules on which this module depends.

   * ``extras_depend``: A one per line list of modules on which this module
     *may* depend.

   * ``xml``: The one per line list of the XML files of the module. They will
     be loaded in the given order at the installation or update of the module.

Here is an example::

    [tryton]
    version=0.0.1
    depends:
        ir
        res
        country
    xml:
        party.xml
        category.xml
        address.xml
        contact_mechanism.xml

Python Files
============

The Python files define the models for the modules.

XML Files
=========

The XML files define data that will be inserted into the database.

There is an rnc for those files stored in ``trytond/tryton.rnc``.

The following snippet gives a first idea of what an xml file looks:

.. highlight:: xml

::

  <?xml version="1.0"?>
  <tryton>
      <data>
          <record model="res.group" id="group_party_admin">
              <field name="name">Party Administration</field>
          </record>
          <record model="res.user-res.group"
              id="user_admin_group_party_admin">
              <field name="user" ref="res.user_admin"/>
              <field name="group" ref="group_party_admin"/>
          </record>

          <menuitem name="Party Management" sequence="0" id="menu_party"
              icon="tryton-users"/>

          <record model="ir.ui.view" id="party_view_tree">
              <field name="model">party.party</field>
              <field name="type">tree</field>
              <field name="arch">
                  <![CDATA[
                  <tree string="Parties">
                      <field name="code"/>
                      <field name="name"/>
                      <field name="lang"/>
                      <field name="vat_code"/>
                      <field name="active" tree_invisible="1"/>
                      <field name="vat_country" tree_invisible="1"/>
                      <field name="vat_number" tree_invisible="1"/>
                  </tree>
                  ]]>
              </field>
          </record>
      </data>
  </tryton>

Here is the list of the tags:

    * ``tryton``: The main tag of the xml

    * ``data``: Define a set of data inside the file. It can have the
      attributes:

        * ``noupdate`` to prevent the framework to update the records,
        * ``skiptest`` to prevent import of data when running tests,
        * ``depends`` to import data only if all modules in the comma separated
          module list value are installed,
        * ``grouped`` to create records at the end with a grouped call.

    * ``record``: Create a record of the model defined by the attribute
      ``model`` in the database. The ``id`` attribute can be used to refer to
      the record later in any xml file.

    * ``field``: Set the value of the field with the name defined by the
      attribute ``name``.

      Here is the list of attributes:

        * ``search``: Only for relation field. It contains a domain which is
          used to search for the value to use. The first value found will be
          used.

        * ``ref``: Only for relation field. It contains an xml id of the
          relation to use as value. It must be prefixed by the module name with
          an ending dot, if the record is defined in an other module.

        * ``eval``: Python code to evaluate and use result as value.
          The following expressions are available:

            * ``time``: The python time_ module
            * ``version``: The current Tryton version
            * ``ref``: A function that converts an XML id into a database id.
            * ``Decimal``: The python Decimal_ object
            * ``datetime``: The python datetime_ module

        * ``pyson``: convert the evaluated value into :ref:`PYSON <ref-pyson>`
          string.

        * ``depends``: set value only if all modules in the comma separated
          module list value are installed.

        .. note::
            Field content is considered as a string. So for fields that require
            other types, it is required to use the ``eval`` attribute.
        ..


    * ``menuitem``: Shortcut to create ir.ui.menu records.

      Here is the list of attributes:

        * ``id``: The id of the menu.

        * ``name``: The name of the menu.

        * ``icon``: The icon of the menu.

        * ``sequence``: The sequence value used to order the menu entries.

        * ``parent``: The xml id of the parent menu.

        * ``action``: The xml id of the action linked to the menu.

        * ``groups``: A list of xml id of group, that have access to the menu,
          separated by commas.

        * ``active``: A boolean telling if the menu is active or not.


.. _ConfigParser: http://docs.python.org/library/configparser.html
.. _time: http://docs.python.org/library/time.html
.. _Decimal: https://docs.python.org/library/decimal.html
.. _datetime: https://docs.python.org/library/datetime.html
