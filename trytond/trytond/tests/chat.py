# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ChatMixin, ModelSQL
from trytond.pool import Pool


class ChatRoom(ChatMixin, ModelSQL):
    __name__ = 'test.chat.room'


def register(module):
    Pool.register(
        ChatRoom,
        module=module, type_='model')
