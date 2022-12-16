******
Design
******

The *Stock Package Shipping Sendcloud Module* introduces the following concepts:

.. _model-carrier.credential.sendcloud:

Sendcloud Credential
====================

This is used to store the credentials needed to connect to the Sendcloud API.
It also defines the sender address for each warehouse and the shipping method
for each carrier.

.. note::

   For carriers without a shipping method, the Sendcloud rules are applied.

.. seealso::

   The credentials can be accessed from the main menu item:

      |Carrier --> Configuration --> Sendcloud Credentials|__

      .. |Carrier --> Configuration --> Sendcloud Credentials| replace:: :menuselection:`Carrier --> Configuration --> Sendcloud Credentials`
      __ https://demo.tryton.org/model/carrier.credential.sendcloud

.. _model-carrier:

Carrier
=======

When the *Stock Package Shipping Sendcloud Module* is activated, carriers gain
some extra properties.
These include a new shipping service "Sendcloud" and a label format.

.. seealso::

   The :doc:`Carrier <carrier:index>` concept is introduced by the
   :doc:`Carrier Module <carrier:index>`.
