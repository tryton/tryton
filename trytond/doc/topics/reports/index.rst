.. _topics-reports:

=======
Reports
=======

Tryton can generate dynamic reports in many formats from templates. The reports
are generated in one step as follows: a report template in a special file
format, explained later, is interpolated with dynamic data and placed into a
document of the same file format. Tryton's ability to generate documents in
this way allows documents to be generated for any editor that supports the Open
Document Format which can be converted to third party formats, such as PDF.
`LibreOffice`_ must be installed on the server host for format conversion.

.. _LibreOffice: https://www.libreoffice.org/

Report Templates
================

Report templates are files with a format supported by relatorio_, that contain
snippets of the Genshi_ templating language.

Here is an example of the text that would be placed in an open document text
document, ``*.odt``, that displays the full name and the address lines of the
first address of each party.
The Genshi code is placed in the template using "Placeholder Text Fields".
These are specific to ODT files.

.. _relatorio: https://relatorio.tryton.org/
.. _Genshi: https://genshi.edgewall.org/

When defining an ``ir.action.report`` the following attributes are available:

``name``
   The name of the report.

``report_name``
   The ``__name__`` of the report model.

``model``
   The :attr:`~trytond.model.Model.__name__` of the
   :class:`~trytond.model.Model` the report is based.
   Report that is not for a specific model, needs to leave this empty.

``report``
   The path to the template file starting with the module directory.

``template_extension``
   The template format.

``single``
   ``True`` if the template works only for one record.
   If such report is called with more than one record, a zip file containing
   all the reports will be generated.

``record_name``
   A Genshi Expression to compute the filename for each record.

Report Usage
============

Using Genshi and Open Office
----------------------------

Setting up an ODT file
^^^^^^^^^^^^^^^^^^^^^^

If you are creating a report from scratch you should perform the following
steps:

 - Remove user data

    * Open :menuselection:`File --> Properties...`

    * Uncheck "Apply user data"

    * Uncheck "Save preview image with this document"

    * Click on "Reset Properties"

 - Set some parameters

    * Set the zoom to 100% (View>Zoom)

    * Set the document to read-only mode (:menuselection:`File --> Properties..
      --> Security`)
      (Decreases the time it takes to open the document.)

 - Usage

    * Use Liberation fonts (Only necessary if being officially included in
      Tryton)

    * Try to use styles in report templates so that they can be extended.

Using Genshi in an ODT file
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Genshi code is placed in the template using "Placeholder Text Fields".
These are specific to ``*.odt`` files and can be found in the open office
:menuselection:`Insert --> Fields --> More Fields...` menu and then by
selecting Functions tab, Placeholder Type and Text Format.
The Genshi code is placed into the Placeholder value.
There are alternatives for embedding Genshi that are supported by relatorio but
their use is not encouraged within Tryton.

See Genshi's documentation for more information: `Genshi XML Template
Language`_.

.. _Genshi XML Template Language: https://genshi.edgewall.org/wiki/Documentation/xml-templates.html

Accessing models from within the report
---------------------------------------

By default instances of the models, the report is for, are passed in to the
report via a list of ``records`` (or ``record`` if ``single`` is ``True``).
These records behave just as they would within ``trytond`` itself.
You can access any of the models relations as well.
For example within the invoice report each record is an invoice and you can
access the name of the party of the invoice via ``invoice.party.name``.
Additional objects can be passed to a report.
This is discussed below in `Passing custom values to a report`_

Within Tryton the model, the report is based on, can be found by opening the
menu item::

   |Administration --> Models --> Models|__

   .. |Administration --> Models --> Models| replace:: :menuselection:`Administration --> Models --> Models`
   __ https://demo.tryton.org/model/ir.model

Furthermore in Tryton the fields for that model can be found by opening the
menu item::

   |Administration --> Models --> Models --> Fields|__

   .. |Administration --> Models --> Models --> Fields| replace:: :menuselection:`Administration --> Models --> Models --> Fields`
   __ https://demo.tryton.org/model/ir.model.field


Creating a simple report template for a model from the client
-------------------------------------------------------------

Once you have created a report template it has to be uploaded to the server.
This can be done by creating a new record by opening the menu item::

   |Administration --> User Interface --> Actions --> Reports|__

   .. |Administration --> User Interface --> Actions --> Reports| replace:: :menuselection:`Administration --> User Interface --> Actions --> Reports`
   __ https://demo.tryton.org/model/ir.action.report

Just make sure to include the template file in the content field.

In order to make the report printable from a record create a ``Print form``
keyword related to the model where the report should be available.

Customizing an existing report from the client
----------------------------------------------

The content of existing reports can be updated from the menu item:

   :menuselection:`Administration --> User Interface --> Actions --> Reports`

The easiest way is to download the existing content, edit it and upload it back
to the server.

.. note::

   It is possible to restore the original content by clearing the content and
   saving the record.


Creating a simple report template for a model within a module
-------------------------------------------------------------

Once you have created a report template stored in your module, you must create
an XML record of ``ir.action.report`` and another XML record of
``ir.action.keyword`` like:

.. code-block:: xml

   <tryton>
      <data>
         <record model="ir.action.report" id="my_report">
            <field name="name">My Report</field>
            <field name="report_name">my_module.my_report</field>
            <field name="model">model.name</field>
            <field name="report">my_module/report.fodt</field>
            <field name="template_extension">odt</field>
         </record>
         <record model="ir.action.keyword" id="my_report_keyword">
            <field name="keyword">form_print</field>
            <field name="model">model.name,-1</field>
            <field name="action" ref="my_report"/>
         </record>
      </data>
   </tryton>

Replacing existing Tryton reports withing a module
--------------------------------------------------

To replace an existing report you must deactivate the old report and activate
the new report.

For example to deactivate the sale report:

.. code-block:: xml

   <record model="ir.action.report" id="sale.report_sale">
      <field name="active" eval="False"/>
   </record>

Then you must create your new sale report:

.. code-block:: xml

   <data>
      <record model="ir.action.report" id="report_sale">
         <field name="name">Sale</field>
         <field name="report_name">sale.sale</field>
         <field name="model">sale.sale</field>
         <field name="report">my_module/sale.odt</field>
         <field name="template_extension">odt</field>
      </record>
      <record model="ir.action.keyword" id="report_sale_keyword">
         <field name="keyword">form_print</field>
         <field name="model">sale.sale,-1</field>
         <field name="action" ref="report_sale"/>
      </record>
   </data>

Passing custom values to a report
---------------------------------

In this example ``Report.get_context`` is overridden and an employee
record is set into context.
Now the invoice report will be able to access the employee record.

.. code-block:: python

    from tryton.pool import Pool
    from trytond.report import Report
    from trytond.transaction import Transaction

    class InvoiceReport(Report):
        __name__ = 'account.invoice'

        @classmethod
        def get_context(cls, records, header, data):
            pool = Pool()
            Employee = pool.get('company.employee')

            context = super().get_context(records, header, data)
            employee_id = Transaction().context.get('employee')
            employee = Employee(employee_id) if employee_id else None
            context['employee'] = employee

            return context
