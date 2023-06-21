# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import warnings

from sql import Cast, Expression, Literal, Query
from sql.functions import Position, Substring

from trytond.pool import Pool
from trytond.pyson import PYSONEncoder
from trytond.rpc import RPC
from trytond.tools import cached_property
from trytond.transaction import (
    Transaction, inactive_records, without_check_access)

from .field import (
    Field, context_validate, domain_method, domain_validate,
    instantiate_context, search_order_validate)
from .selection import SelectionMixin


class Reference(SelectionMixin, Field):
    '''
    Define a reference field (``str``).
    '''
    _type = 'reference'
    _sql_type = 'VARCHAR'

    def __init__(self, string='', selection=None, sort=True,
            selection_change_with=None, translate=True, search_order=None,
            search_context=None, help='', help_selection=None, required=False,
            readonly=False, domain=None, states=None,
            on_change=None, on_change_with=None, depends=None, context=None,
            loading='lazy', datetime_field=None):
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
        super(Reference, self).__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        self.datetime_field = datetime_field
        if hasattr(selection, 'copy'):
            self.selection = selection.copy()
        else:
            self.selection = selection
        self.selection_change_with = set()
        if selection_change_with:
            warnings.warn('selection_change_with argument is deprecated, '
                'use the depends decorator',
                DeprecationWarning, stacklevel=2)
            self.selection_change_with.update(selection_change_with)
        self.sort = sort
        self.translate_selection = translate
        self.help_selection = help_selection
        self.__search_order = None
        self.search_order = search_order
        self.__search_context = None
        self.search_context = search_context or {}

    __init__.__doc__ += Field.__init__.__doc__

    @property
    def domain(self):
        return self.__domain

    @domain.setter
    def domain(self, value):
        if value is None:
            value = {}
        assert isinstance(value, dict)
        for domain in value.values():
            domain_validate(domain)
        self.__domain = value

    @property
    def search_order(self):
        return self.__search_order

    @search_order.setter
    def search_order(self, value):
        if value is None:
            value = {}
        assert isinstance(value, dict)
        for order in value.values():
            search_order_validate(order)
        self.__search_order = value

    @property
    def search_context(self):
        return self.__search_context

    @search_context.setter
    def search_context(self, value):
        context_validate(value)
        self.__search_context = value

    @cached_property
    def display_depends(self):
        depends = super().display_depends
        if self.datetime_field:
            depends.add(self.datetime_field)
        return depends

    def set_rpc(self, model):
        super(Reference, self).set_rpc(model)
        if not isinstance(self.selection, (list, tuple)):
            assert hasattr(model, self.selection), \
                'Missing %s on model %s' % (self.selection, model.__name__)
            instantiate = 0 if self.selection_change_with else None
            cache = dict(days=1) if instantiate is None else None
            model.__rpc__.setdefault(
                self.selection, RPC(instantiate=instantiate, cache=cache))

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
            except ValueError:
                continue
            if ref_id < 0:
                continue
            res[i] = ref_model + ',' + str(ref_id)
            ref_to_check.setdefault(ref_model, (set(), []))
            ref_to_check[ref_model][0].add(ref_id)
            ref_to_check[ref_model][1].append(i)

        # Check if reference ids still exist
        with inactive_records(), without_check_access():
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
        if value and not isinstance(value, (str, Query, Expression)):
            try:
                value = '%s,%s' % tuple(value)
            except TypeError:
                value = str(value)
        return super(Reference, self).sql_format(value)

    def sql_id(self, column, Model):
        "Return SQL expression for the id part of the field"
        return Cast(Substring(
                column, Position(',', column) + Literal(1)),
            Model.id.sql_type().base)

    @inactive_records
    @domain_method
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
        return (
            self.sql_id(column, Model).in_(query)
            & column.like(target + ',%'))

    def definition(self, model, language):
        encoder = PYSONEncoder()
        definition = super().definition(model, language)
        definition['datetime_field'] = self.datetime_field
        definition['search_context'] = encoder.encode(self.search_context)
        definition['search_order'] = encoder.encode(self.search_order)
        return definition
