# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import warnings

from sql import Cast, Literal, Query, Expression
from sql.functions import Substring, Position

from trytond.pool import Pool
from trytond.pyson import PYSONEncoder
from trytond.rpc import RPC
from trytond.transaction import Transaction
from .selection import SelectionMixin
from .field import (Field, search_order_validate, context_validate,
    with_inactive_records, instantiate_context)


class Reference(SelectionMixin, Field):
    '''
    Define a reference field (``str``).
    '''
    _type = 'reference'
    _sql_type = 'VARCHAR'
    _py_type = str

    def __init__(self, string='', selection=None, sort=True,
            selection_change_with=None, translate=True, search_order=None,
            search_context=None, help='', required=False, readonly=False,
            domain=None, states=None, select=False, on_change=None,
            on_change_with=None, depends=None, context=None, loading='lazy',
            datetime_field=None):
        '''
        :param selection: A list or a function name that returns a list.
            The list must be a list of tuples. First member is an internal name
            of model and the second is the user name of model.
        :param sort: A boolean to sort or not the selections.
        :param datetime_field: The name of the field that contains the datetime
            value to read the target records.
        :param search_order: The order to use when searching for a record
        :param search_context: The context to use when searching for a record
        '''
        if datetime_field:
            if depends:
                depends.append(datetime_field)
            else:
                depends = [datetime_field]
        super(Reference, self).__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            select=select, on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        self.datetime_field = datetime_field
        self.selection = selection or None
        self.selection_change_with = set()
        if selection_change_with:
            warnings.warn('selection_change_with argument is deprecated, '
                'use the depends decorator',
                DeprecationWarning, stacklevel=2)
            self.selection_change_with |= set(selection_change_with)
        self.sort = sort
        self.translate_selection = translate
        self.__search_order = None
        self.search_order = search_order
        self.__search_context = None
        self.search_context = search_context or {}

    __init__.__doc__ += Field.__init__.__doc__

    @property
    def search_order(self):
        return self.__search_order

    @search_order.setter
    def search_order(self, value):
        search_order_validate(value)
        self.__search_order = value

    @property
    def search_context(self):
        return self.__search_context

    @search_context.setter
    def search_context(self, value):
        context_validate(value)
        self.__search_context = value

    def set_rpc(self, model):
        super(Reference, self).set_rpc(model)
        if not isinstance(self.selection, (list, tuple)):
            assert hasattr(model, self.selection), \
                'Missing %s on model %s' % (self.selection, model.__name__)
            instantiate = 0 if self.selection_change_with else None
            model.__rpc__.setdefault(
                self.selection, RPC(instantiate=instantiate))

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
            for ref_model, (ref_ids, ids) in ref_to_check.items():
                try:
                    pool.get(ref_model)
                except KeyError:
                    res.update(dict((i, None) for i in ids))
                    continue
                Ref = pool.get(ref_model)
                refs = Ref.search([
                    ('id', 'in', list(ref_ids)),
                    ], order=[])
                refs = list(map(str, refs))
                for i in ids:
                    if res[i] not in refs:
                        res[i] = None
        return res

    def __set__(self, inst, value):
        from ..model import Model
        if not isinstance(value, (Model, type(None))):
            if isinstance(value, str):
                target, value = value.split(',')
            else:
                target, value = value
            Target = Pool().get(target)
            ctx = instantiate_context(self, inst)
            with Transaction().set_context(ctx):
                if isinstance(value, dict):
                    value = Target(**value)
                else:
                    value = Target(value)
        super(Reference, self).__set__(inst, value)

    def sql_format(self, value):
        if not isinstance(value, (str, Query, Expression)):
            try:
                value = '%s,%s' % tuple(value)
            except TypeError:
                pass
        return super(Reference, self).sql_format(value)

    @with_inactive_records
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

    def definition(self, model, language):
        encoder = PYSONEncoder()
        definition = super().definition(model, language)
        definition['datetime_field'] = self.datetime_field
        definition['search_context'] = encoder.encode(self.search_context)
        definition['search_order'] = encoder.encode(self.search_order)
        return definition
