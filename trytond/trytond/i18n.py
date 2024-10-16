# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.tools.string_ import LazyString
from trytond.transaction import Transaction

_none = object()


def _ngettext(message_id, *args, **variables):
    if not Transaction().database:
        return message_id
    pool = Pool()
    try:
        Message = pool.get('ir.message')
    except KeyError:
        return message_id
    if len(args) < 2:
        n, = args
        language = Transaction().language
    else:
        n, language = args
    try:
        module, id_ = message_id.split('.')
    except ValueError:
        if pool.test:
            raise
        return message_id
    try:
        if n is _none:
            return Message.gettext(module, id_, language, **variables)
        else:
            return Message.ngettext(module, id_, n, language, **variables)
    except (KeyError, ValueError):
        if pool.test:
            raise
        return message_id


def gettext(message_id, *args, **variables):
    "Returns the message translated into language"
    return _ngettext(message_id, _none, *args, **variables)


def lazy_gettext(message_id, *args, **variables):
    "Like gettext but the string returned is lazy"
    return LazyString(gettext, message_id, *args, **variables)


def ngettext(message_id, n, *args, **variables):
    return _ngettext(message_id, n, *args, **variables)


def lazy_ngettext(message_id, n, *args, **variables):
    "Like ngettext but the string returned is lazy"
    return LazyString(ngettext, message_id, n, *args, **variables)
