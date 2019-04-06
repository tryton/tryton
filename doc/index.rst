Belgian Account Module
######################

The Belgian account module defines the standard chart of account.

The module generates french and dutch chart of accounts / chart of taxes. The
french / dutch XML files are generated from the same original XML file thanks
to the localize.xsl XSLT script. The script will produce on the standard output
the desired XML file. The XSLT script can be launched with the following
command::

   xsltproc --stringparam lang <lang> localize.xsl <xml file>

where ``lang`` is either ``fr`` or ``nl``.
