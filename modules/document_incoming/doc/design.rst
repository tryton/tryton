******
Design
******

The *Document Incoming Module* introduces the following concepts:

.. _model-document.incoming:

Incoming Document
=================

The *Incoming Document* contains a list of files to process.

When a document is processed, it creates a new record following its type set.

The extension in the name is used to determine the `MIME type
<https://en.wikipedia.org/wiki/Media_type>`_ of the document.

A document can be replaced by a sets of children documents.
In this case the parent document is deactivated.

.. seealso::

   Incoming Documents can be found by opening the main menu item:

      |Documents --> Incoming Documents|__

      .. |Documents --> Incoming Documents| replace:: :menuselection:`Documents --> Incoming Documents`
      __ https://demo.tryton.org/model/document.incoming

Wizards
-------

.. _wizard-document.incoming.split:

Split
^^^^^

The *Split* wizard divides an `Incoming Document <model-document.incoming>` per
pages.
It creates a children document for each set of pages setup.
Pages that are not setup are also always put in a document.

.. _model-document.incoming.configuration:

Configuration
=============

The *Incoming Document Configuration* concept is used to store the settings
which affect how the system behaves in relation to incoming documents.

.. seealso::

   Configuration settings are found by opening the main menu item:

      |Documents --> Configuration --> Incoming Configuration|__

      .. |Documents --> Configuration --> Incoming Configuration| replace:: :menuselection:`Documents --> Configuration --> Incoming Configuration`
      __ https://demo.tryton.org/model/document.incoming.configuration
