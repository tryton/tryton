# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.tools.string_ import LazyString
from trytond.transaction import Transaction


def gettext(message_id, *args, **variables):
    "Returns the message translated into language"
    if not Transaction().database:
        return message_id
    pool = Pool()
    try:
        Message = pool.get('ir.message')
    except KeyError:
        return message_id
    if not args:
        language = Transaction().language
    else:
        language, = args
    try:
        module, id_ = message_id.split('.')
    except ValueError:
        if pool.test:
            raise
        return message_id
    try:
        return Message.gettext(module, id_, language, **variables)
    except (KeyError, ValueError):
        if pool.test:
            raise
        return message_id


def lazy_gettext(message_id, *args, **variables):
    "Like gettext but the string returned is lazy"
    return LazyString(gettext, message_id, *args, **variables)
