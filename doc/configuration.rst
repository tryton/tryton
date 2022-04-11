*************
Configuration
*************

The account_es_sii module uses the section ``account_es_sii`` to retrieve
the path of the SSL certificates.

``certificate``
  the path to the SSL certificate.

``privatekey``
  the path to the SSL private key.

.. warning::
    The private key must be unencrypted.

How to obtain the certificate and private keys?
-----------------------------------------------

Both values should be extracted from the p12 certificate issued by the
`FNMT <https://www.cert.fnmt.es/certificados/>`_.
The certificate should be related to the company presenting the information
or an authorized party.

Given a ``cert.p12`` certificate its keys can be extracted with following
commands:

.. code-block:: console

    $ openssl pkcs12 -in cert.p12 -clcerts -nokeys -out public.crt
    $ openssl pkcs12 -in cert.p12 -nocerts -out private.key
    $ openssl rsa -in private.key -out private_unencripted.key

The path to ``private_unencripted.key`` should be used as ``privatekey`` and
the one to ``public.crt`` as ``certificate``.
