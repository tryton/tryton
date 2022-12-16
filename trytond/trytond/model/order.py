# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
from trytond.model import fields


def sequence_ordered(field_name='sequence', field_label='Sequence',
        order='ASC NULLS FIRST'):
    "Returns a mixin to order the model by order fields"

    class SequenceOrderedMixin(object):
        "Mixin to order model by a sequence field"

        @classmethod
        def __setup__(cls):
            super(SequenceOrderedMixin, cls).__setup__()
            cls._order = [(field_name, order)] + cls._order

    setattr(SequenceOrderedMixin, field_name, fields.Integer(field_label))
    return SequenceOrderedMixin
