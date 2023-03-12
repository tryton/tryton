*****
Usage
*****

.. _Activate extended Intrastat declaration:

Activate extended Intrastat declaration
=======================================

You must activate the :doc:`Incoterm Module <incoterm:index>`.
And on the `Fiscal Year <account:model-account.fiscalyear>` for which you must
file extended declaration, you must check the :guilabel:`Intrastat Extended`
checkbox.

.. _Declaration after Brexit:

Declarations after Brexit
=========================

In order to include the Northern Ireland in the Intrastat declaration, you must
create a dedicated `Country <country:model-country.country>` with the code
``XI`` and use the VAT number starting with ``XI`` as identifier of the counter
parties.
