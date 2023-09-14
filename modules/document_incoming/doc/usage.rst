*****
Usage
*****

.. _Push documents:

Push documents
==============

You can push `Incoming Documents <model-document.incoming>` into Tryton using a
Web service.

You need first to create a `User Application Key
<trytond:topics-user_application>` from the user preferences.
Then you can post documents on the `URL <https://en.wikipedia.org/wiki/URL>`_
path ``/<database_name>/document_incoming`` with the key in the
``Authorization`` header.
See `Post incoming document` for all the options.

For example using `curl <https://curl.se/>`_, you can push piped document and
process it with:

.. code-block:: shell

   | curl -X POST "https://<host>:<port>/<database_name>/document_incoming?process=1" -H "Authorization: bearer xxxxx" -H "Content-Type:  application/octet-stream" --data-binary @-
