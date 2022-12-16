#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
try:
    import simplejson as json
except ImportError:
    import json
import datetime
from dateutil.relativedelta import relativedelta
from functools import reduce


class PYSON(object):

    def pyson(self):
        raise NotImplementedError

    def types(self):
        raise NotImplementedError

    @staticmethod
    def eval(dct, context):
        raise NotImplementedError

    def __invert__(self):
        if self.types() != set([bool]):
            return Not(Bool(self))
        else:
            return Not(self)

    def __and__(self, other):
        if (isinstance(other, PYSON)
                and other.types() != set([bool])):
            other = Bool(other)
        if (isinstance(self, And)
                and not isinstance(self, Or)):
            self._statements.append(other)
            return self
        if self.types() != set([bool]):
            return And(Bool(self), other)
        else:
            return And(self, other)

    def __or__(self, other):
        if (isinstance(other, PYSON)
                and other.types() != set([bool])):
            other = Bool(other)
        if isinstance(self, Or):
            self._statements.append(other)
            return self
        if self.types() != set([bool]):
            return Or(Bool(self), other)
        else:
            return Or(self, other)

    def __eq__(self, other):
        return Equal(self, other)

    def __ne__(self, other):
        return Not(Equal(self, other))

    def __gt__(self, other):
        return Greater(self, other)

    def __ge__(self, other):
        return Greater(self, other, True)

    def __lt__(self, other):
        return Less(self, other)

    def __le__(self, other):
        return Less(self, other, True)

    def get(self, k, d=''):
        return Get(self, k, d)

    def in_(self, obj):
        return In(self, obj)

    def contains(self, k):
        return In(k, self)


class PYSONEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, PYSON):
            return obj.pyson()
        elif isinstance(obj, datetime.date):
            if isinstance(obj, datetime.datetime):
                return DateTime(obj.year, obj.month, obj.day,
                        obj.hour, obj.minute, obj.second, obj.microsecond
                        ).pyson()
            else:
                return Date(obj.year, obj.month, obj.day).pyson()
        return super(PYSONEncoder, self).default(obj)


class PYSONDecoder(json.JSONDecoder):

    def __init__(self, context=None):
        self.__context = context or {}
        super(PYSONDecoder, self).__init__(object_hook=self._object_hook)

    def _object_hook(self, dct):
        if '__class__' in dct:
            klass = globals().get(dct['__class__'])
            if klass and hasattr(klass, 'eval'):
                return klass.eval(dct, self.__context)
        return dct


class Eval(PYSON):

    def __init__(self, value, default=''):
        super(Eval, self).__init__()
        self._value = value
        self._default = default

    def pyson(self):
        return {
            '__class__': 'Eval',
            'v': self._value,
            'd': self._default,
            }

    def types(self):
        if isinstance(self._default, PYSON):
            return self._default.types()
        else:
            return set([type(self._default)])

    @staticmethod
    def eval(dct, context):
        return context.get(dct['v'], dct['d'])


class Not(PYSON):

    def __init__(self, value):
        super(Not, self).__init__()
        if isinstance(value, PYSON):
            assert value.types() == set([bool]), 'value must be boolean'
        else:
            assert isinstance(value, bool), 'value must be boolean'
        self._value = value

    def pyson(self):
        return {
            '__class__': 'Not',
            'v': self._value,
            }

    def types(self):
        return set([bool])

    @staticmethod
    def eval(dct, context):
        return not dct['v']


class Bool(PYSON):

    def __init__(self, value):
        super(Bool, self).__init__()
        self._value = value

    def pyson(self):
        return {
            '__class__': 'Bool',
            'v': self._value,
            }

    def types(self):
        return set([bool])

    @staticmethod
    def eval(dct, context):
        return bool(dct['v'])


class And(PYSON):

    def __init__(self, *statements):
        super(And, self).__init__()
        for statement in statements:
            if isinstance(statement, PYSON):
                assert statement.types() == set([bool]), \
                    'statement must be boolean'
            else:
                assert isinstance(statement, bool), \
                    'statement must be boolean'
        assert len(statements) >= 2, 'must have at least 2 statements'
        self._statements = list(statements)

    def pyson(self):
        return {
            '__class__': 'And',
            's': self._statements,
            }

    def types(self):
        return set([bool])

    @staticmethod
    def eval(dct, context):
        return bool(reduce(lambda x, y: x and y, dct['s']))


class Or(And):

    def pyson(self):
        res = super(Or, self).pyson()
        res['__class__'] = 'Or'
        return res

    @staticmethod
    def eval(dct, context):
        return bool(reduce(lambda x, y: x or y, dct['s']))


class Equal(PYSON):

    def __init__(self, statement1, statement2):
        super(Equal, self).__init__()
        if isinstance(statement1, PYSON):
            types1 = statement1.types()
        else:
            types1 = set([type(statement1)])
        if isinstance(statement2, PYSON):
            types2 = statement2.types()
        else:
            types2 = set([type(statement2)])
        assert types1 == types2, 'statements must have the same type'
        self._statement1 = statement1
        self._statement2 = statement2

    def pyson(self):
        return {
            '__class__': 'Equal',
            's1': self._statement1,
            's2': self._statement2,
            }

    def types(self):
        return set([bool])

    @staticmethod
    def eval(dct, context):
        return dct['s1'] == dct['s2']


class Greater(PYSON):

    def __init__(self, statement1, statement2, equal=False):
        super(Greater, self).__init__()
        for i in (statement1, statement2):
            if isinstance(i, PYSON):
                assert i.types().issubset(set([int, long, float])), \
                    'statement must be an integer or a float'
            else:
                assert isinstance(i, (int, long, float)), \
                    'statement must be an integer or a float'
        if isinstance(equal, PYSON):
            assert equal.types() == set([bool])
        else:
            assert isinstance(equal, bool)
        self._statement1 = statement1
        self._statement2 = statement2
        self._equal = equal

    def pyson(self):
        return {
            '__class__': 'Greater',
            's1': self._statement1,
            's2': self._statement2,
            'e': self._equal,
            }

    def types(self):
        return set([bool])

    @staticmethod
    def _convert(dct):
        for i in ('s1', 's2'):
            if not isinstance(dct[i], (int, long, float)):
                dct = dct.copy()
                dct[i] = float(dct[i])
        return dct

    @staticmethod
    def eval(dct, context):
        dct = Greater._convert(dct)
        if dct['e']:
            return dct['s1'] >= dct['s2']
        else:
            return dct['s1'] > dct['s2']


class Less(Greater):

    def pyson(self):
        res = super(Less, self).pyson()
        res['__class__'] = 'Less'
        return res

    @staticmethod
    def eval(dct, context):
        dct = Less._convert(dct)
        if dct['e']:
            return dct['s1'] <= dct['s2']
        else:
            return dct['s1'] < dct['s2']


class If(PYSON):

    def __init__(self, condition, then_statement, else_statement=None):
        super(If, self).__init__()
        if isinstance(condition, PYSON):
            assert condition.types() == set([bool]), \
                'condition must be boolean'
        else:
            assert isinstance(condition, bool), 'condition must be boolean'
        if isinstance(then_statement, PYSON):
            then_types = then_statement.types()
        else:
            then_types = set([type(then_statement)])
        if isinstance(else_statement, PYSON):
            assert then_types == else_statement.types(), \
                'then and else statements must be the same type'
        else:
            assert then_types == set([type(else_statement)]), \
                'then and else statements must be the same type'
        self._condition = condition
        self._then_statement = then_statement
        self._else_statement = else_statement

    def pyson(self):
        return {
            '__class__': 'If',
            'c': self._condition,
            't': self._then_statement,
            'e': self._else_statement,
            }

    def types(self):
        if isinstance(self._then_statement, PYSON):
            return self._then_statement.types()
        else:
            return set([type(self._then_statement)])

    @staticmethod
    def eval(dct, context):
        if dct['c']:
            return dct['t']
        else:
            return dct['e']


class Get(PYSON):

    def __init__(self, obj, key, default=''):
        super(Get, self).__init__()
        if isinstance(obj, PYSON):
            assert obj.types() == set([dict]), 'obj must be a dict'
        else:
            assert isinstance(obj, dict), 'obj must be a dict'
        self._obj = obj
        if isinstance(key, PYSON):
            assert key.types() == set([str]), 'key must be a string'
        else:
            assert type(key) == str, 'key must be a string'
        self._key = key
        self._default = default

    def pyson(self):
        return {
            '__class__': 'Get',
            'v': self._obj,
            'k': self._key,
            'd': self._default,
            }

    def types(self):
        if isinstance(self._default, PYSON):
            return self._default.types()
        else:
            return set([type(self._default)])

    @staticmethod
    def eval(dct, context):
        return dct['v'].get(dct['k'], dct['d'])


class In(PYSON):

    def __init__(self, key, obj):
        super(In, self).__init__()
        if isinstance(key, PYSON):
            assert key.types().issubset(set([str, int, long])), \
                'key must be a string or an integer or a long'
        else:
            assert type(key) in [str, int, long], \
                'key must be a string or an integer or a long'
        if isinstance(obj, PYSON):
            assert obj.types().issubset(set([dict, list])), \
                'obj must be a dict or a list'
            if obj.types() == set([dict]):
                assert type(key) == str, 'key must be a string'
        else:
            assert type(obj) in [dict, list]
            if type(obj) == dict:
                assert type(key) == str, 'key must be a string'
        self._key = key
        self._obj = obj

    def pyson(self):
        return {
            '__class__': 'In',
            'k': self._key,
            'v': self._obj,
            }

    def types(self):
        return set([bool])

    @staticmethod
    def eval(dct, context):
        return dct['k'] in dct['v']


class Date(PYSON):

    def __init__(self, year=None, month=None, day=None,
            delta_years=0, delta_months=0, delta_days=0):
        super(Date, self).__init__()
        for i in (year, month, day, delta_years, delta_months, delta_days):
            if isinstance(i, PYSON):
                assert i.types().issubset(set([int, long, type(None)])), \
                    '%s must be an integer or None' % (i,)
            else:
                assert isinstance(i, (int, long, type(None))), \
                    '%s must be an integer or None' % (i,)
        self._year = year
        self._month = month
        self._day = day
        self._delta_years = delta_years
        self._delta_months = delta_months
        self._delta_days = delta_days

    def pyson(self):
        return {
            '__class__': 'Date',
            'y': self._year,
            'M': self._month,
            'd': self._day,
            'dy': self._delta_years,
            'dM': self._delta_months,
            'dd': self._delta_days,
            }

    def types(self):
        return set([datetime.date])

    @staticmethod
    def eval(dct, context):
        return datetime.date.today() + relativedelta(
            year=dct['y'],
            month=dct['M'],
            day=dct['d'],
            years=dct['dy'],
            months=dct['dM'],
            days=dct['dd'],
            )


class DateTime(Date):

    def __init__(self, year=None, month=None, day=None,
            hour=None, minute=None, second=None, microsecond=None,
            delta_years=0, delta_months=0, delta_days=0,
            delta_hours=0, delta_minutes=0, delta_seconds=0,
            delta_microseconds=0):
        super(DateTime, self).__init__(year=year, month=month, day=day,
                delta_years=delta_years, delta_months=delta_months,
                delta_days=delta_days)
        for i in (hour, minute, second, microsecond,
                delta_hours, delta_minutes, delta_seconds, delta_microseconds):
            if isinstance(i, PYSON):
                assert i.types() == set([int, long, type(None)]), \
                    '%s must be an integer or None' % (i,)
            else:
                assert isinstance(i, (int, long, type(None))), \
                    '%s must be an integer or None' % (i,)
        self._hour = hour
        self._minute = minute
        self._second = second
        self._microsecond = microsecond
        self._delta_hours = delta_hours
        self._delta_minutes = delta_minutes
        self._delta_seconds = delta_seconds
        self._delta_microseconds = delta_microseconds

    def pyson(self):
        res = super(DateTime, self).pyson()
        res['__class__'] = 'DateTime'
        res['h'] = self._hour
        res['m'] = self._minute
        res['s'] = self._second
        res['ms'] = self._microsecond
        res['dh'] = self._delta_hours
        res['dm'] = self._delta_minutes
        res['ds'] = self._delta_seconds
        res['dms'] = self._delta_microseconds
        return res

    def types(self):
        return set([datetime.datetime])

    @staticmethod
    def eval(dct, context):
        return datetime.datetime.now() + relativedelta(
            year=dct['y'],
            month=dct['M'],
            day=dct['d'],
            hour=dct['h'],
            minute=dct['m'],
            second=dct['s'],
            microsecond=dct['ms'],
            years=dct['dy'],
            months=dct['dM'],
            days=dct['dd'],
            hours=dct['dh'],
            minutes=dct['dm'],
            seconds=dct['ds'],
            microseconds=dct['dms'],
            )


class Len(PYSON):

    def __init__(self, value):
        super(Len, self).__init__()
        if isinstance(value, PYSON):
            assert value.types().issubset(set([dict, list, str])), \
                'value must be a dict or a list or a string'
        else:
            assert type(value) in [dict, list, str], \
                'value must be a dict or list or a string'
        self._value = value

    def pyson(self):
        return {
            '__class__': 'Len',
            'v': self._value,
            }

    def types(self):
        return set([int, long])

    @staticmethod
    def eval(dct, context):
        return len(dct['v'])

CONTEXT = {
    'Eval': Eval,
    'Not': Not,
    'Bool': Bool,
    'And': And,
    'Or': Or,
    'Equal': Equal,
    'Greater': Greater,
    'Less': Less,
    'If': If,
    'Get': Get,
    'In': In,
    'Date': Date,
    'DateTime': DateTime,
    'Len': Len,
}
