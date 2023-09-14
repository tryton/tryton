*************
API Reference
*************

.. _Post incoming document:

Post incoming document
======================

The *Incoming Document Module* defines some routes for user applications:

   - ``POST`` ``/<database_name>/document_incoming``:
     Create an `Incoming Document <model-document.incoming>` using:

      - the `JSON <https://en.wikipedia.org/wiki/JSON>`_ Object with at least
        ``data`` key containing the document encoded in `Base64
        <https://en.wikipedia.org/wiki/Base64>`_.
        Other keys are treated as values for the fields of the record.

      - an octet-stream of the ``data``.
        The parameters of the request are treated as values for the fields of
        the record.

     Some request parameters change the behavior of the request:

      - ``process``: a boolean (``1`` or ``0``) to launch the processing on the
        created record.
