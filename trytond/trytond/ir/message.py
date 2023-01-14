# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.cache import Cache
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.transaction import Transaction


class Message(ModelSQL, ModelView):
    "Message"
    __name__ = "ir.message"

    _message_cache = Cache('ir.message', context=False)
    text = fields.Text("Text", required=True, translate=True)

    @classmethod
    def gettext(cls, *args, **variables):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        module, message_id, language = args

        key = (module, message_id, language)
        text = cls._message_cache.get(key)
        if text is None:
            message_id = ModelData.get_id(module, message_id)
            with Transaction().set_context(language=language):
                message = cls(message_id)

            text = message.text
            cls._message_cache.set(key, text)
        return text if not variables else text % variables

    @classmethod
    def write(cls, messages, values, *args):
        super(Message, cls).write(messages, values, *args)
        cls._message_cache.clear()

    @classmethod
    def delete(cls, messages):
        super(Message, cls).delete(messages)
        cls._message_cache.clear()

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('text',) + tuple(clause[1:])]
