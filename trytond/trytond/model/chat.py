# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from collections import namedtuple
from itertools import groupby

from trytond.i18n import gettext, ngettext
from trytond.pool import Pool
from trytond.transaction import Transaction

from .descriptors import dualmethod

ChatMessage = namedtuple(
    'ChatMessage',
    ['msg_id', 'n', 'variables', 'audience'])


class ChatMixin:
    __slots__ = ()

    def chat_language(self, audience='internal'):
        return

    @dualmethod
    def chat_post(
            cls, records, message_id,
            audience='internal', n=None, **variables):
        transaction = Transaction()
        for language, recs in groupby(
                records, key=lambda r: r.chat_language(audience)):
            with transaction.set_context(language=language):
                cls.__queue__._chat_dispatch(
                    records,
                    ChatMessage(
                        msg_id=message_id,
                        n=n,
                        variables=variables,
                        audience=audience,
                        ))

    @classmethod
    def _chat_dispatch(cls, records, message):
        pool = Pool()
        Channel = pool.get('ir.chat.channel')
        transaction = Transaction()
        message = ChatMessage(*message)
        if message.n is None:
            msg = gettext(message.msg_id, **message.variables)
        else:
            msg = ngettext(message.msg_id, message.n, **message.variables)
        with transaction.set_user(0):
            for record in records:
                Channel.post(record, msg, audience=message.audience)
