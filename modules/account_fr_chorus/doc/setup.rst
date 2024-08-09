*****
Setup
*****

.. _Connect to Chorus Pro:

Connect to Chorus Pro
=====================

Tryton uses the API with `OAuth2 <https://en.wikipedia.org/wiki/OAuth#OAuth_2.0>`_.

You must create a PISTE application for Tryton following the `User guide
<https://piste.gouv.fr/en/help-center/guide>`_.
The application must have access to these APIs:

   * Factures
   * Transverses

You must now create a technical account following the `Connection to Chorus Pro
guide
<https://communaute.chorus-pro.gouv.fr/documentation/connection-to-chorus-pro/?lang=en>`_.
And declare an API connection request by PISTE.

You can not enter in the `Configuration <model-account.configuration>` the
Chorus Pro :guilabel:`Login` and Chorus Pro :guilabel:`Password` of a technical
account and :guilabel:`Piste Client ID` and :guilabel:`Piste Client Secret`
from the `PISTE <https://piste.gouv.fr/>`_ connection.

On the configuration you can also choose between the "Qualification" or the
"Production" :guilabel:`Service` and the :guilabel:`Syntax`.

.. note::
   It may take few minutes before the API access is authorized.

.. note::
   Follow `Chorus Pro Quailification Portal
   <https://communaute.chorus-pro.gouv.fr/documentation/chorus-pro-qualification-portal/?lang=en>`_
   to create a dataset for testing.
