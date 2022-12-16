# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import warnings

from sql import Cast, Literal, Query, Expression
from sql.functions import Substring, Position

from .field import Field, SQLType
from .char import Char
from ...transaction import Transaction
from ...pool import Pool
from ... import backend


class Reference(Field):
    '''
    Define a reference field (``str``).
    '''
    _type = 'reference'

    def __init__(self, string='', selection=None, selection_change_with=None,
            help='', required=False, readonly=False, domain=None, states=None,
            select=False, on_change=None, on_change_with=None, depends=None,
            context=None, loading='lazy'):
        '''
        :param selection: A list or a function name that returns a list.
            The list must be a list of tuples. First member is an internal name
            of model and the second is the user name of model.
        '''
        super(Reference, self).__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            select=select, on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        self.selection = selection or None
        self.selection_change_with = set()
        if selection_change_with:
            warnings.warn('selection_change_with argument is deprecated, '
                'use the depends decorator',
                DeprecationWarning, stacklevel=2)
            self.selection_change_with |= set(selection_change_with)
    __init__.__doc__ += Field.__init__.__doc__

    def get(self, ids, model, name, values=None):
        '''
        Replace removed reference id by None.
        '''
        pool = Pool()
        if values is None:
            values = {}
        res = {}
        for i in values:
            res[i['id']] = i[name]
        ref_to_check = {}
        for i in ids:
            if not (i in res):
                res[i] = None
                continue
            if not res[i]:
                continue
            ref_model, ref_id = res[i].split(',', 1)
            if not ref_model:
                continue
            try:
                ref_id = int(ref_id)
            except Exception:
                continue
            if ref_id < 0:
                continue
            res[i] = ref_model + ',' + str(ref_id)
            ref_to_check.setdefault(ref_model, (set(), []))
            ref_to_check[ref_model][0].add(ref_id)
            ref_to_check[ref_model][1].append(i)

        # Check if reference ids still exist
        with Transaction().set_context(active_test=False), \
                Transaction().set_context(_check_access=False):
            for ref_model, (ref_ids, ids) in ref_to_check.iteritems():
                try:
                    pool.get(ref_model)
                except KeyError:
                    res.update(dict((i, None) for i in ids))
                    continue
                Ref = pool.get(ref_model)
                refs = Ref.search([
                    ('id', 'in', list(ref_ids)),
                    ], order=[])
                refs = map(str, refs)
                for i in ids:
                    if res[i] not in refs:
                        res[i] = None
        return res

    def __set__(self, inst, value):
        from ..model import Model
        if not isinstance(value, (Model, type(None))):
            if isinstance(value, basestring):
                target, value = value.split(',')
            else:
                target, value = value
            Target = Pool().get(target)
            if isinstance(value, dict):
                value = Target(**value)
            else:
                value = Target(value)
        super(Reference, self).__set__(inst, value)

    @staticmethod
    def sql_format(value):
        if not isinstance(value, (basestring, Query, Expression)):
            try:
                value = '%s,%s' % tuple(value)
            except TypeError:
                pass
        return Char.sql_format(value)

    def sql_type(self):
        db_type = backend.name()
        if db_type == 'mysql':
            return SQLType('CHAR', 'VARCHAR(255)')
        return SQLType('VARCHAR', 'VARCHAR')

    def convert_domain(self, domain, tables, Model):
        if '.' not in domain[0]:
            return super(Reference, self).convert_domain(domain, tables, Model)
        pool = Pool()
        name, operator, value, target = domain[:4]
        Target = pool.get(target)
        table, _ = tables[None]
        name, target_name = name.split('.', 1)
        assert name == self.name
        column = self.sql_column(table)
        target_domain = [(target_name,) + tuple(domain[1:3])
            + tuple(domain[4:])]
        if 'active' in Target._fields:
            target_domain.append(('active', 'in', [True, False]))
        query = Target.search(target_domain, order=[], query=True)
        return (Cast(Substring(column,
                    Position(',', column) + Literal(1)),
                Model.id.sql_type().base).in_(query)
            & column.ilike(target + ',%'))
