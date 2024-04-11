*********************
Development Reference
*********************

The module generates chart of accounts per country and language from the same
original XML thanks to the localize.xsl XSL script.
The command produce on the standard output the desired XML file:

.. code-block:: bash

   xsltproc --stringparam chart <chart> --stringparam lang <lang> localize.xsl account_syscohada.xml | sed -e "s/\$country/<country>/"
