.. _model-ir.chat.channel:

Chat Channel
============

A *Channel* stores the `model-ir.chat.message` linked to a
:class:`~trytond.model.ChatMixin`.


.. _model-ir.chat.follower:

Chat Follower
=============

The *Follower* concept stores the `model-res.user` or *email* to
notify for new message on the linked `model-ir.chat.channel`.


.. _model-ir.chat.message:

Chat Message
============

A *Message* stores the content posted to a `model-ir.chat.channel`.
The audience property defines who can see the message.
