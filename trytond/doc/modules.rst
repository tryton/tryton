
:tocdepth: 2

Modules
#######

The modules of Tryton extend the functionality of the platform. The server
comes by default with only a few functionality included in those modules:
ir, res, webdav, workflow

Module Structure
****************

A module is a directory in trytond/modules that contains at least two files:

   * ``__init__.py``: a Tryton module must be a Python module.

   * ``__tryton__.py``: a Python file that describes the Tryton module.

``__init__.py`` file
^^^^^^^^^^^^^^^^^^^^

It is the Python ``__init__.py`` to define a module. It must import all the python files from the module.


``__tryton__.py`` file
^^^^^^^^^^^^^^^^^^^^^^

It is a Python file that must contain only dictionary with those keywords:

   * ``name``: The name of the module.

   * ``name_language_code``: The name of the module in the language code.

   * ``version``: The version number of the module.

   * ``author``: The author name of the module.

   * ``email``: The email address of the module (optional).

   * ``website``: The url of the website for the module (optional).

   * ``category``: A category for the module (optional).

   * ``description``: A long description of the module.

   * ``description_language_code``: The long description in the language code.

   * ``depends``: A list of modules on which the module depends.

   * ``xml``: The list of the XML files of the module. There will be loaded at the installation or update of the module.

   * ``translation``: The list of csv files that contains the translation. The name of the files must be the language code.


Here is an example:

.. highlight:: python

::

  {
      "name" : "Party",
      "version" : "0.0.1",
      "author" : "B2CK",
      'email': 'info@b2ck.com',
      'website': 'http://www.tryton.org/',
      "category" : "Generic",
      "description": "Define parties, addresses and co.",
      "depends" : [
          "ir",
          "res",
          "country",
      ],
      "xml" : [
          "party.xml",
          "category.xml",
          "address.xml",
          "contact_mechanism.xml",
      ],
      'translation': [
          'fr_FR.csv',
          'de_DE.csv',
          'es_ES.csv',
      ],
  }

Python files
************

The Python files defines the Models for the modules.

XML files
*********

The XML files defines data that will be inserted into the database.

There is an rnc for those files stored in ``trytond/tryton.rnc``.

The following snippet gives a first idea of what looks a xml file:

.. highlight:: xml

::

  <?xml version="1.0"?>
  <tryton>
      <data>
          <record model="res.group" id="group_party_admin">
              <field name="name">Party Administration</field>
          </record>
          <record model="res.user" id="res.user_admin">
              <field name="groups" eval="[('add', ref('group_party_admin'))]"/>
          </record>

          <menuitem name="Party Management" sequence="0" id="menu_party"
              icon="tryton-users"/>

          <record model="ir.ui.view" id="party_view_tree">
              <field name="model">party.party</field>
              <field name="type">tree</field>
              <field name="arch" type="xml">
                  <![CDATA[
                  <tree string="Parties">
                      <field name="code" select="1"/>
                      <field name="name" select="1"/>
                      <field name="lang" select="2"/>
                      <field name="vat_code" select="1"/>
                      <field name="active" select="2" tree_invisible="1"/>
                      <field name="vat_country" select="2" tree_invisible="1"/>
                      <field name="vat_number" select="2" tree_invisible="1"/>
                  </tree>
                  ]]>
              </field>
          </record>
      </data>
  </tryton>

Here is the list of the tags:

    * ``tryton``: The main tag of the xml

    * ``data``: Define a set of data inside the file. It can have the attributes ``noupdate`` to prevent the framework to update the records.

    * ``record``: Create a record of the model defined by the attribute ``model`` in the database. The ``id`` attribute can be use to refer to the record later in any xml file.

    * ``field``: Set the value of the field with the name defined by the attribute ``name``.

      Here is the list of attributes:

        * ``search``: Only for relation field, it contains a domain on which searching for the first record and use it as value.

        * ``ref``: Only for relation field, it contains a xml id of the relation to use as value. It must be preceed by the module name with a ending dot if the record is defined in an other module.

        * ``eval``: Python code to evaluate and use result as value.

        * ``type``: If set to xml, it will use the CDATA content as value.


    * ``menuitem``: Shortcut to create ir.ui.menu records.

      Here is the list of attributes:

        * ``id``: The id of the menu.

        * ``name``: The name of the menu.

        * ``icon``: The icon of the menu.

        * ``sequence``: The sequence value used to order the menu entries.

        * ``parent``: The xml id of the parent menu.

        * ``action``: The xml id of the action linked to the menu.

        * ``groups``: A list of xml id of group, that have access to the menu, separated by commas.

        * ``active``: A boolean telling if the menu is active or not.
