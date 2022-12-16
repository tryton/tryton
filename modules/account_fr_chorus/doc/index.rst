Account French Chorus Module
############################

The account_fr_chorus module allows to send invoices through the `Chorus Pro
<https://chorus-pro.gouv.fr/>`_ portal.

If the party is checked for Chorus Pro, all posted customer invoices are queued to be sent.
A cron job will send them every 15 minutes by default using the credential from
the accounting configuration.

Configuration
*************

The account_fr_chorus module uses the section `account_fr_chorus` to retrieve
the path of the SSL certificates.

- `certificate`: the path to the SSL certificate.

- `privatekey`: the path to the SSL private key.

.. warning::
    The private key must be unencrypted.
..
