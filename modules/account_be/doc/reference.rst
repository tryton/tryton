*********************
Development Reference
*********************

The *Belgian Account Module* includes the chart of accounts in french and
dutch.
The :abbr:`XML (eXtensible Markup Language)` files that contain the localised
charts of account are all generated from the same source XML file.
The :file:`localize.xsl` :abbr:`XSLT (XML Stylesheet Language Transform)` file
defines how the source XML file is transformed into a localised chart of
accounts.

To output a localised chart of accounts for language ``<lang>`` (either ``fr``
or ``nl``) run:

.. code-block:: bash

   xsltproc --stringparam lang <lang> localize.xsl account_be.xml
