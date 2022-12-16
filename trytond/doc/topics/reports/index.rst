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

Report templates are files with a format supported by relatorio, that contain
snippets of the Genshi templating language.

Here is an example of the text that would be placed in an open document text
document, ``*.odt``, that displays the full name and the address lines of the
first address of each party. The genshi code is placed in the template using
``Functions->Placeholder->Text`` Fields. These are specific to ODT files.

Report API
==========

Python API
----------

.. TODO

XML Description
---------------

When defining an ``ir.action.report`` the following attributes are available:

    * ``name``: The name of the report.

    * ``report_name``: The name of the report model, for example
      my_module.my_report.  This is the name you would use with ``Pool().get``

    * ``model``: If this report is of an existing model this is its name.
      For example my_module.my_model. Custom reports that aren't of a specific
      model will need to leave this blank.

    * ``report``: The path to the template file starting with the module, for
      example my_module/my_report.odt.

    * ``template_extension``: The template format.

    * ``single``: ``True`` if the template works only for one record. If such
      report is called with more than one record, a zip file containing all the
      reports will be generated.


Report Usage
============

Using genshi and open office reports
------------------------------------

Setting up an ODT file
^^^^^^^^^^^^^^^^^^^^^^

If you are creating a report from scratch you should perform the following
steps:

 - Remove user data

    * "File > Properties..."

    * Uncheck "Apply user data"

    * Click on "Reset"

 - Select Style and Formatting

    * Press F11 or "Format > Style and Formatting"

    * Click on the drop down at the right top

    * Select "Load Styles"

    * Click on "From File..."

    * Select a existing report (``company/header_A4.odt``)

 - Set some parameters

    * Set the zoom to 100% (View>Zoom)

    * Set the document in read-only mode (``File>Properties>Security``)
      (Decreases the time it takes to open the document.)

 - Usage

    * Use Liberation fonts (Only necessary if being officially included in
      Tryton)

    * Try to use styles in report templates so that they can be extended.

Using Genshi in an ODT file
^^^^^^^^^^^^^^^^^^^^^^^^^^^
The genshi code is placed in the template using Functions->Placeholder->Text
Fields. These are specific to ``*.odt`` files and can be found in the open
office menu at Insert -> Fields -> Other and then Functions -> Placeholder ->
Text.  Type genshi code into the Placeholder field.  There are alternatives for
embedding genshi that are supported by relatorio but their use is not
encouraged within Tryton.

Also note that relatorio only supports a subset of genshi. The directives that
are supported by relatorio can be found here: `Quick Example`_ .

See genshi's documentation for more information: `Genshi XML Templates`_

Examples
^^^^^^^^

The modules company, account_invoice and stock all contain helpful examples.

Also see relatorio's site for some examples:

 - `Quick Example`_

 - `In Depth Introduction`_

 - `Example Documents`_


Accessing models from within the report
---------------------------------------

By default instances of the models the report is for are passed in to the
report via a list of objects called ``records`` (or ``record`` if ``single`` is
``True``).  These records behave just as they would within trytond itself. You
can access any of the models relations as well.  For example within the invoice
report each object is an invoice and you can access the name of the party of
the invoice via ``invoice.party.name``.  Additional objects can be passed to a
report. This is discussed below in ``Passing custom data to a report``.

Within Tryton the underlying model the report can be found by following the
Menu to ``Administration > UI > Actions > Report``. Furthermore in tryton the
fields for that model can be found by following the menu to ``Administration >
Model > Model``.  Model relation fields can be accessed to any depth, for
example, one could access ``invoice.party.addresses`` to get a list of addresses
for the party of an invoice.

Creating a simple report template for a model from client
---------------------------------------------------------

Once you have created a report template it has to be uploaded to trytond. This
can be done by creating a new record in the
``Administration > UI > Actions > Report`` menu. Just make sure to include the
template file in the content field.

In order to make the report printable from a model create a "Print form"
keyword related to the model where the report should be available.

Creating a simple report template for a model in XML
----------------------------------------------------

Less work has to be done if you just want a simple report representation of a
model.  There are just 2 steps.  First, create a report template file in a
format supported by relatorio.  Second, describe your report in XML making sure
to define the correct ``report_name`` and ``model``.

Replacing existing Tryton reports
---------------------------------

To replace an existing report you must deactivate the old report and activate
the new report.

For example to deactivate the sale report:

.. highlight:: xml

::

  <record model="ir.action.report" id="sale.report_sale">
    <field name="active" eval="False"/>
  </record>

Then you must activate the new sale report that exists in your new module:

.. highlight:: xml

::

  <record model="ir.action.report" id="report_sale">
    <field name="name">Sale</field>
    <field name="report_name">sale.sale</field>
    <field name="model">sale.sale</field>
    <field name="report">my_module/sale.odt</field>
    <field name="template_extension">odt</field>
  </record>

And create the keyword for the new report:

.. highlight:: xml

::

  <record model="ir.action.keyword" id="report_sale_keyword">
      <field name="keyword">form_print</field>
      <field name="model">sale.sale,-1</field>
      <field name="action" ref="report_sale"/>
  </record>

Passing custom data to a report
-------------------------------

In this example ``Report.get_context`` is overridden and an employee
object is set into context.  Now the invoice report will be able to access the
employee object.

.. highlight:: python

::

    from trytond.report import Report
    from tryton.pool import Pool

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

    Pool.register(InvoiceReport, type_='report')

.. _Genshi XML Templates: http://genshi.edgewall.org/wiki/Documentation/0.5.x/xml-templates.html

.. _Quick Example: https://relatorio.readthedocs.io/en/latest/quickexample.html

.. _In Depth Introduction: https://relatorio.readthedocs.io/en/latest/indepthexample.html

.. _Example Documents: http://hg.tryton.org/relatorio/file/default/examples
