******
Design
******

The *EDocument Peppol Module* introduces the following concepts:

.. _model-edocument.peppol:

Document
========

The *Document* keeps track of the document sent or received on the
`Peppol network <https://peppol.org/>`_.

.. seealso::

   Documents can be seen by opening the main menu item:

      |Administration --> Peppol --> Documents|__

      .. |Administration --> Peppol --> Documents| replace:: :menuselection:`Administration --> Peppol --> Documents`
      __ https://demo.tryton.org/model/edocument.peppol

.. _model-edocument.peppol.service:

Service
=======

The *Service* stores the credentials to communicate with the defined service.

The first matching service is used by default to process a `Document
<model-edocument.peppol>`.

.. seealso::

   Services are found by opening the main menu item:

      |Administration --> Peppol --> Services|__

      .. |Administration --> Peppol --> Services| replace:: ::menuselection:`Administration --> Peppol --> Services`
      __ https://demo.tryton.org/model/edocument.peppol.service

.. _model-party.party:

Party
=====

When the *EDocument Peppol Module* is activated, the *Party* gains a new
property to store the type of documents to be sent to the customer via the
Peppol network.

.. seealso::

   The `Party <party:model-party.party>` concept is introduced by the
   :doc:`Party Module <party:index>`.
