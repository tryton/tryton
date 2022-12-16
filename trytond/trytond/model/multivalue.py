# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .model import Model
from .match import MatchMixin


class MultiValueMixin(object):
    __slots__ = ()

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        Value = pool.get('%s.%s' % (cls.__name__, field))
        assert issubclass(Value, ValueMixin), (
            "%s is not a subclass of ValueMixin" % Value)
        return Value

    def multivalue_records(self, field):
        Value = self.multivalue_model(field)
        for fname, field in self._fields.items():
            if (field._type == 'one2many'
                    and field.model_name == Value.__name__):
                return getattr(self, fname)
        return Value.search([])

    def multivalue_record(self, field, **pattern):
        Value = self.multivalue_model(field)
        for fname, field in Value._fields.items():
            if (field._type == 'many2one'
                    and field.model_name == self.__name__):
                pattern = pattern.copy()
                pattern[fname] = self
                break
        return Value(**pattern)

    def __values(self, field, pattern, match_none=True):
        Value = self.multivalue_model(field)
        # Limit the cache to matching records
        return Value.browse((v for v in self.multivalue_records(field)
            if v.match(pattern, match_none=match_none)))

    def get_multivalue(self, name, **pattern):
        Value = self.multivalue_model(name)
        pattern = filter_pattern(pattern, Value)
        values = self.__values(name, pattern, match_none=False)
        if not values:
            value = Value(**pattern)
            func = getattr(self, 'default_%s' % name, lambda **kw: None)
            setattr(value, name, func(**pattern))
        else:
            value = values[0]
        return getattr(value, name)

    def _multivalue_getter(self, name):
        Value = self.multivalue_model(name)
        value = self.get_multivalue(name)
        if isinstance(value, Model):
            if Value._fields[name]._type == 'reference':
                return str(value)
            return value.id
        elif isinstance(value, (list, tuple)):
            return [r.id for r in value]
        else:
            return value

    def set_multivalue(self, name, value, save=True, **pattern):
        Value = self.multivalue_model(name)
        pattern = filter_pattern(pattern, Value)
        values = self.__values(name, pattern, match_none=True)
        if not values:
            values = [self.multivalue_record(name, **pattern)]
        for record in values:
            setattr(record, name, value)
        if save:
            Value.save(values)
        else:
            return values

    @classmethod
    def _multivalue_setter(cls, records, name, val):
        Value = cls.multivalue_model(name)
        to_save = []
        for record in records:
            to_save.extend(record.set_multivalue(name, val, save=False))
        Value.save(to_save)


class ValueMixin(MatchMixin):

    def match(self, pattern, match_none=True):
        return super(ValueMixin, self).match(pattern, match_none=match_none)


def filter_pattern(pattern, Value):
    return {f: v for f, v in pattern.items() if f in Value._fields}
