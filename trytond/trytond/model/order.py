# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.

from functools import total_ordering

from sql import Column

from trytond.i18n import lazy_gettext
from trytond.model import Index, Model, fields


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
            super().__setup__()
            table = cls.__table__()
            cls._order = [(field_name, order)] + cls._order
            cls._sql_indexes.add(
                Index(table,
                    (Column(table, field_name), Index.Range(order=order)),
                    (table.id, Index.Range(order=order))))

    setattr(SequenceOrderedMixin, field_name, fields.Integer(field_label))
    return SequenceOrderedMixin


@total_ordering
class _reversor:
    __slots__ = ('_obj',)

    def __init__(self, obj):
        self._obj = obj

    def __eq__(self, other):
        if not isinstance(other, _reversor):
            return NotImplemented
        return self._obj == other._obj

    def __lt__(self, other):
        if not isinstance(other, _reversor):
            return NotImplemented
        return self._obj > other._obj


class _attrgetter:
    __slots__ = ('_attr', '_null', '_reverse')

    def __init__(self, attr, null=None, reverse=False):
        self._attr = attr
        self._null = null
        self._reverse = reverse

    def __call__(self, obj):
        for name in self._attr.split('.'):
            obj = getattr(obj, name, None)
            if obj is None:
                break
        if isinstance(obj, Model):
            Target = obj.__class__
            oname = 'id'
            if (Target._rec_name in Target._fields
                    and Target._fields[Target._rec_name].sortable(Target)):
                oname = Target._rec_name
            if (Target._order_name in Target._fields
                    and Target._fields[Target._order_name].sortable(Target)):
                oname = Target._order_name
            obj = getattr(obj, oname)
        null = obj is None
        if self._null is not None:
            if null:
                null = self._null
            else:
                null = not self._null
        value = (null, obj)
        if self._reverse:
            value = _reversor(value)
        return value


def sort(records, order):
    "Return a new list of records ordered"
    if not order:
        return records
    getters = []
    for oexpr, otype in order:
        try:
            otype, null_ordering = otype.split(' ', 1)
        except ValueError:
            null_ordering = None
        reverse = otype == 'DESC'
        if null_ordering == 'NULLS FIRST':
            null = reverse
        elif null_ordering == 'NULLS LAST':
            null = not reverse
        else:
            null = None
        getters.append(_attrgetter(oexpr, null, reverse))

    def func(obj):
        return tuple(getter(obj) for getter in getters)
    return sorted(records, key=func)
