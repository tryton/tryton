Spanish Account Module
######################

The Spanish account module defines the following charts of account:

 * Plan General Contable Español 2008
 * Plan Contable para PYMES 2008

The chart was published as `REAL DECRETO 1514/2007
<https://www.boe.es/boe/dias/2007/11/20/pdfs/C00001-00152.pdf>`_ on 20th November
2007.

A wizard allows to generate the following AEAT files:

* Modelo 111
* Modelo 115
* Modelo 303

The module generates the chart of accounts for the normal and pyme charts.
The XML files for each variant are generated from the same original XML file
thanks to the create_variant.xsl XSLT script. The script will produce on the
standard output the desired XML file. The XSLT script can be launched with the
following commands::

    xsltproc --stringparam chart <chart> create_chart.xsl account.xml
    xsltproc --stringparam chart <chart> create_chart.xsl tax.xml

where ``chart`` is `normal` or `pyme`
