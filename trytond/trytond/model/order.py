# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
from sql import Null, Column
from sql.operators import Equal, NotEqual
from sql.conditionals import Case

from trytond.model import fields


def sequence_ordered(field_name='sequence', field_label='Sequence',
        order='ASC', null_first=True):
    "Returns a mixin to order the model by order fields"

    class SequenceOrderedMixin(object):
        "Mixin to order model by a sequence field"

        @classmethod
        def __setup__(cls):
            super(SequenceOrderedMixin, cls).__setup__()
            cls._order = [(field_name, order)] + cls._order

    setattr(SequenceOrderedMixin, field_name, fields.Integer(field_label))

    @classmethod
    def order_function(cls, tables):
        table, _ = tables[None]
        operator = Equal
        if not null_first:
            operator = NotEqual
        field = Column(table, field_name)
        return [Case((operator(field, Null), 0), else_=1), field]
    setattr(SequenceOrderedMixin, 'order_%s' % field_name, order_function)
    return SequenceOrderedMixin
