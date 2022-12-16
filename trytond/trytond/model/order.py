# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
from sql import Column

from trytond.i18n import lazy_gettext
from trytond.model import Index, fields


def sequence_ordered(
        field_name='sequence',
        field_label=lazy_gettext('ir.msg_sequence'),
        order='ASC NULLS FIRST'):
    "Returns a mixin to order the model by order fields"
    assert order.startswith('ASC')

    class SequenceOrderedMixin(object):
        "Mixin to order model by a sequence field"
        __slots__ = ()

        @classmethod
        def __setup__(cls):
            super(SequenceOrderedMixin, cls).__setup__()
            table = cls.__table__()
            cls._order = [(field_name, order)] + cls._order
            cls._sql_indexes.add(
                Index(table,
                    (Column(table, field_name), Index.Range(order=order)),
                    (table.id, Index.Range(order=order))))

    setattr(SequenceOrderedMixin, field_name, fields.Integer(field_label))
    return SequenceOrderedMixin
