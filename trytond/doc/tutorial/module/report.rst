.. _tutorial-module-report:

Create report
=============

A frequent requirement is to generate a printable document for a record.
For that we use ``trytond.report.Report`` which provides the tooling to
render OpenDocument_ based on relatorio_ template.

First we create a ``trytond.report.Report`` class in :file:`opportunity.py`:

.. code-block:: python

    from trytond.report import Report
    ...
    class OpportunityReport(Report):
        __name__ = 'training.opportunity.report'

And we register it in the :class:`~trytond.pool.Pool` as type ``report`` in
:file:`__init__.py`:

.. code-block:: python

    def register():
        ...
        Pool.register(
            opportunity.OpportunityReport,
            module='opportunity', type_='report')


Now we have to create a ``ir.action.report`` and ``ir.action.keyword`` in
:file:`opportunity.xml`:

.. code-block:: xml

   <tryton>
      <data>
         ...
         <record model="ir.action.report" id="report_opportunity">
            <field name="name">Opportunity</field>
            <field name="report_name">training.opportunity.report</field>
            <field name="model">training.opportunity</field>
            <field name="report">opportunity/opportunity.fodt</field>
            <field name="template_extension">odt</field>
         </record>
         <record model="ir.action.keyword" id="report_opportunity_keyword">
            <field name="keyword">form_print</field>
            <field name="model">training.opportunity,-1</field>
            <field name="action" ref="report_opportunity"/>
         </record>
      </data>
   </tryton>

The ``ir.action.report`` links the ``trytond.report.Report`` with the
:class:`~trytond.model.Model`.

``name``
   The string that is shown on the menu.
``report_name``
   The name of the ``trytond.report.Report``.
``model``
   The name of the :class:`~trytond.model.Model`.
``report``
   The path to the template file starting with the module directory.
``template_extension``
   The template format.

And like for the :ref:`wizard <tutorial-module-wizard>`, the
``ir.action.keyword`` makes the ``trytond.report.Report`` available as action
to any ``training.opportunity``.

Finally we create the OpenDocument_ template as :file:`opportunity.fodt` using
LibreOffice_.
We use the `Genshi XML Template Language`_ implemented by relatorio_ using
``Placeholder Text``.
The rendering context contains the variable ``records`` which is a list of
selected record instances.

Here is an example of the directives to insert in the document:

.. code-block:: text

   <for each="opportunity in records">
   Opportunity: <opportunity.rec_name>
   Party: <opportunity.party.rec_name>
   Start Date: <format_date(opportunity.start_date) if opportunity.start_date else ''>
   End Date: <format_date(opportunity.end_date) if opportunity.end_date else ''>

   Comment:
   <for each="line in (opportunity.comment or '').splitlines()">
   <line>
   </for>
   </for>

.. note::
   We must render text field line by line because OpenDocument does not
   consider simple breakline.

Update database
---------------

As we have registered new report and XML records, we need to update the
database with:

.. code-block:: console

   $ trytond-admin -d test --all

And restart the server and reconnect with the client to test rendering the
report:

.. code-block:: console

   $ trytond

Next we create a :ref:`a reporting model using SQL query
<tutorial-module-table-query>`.

.. _OpenDocument: https://en.wikipedia.org/wiki/OpenDocument
.. _relatorio: https://relatorio.tryton.org/
.. _LibreOffice: https://www.libreoffice.org/
.. _Genshi XML Template Language: https://genshi.edgewall.org/wiki/Documentation/xml-templates.html
