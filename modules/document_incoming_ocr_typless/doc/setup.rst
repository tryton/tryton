*****
Setup
*****

.. _Configure Typeless service:

Configure Typless service
=========================

First you must `register to Typless <https://app.typless.com/>`_ and retrieve
the API key from your profile.

Then create a document type and configured it for the `Incoming Documents
<document_incoming:model-document.incoming>` you want to process

When setting the `OCR Service
<document_incoming_ocr:model-document.incoming.ocr.service>`'s type to
:guilabel:`Typless`, you must fill in the :guilabel:`API Key` with the key and
:guilabel:`Document Type` with the name of the document type created. You can
fill if needed the selection criteria.


.. _Setup fields for Unknown type:

Setup fields for Unknown type
=============================

To process `Incoming Documents <document_incoming:model-document.incoming>`
with :guilabel:`Unknown` type, you should add the metadata field:

   - ``document_type``: ``Constant``

.. _Setup fields for Supplier Invoice type:

Setup fields for Supplier Invoice type
======================================

To process `Incoming Documents <document_incoming:model-document.incoming>`
with :guilabel:`Supplier Invoice` type, you may add the metadata fields:

   - ``company_name``: ``String`` (optional)

   - ``company_tax_identifier``: ``String`` (optional)

   - ``supplier_name``: ``String``

   - ``tax_identifier``: ``String`` (optional)

   - ``currency``: ``Constant`` (optional)

   - ``number``: ``String`` (optional)

   - ``description``: ``String`` (optional)

   - ``invoice_date``: ``Date`` (optional)

   - ``payment_term_date``: ``Date`` (optional)

   - ``total_amount``: ``Number``

   - ``untaxed_amount``: ``Number`` (optional)

   - ``tax_amount``: ``Number`` (optional)

   - ``purchase_orders``: ``String`` (optional)

If you want to process also the invoice lines, you may add the line item fields:

   - ``product_name``: ``String`` (optional)

   - ``description``: ``String``

   - ``unit``: ``String`` (optional)

   - ``quantity``: ``Number``

   - ``unit_price``: ``Number`` (optional if ``amount`` is set)

   - ``amount``: ``Number`` (optional if ``unit_price`` is set)

   - ``purchase_order``: ``String`` (optional)

You can also active the "Vat rate net plugin" with ``untaxed_amount`` as
:guilabel:`Net amount field` and ``total_amount`` as :guilabel:`Gross amount
field`.
