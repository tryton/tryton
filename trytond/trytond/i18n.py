# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.transaction import Transaction
from trytond.pool import Pool


def gettext(message_id, *args, **variables):
    "Returns the message translated into language"
    pool = Pool()
    Message = pool.get('ir.message')
    if not args:
        language = Transaction().language
    else:
        language, = args
    try:
        module, id_ = message_id.split('.')
    except ValueError:
        return message_id
    try:
        return Message.gettext(module, id_, language, **variables)
    except KeyError:
        return message_id
