.. _ref-bus:
.. module:: trytond.bus

Bus
===

The Tryton server listens on ``POST`` requests on the routes matching
``/<database_name>/bus`` and replies with JSON_ dictionary containing:

``channel``
   The channel on which this message has been received.

``message``
   A dictionary that is the message the client must handle.
   The specification of the message depends of its type.

   All messages should at least content a unique identifier in the key
   ``message_id`` and their type in the key of the same name.

Client sending their requests on the route must be authenticated.
The request must submit a JSON_ dictionary containing:

``last_message``
   A value identifying the last message received by the client.
   This value can be ``null``.

``channels``
   A list of strings denoting the channels the client is listening to.

.. _JSON: https://en.wikipedia.org/wiki/JSON

.. class:: Bus

   Expose two methods that are used by the framework:
   ``publish`` and ``subscribe``.

.. classmethod:: Bus.publish(channel, message)

   Send a message to a specific channel.

   Implemented messages are:

      * :ref:`Notifications <bus_notification_spec>`

.. classmethod:: Bus.subscribe(database, channels[, last_message])

   Subscribe a user client to some ``channels`` of messages.

   The ``message_id`` parameter defines the last message id received by the
   client.
   It defaults to ``None`` when not provided.

The default implementation provides an helper method to construct the response:

.. classmethod:: Bus.create_response(channel, message)

   Create a dictionary suitable as a response from a message and a timestamp.

   ``channel`` is the channel on which the message has been received.

   ``message`` is the content of the message sent to the client.

.. note::

   The implementation relies on the fact that the order of the messages
   received is consistent across different trytond instances allowing to
   dispatch the request to any trytond server running.

Notification
------------

Tryton provides a shortcut to send a notification with the ``notify`` function.

.. function:: notify(title[, body[, priority[, user[, client]]]])

   Send a text message to a user's client to be displayed using a notification
   popup. The meaning of ``title``, ``body`` and ``priority`` is defined in
   :ref:`bus_notification_spec`.

   If ``user`` is not set, the current
   :attr:`~trytond.transaction.Transaction.user` is used.
   Otherwise ``user`` is the user id to notify.

   If ``client`` is not set then every client of the user receives the message.
   If ``client`` and ``user`` are not set, the system send the notification to
   the current user client.
   Otherwise the notification is sent to the client whose id matches
   ``client``.

.. _bus_notification_spec:

Notification message
~~~~~~~~~~~~~~~~~~~~

Notification messages are composed of four parts:

``kind``
   The string ``notification``.

``title``
   A string containing a one-line summary of the message.

``body``
   A string containing a short informative message for the user.
   It can span multiple lines but no markup is allowed.

``priority``
   An integer between 0 (low priority) to 3 (urgent).
   The notification priority on the platform supporting it.
