*********************
Development Reference
*********************

The *Spanish Account Module* includes the ``normal`` and ``pyme`` charts of
accounts.
The :abbr:`XML (eXtensible Markup Language)` files that contain the localised
charts of account are all generated from the same source XML file.
The :file:`create_chart.xsl` :abbr:`XSLT (XML Stylesheet Language Transform)`
file defines how the source XML file is transformed into each chart of
accounts.

To output a ``<type>`` (either ``normal`` or ``pyme``) of chart of accounts run:

.. code-block:: bash

   xsltproc --stringparam chart <type> create_chart.xsl account.xml
   xsltproc --stringparam chart <type> create_chart.xsl tax.xml
