# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import warnings
from collections import defaultdict
from itertools import chain

from sql import Literal
from sql.conditionals import Coalesce
from sql.operators import Exists

import trytond.config as config
from trytond.pool import Pool
from trytond.pyson import PYSONEncoder
from trytond.tools import cached_property, grouped_slice
from trytond.transaction import Transaction

from .field import (
    Field, context_validate, domain_method, domain_validate, get_eval_fields,
    instanciate_values, instantiate_context, search_order_validate,
    size_validate)


class One2Many(Field):
    _type = 'one2many'
    _py_type = tuple

    def __init__(self, model_name, field, string='', add_remove=None,
            order=None, datetime_field=None, size=None, search_order=None,
            search_context=None, help='', required=False, readonly=False,
            domain=None, filter=None, states=None, on_change=None,
            on_change_with=None, depends=None, context=None, loading='lazy'):
        '''
        :param model_name: The name of the target model.
        :param field: The name of the field that handle the reverse many2one or
            reference.
        :param add_remove: A list that defines a domain on add/remove.
            See domain on ModelStorage.search.
        :param order:  a list of tuples that are constructed like this:
            ``('field name', 'DESC|ASC')``
            allowing to specify the order of result.
        :param datetime_field: The name of the field that contains the datetime
            value to read the target records.
        :param search_order: The order to use when searching for records
        :param search_context: The context to use when searching for a record
        :param filter: A domain to filter target records.
        '''
        super().__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        self.model_name = model_name
        self.field = field
        self.__add_remove = None
        self.add_remove = add_remove
        self.order = order
        self.datetime_field = datetime_field
        self.__size = None
        self.size = size
        self.__search_order = None
        self.search_order = search_order
        self.__search_context = None
        self.search_context = search_context or {}
        self.__filter = None
        self.filter = filter

    if __init__.__doc__:
        __init__.__doc__ += Field.__init__.__doc__

    def _get_add_remove(self):
        return self.__add_remove

    def _set_add_remove(self, value):
        if value is not None:
            domain_validate(value)
        self.__add_remove = value

    add_remove = property(_get_add_remove, _set_add_remove)

    def _get_size(self):
        return self.__size

    def _set_size(self, value):
        size_validate(value)
        self.__size = value

    size = property(_get_size, _set_size)

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

    @cached_property
    def display_depends(self):
        depends = super().display_depends
        if self.datetime_field:
            depends.add(self.datetime_field)
        return depends

    @cached_property
    def edition_depends(self):
        depends = super().edition_depends
        for attribute in ['add_remove', 'size']:
            depends |= get_eval_fields(getattr(self, attribute))
        return depends

    @cached_property
    def validation_depends(self):
        return super().validation_depends | get_eval_fields(self.size)

    def sql_type(self):
        return None

    @property
    def filter(self):
        return self.__filter

    @filter.setter
    def filter(self, value):
        if value is not None:
            domain_validate(value)
        self.__filter = value

    def get(self, ids, model, name, values=None):
        '''
        Return target records ordered.
        '''
        Target = self.get_target()
        field = Target._fields[self.field]
        reference_key = field._type == 'reference'
        res = {}
        for i in ids:
            res[i] = []

        if field.sortable(Target):
            if reference_key:
                order = [(self.field, None)]
            else:
                order = [(self.field + '.id', None)]
        else:
            order = []
        if self.order:
            order += self.order
        elif Target._order:
            order += Target._order
        targets = []
        for sub_ids in grouped_slice(ids):
            if reference_key:
                references = ['%s,%s' % (model.__name__, x) for x in sub_ids]
                clause = [(self.field, 'in', references)]
            else:
                clause = [(self.field, 'in', list(sub_ids))]
            if self.filter:
                clause.append(self.filter)
            targets.append([r.id for r in Target.search(clause, order=order)])
        to_read = list(chain(*targets))
        targets = {t['id']: t
            for t in Target.read(to_read, ['id', self.field])}

        for read_id in to_read:
            target = targets[read_id]
            if reference_key:
                _, origin_id = target[self.field].split(',', 1)
                origin_id = int(origin_id)
            else:
                origin_id = target[self.field]
            res[origin_id].append(target['id'])
        return dict((key, tuple(value)) for key, value in res.items())

    def set(self, Model, name, ids, values, *args):
        '''
        Set the values.
        values: A list of tuples:
            (``create``, ``[{<field name>: value}, ...]``),
            (``write``, [``<ids>``, ``{<field name>: value}``, ...]),
            (``delete``, ``<ids>``),
            (``add``, ``<ids>``),
            (``remove``, ``<ids>``),
            (``copy``, ``<ids>``, ``[{<field name>: value}, ...]``)
        '''
        Target = self.get_target()
        field = Target._fields[self.field]
        to_create = []
        to_write = []
        to_delete = []

        def search_clause(ids):
            if field._type == 'reference':
                references = ['%s,%s' % (Model.__name__, x) for x in ids]
                return (self.field, 'in', references)
            else:
                return (self.field, 'in', ids)

        def field_value(record_id):
            if field._type == 'reference':
                return '%s,%s' % (Model.__name__, record_id)
            else:
                return record_id

        def target_value(record):
            if record is None:
                return None
            if field._type == 'reference':
                return str(record)
            else:
                return record.id

        def create(ids, vlist):
            for record_id in ids:
                value = field_value(record_id)
                for values in vlist:
                    values = values.copy()
                    values[self.field] = value
                    to_create.append(values)

        def write(_, *args):
            actions = iter(args)
            to_write.extend(sum(((Target.browse(ids), values)
                        for ids, values in zip(actions, actions)), ()))

        def delete(_, target_ids):
            to_delete.extend(Target.browse(target_ids))

        def add(ids, target_ids):
            target_ids = list(map(int, target_ids))
            if not target_ids:
                return
            targets = Target.browse(target_ids)
            for record_id in ids:
                fvalue = field_value(record_id)
                to_update = [t for t in targets
                    if target_value(getattr(t, self.field)) != fvalue]
                if to_update:
                    to_write.extend((to_update, {
                                self.field: fvalue,
                                }))

        def remove(ids, target_ids):
            target_ids = list(map(int, target_ids))
            if not target_ids:
                return
            for sub_ids in grouped_slice(target_ids):
                targets = Target.search([
                        search_clause(ids),
                        ('id', 'in', list(sub_ids)),
                        ])
                to_write.extend((targets, {
                            self.field: None,
                            }))

        def copy(ids, copy_ids, default=None):
            copy_ids = list(map(int, copy_ids))

            if default is None:
                default = {}
            default = default.copy()
            copies = Target.browse(copy_ids)
            for record_id in ids:
                default[self.field] = field_value(record_id)
                Target.copy(copies, default=default)

        actions = {
            'create': create,
            'write': write,
            'delete': delete,
            'add': add,
            'remove': remove,
            'copy': copy,
            }
        args = iter((ids, values) + args)
        for ids, values in zip(args, args):
            if not values:
                continue
            for value in values:
                action = value[0]
                args = value[1:]
                actions[action](ids, *args)
        # Ordered operations to avoid uniqueness/overlapping constraints
        if to_delete:
            Target.delete(to_delete)
        if to_write:
            Target.write(*to_write)
        if to_create:
            Target.create(to_create)

    def get_target(self):
        'Return the target Model'
        return Pool().get(self.model_name)

    def __set__(self, inst, value):
        Target = self.get_target()
        ctx = instantiate_context(self, inst)
        extra = {}
        if self.field:
            extra[self.field] = inst
        with Transaction().set_context(ctx):
            records = instanciate_values(Target, value, **extra)
        super().__set__(inst, records)

    def remove(self, inst, records):
        records = set(records)
        if inst._removed is None:
            inst._removed = defaultdict(set)
        inst._removed[self.name].update(map(int, records))
        setattr(
            inst, self.name,
            [r for r in getattr(inst, self.name) if r not in records])

    @domain_method
    def convert_domain(self, domain, tables, Model):
        from ..modelsql import convert_from
        pool = Pool()
        Rule = pool.get('ir.rule')
        Target = self.get_target()
        transaction = Transaction()
        table, _ = tables[None]
        name, operator, value = domain[:3]
        assert operator not in {'where', 'not where'} or '.' not in name

        if Target._history and transaction.context.get('_datetime'):
            target = Target.__table_history__()
            history_where = (
                Coalesce(target.write_date, target.create_date)
                <= transaction.context['_datetime'])
        else:
            target = Target.__table__()
            history_where = None
        origin_field = Target._fields[self.field]
        origin = getattr(Target, self.field).sql_column(target)
        origin_where = None
        if origin_field._type == 'reference':
            origin_where = origin.like(Model.__name__ + ',%')
            origin = origin_field.sql_id(origin, Target)

        subquery_threshold = config.getint('database', 'subquery_threshold')
        use_in = Target.estimated_count() < subquery_threshold
        if '.' not in name:
            if value is None:
                if use_in:
                    where = origin != value
                    if history_where:
                        where &= history_where
                    if origin_where:
                        where &= origin_where
                    if self.filter:
                        query = Target.search(
                            self.filter, order=[], query=True)
                        where &= origin.in_(query)
                    query = target.select(origin, where=where)
                    expression = ~table.id.in_(query)
                else:
                    where = origin == table.id
                    if history_where:
                        where &= history_where
                    if origin_where:
                        where &= origin_where
                    if self.filter:
                        target_tables = {
                            None: (target, None),
                            }
                        target_tables, clause = Target.search_domain(
                            self.filter, tables=target_tables)
                        where &= clause
                        query_table = convert_from(None, target_tables)
                        query = query_table.select(Literal(1), where=where)
                    else:
                        query = target.select(Literal(1), where=where)
                    expression = ~Exists(query)

                if operator == '!=':
                    expression = ~expression
                return expression
            else:
                if isinstance(value, str):
                    if not operator.endswith('where'):
                        warnings.warn(
                            f"Missing target field "
                            f"in operand of domain {domain}")
                    target_name = 'rec_name'
                else:
                    target_name = 'id'
        else:
            _, target_name = name.split('.', 1)
        if operator not in {'where', 'not where'}:
            target_domain = [(target_name,) + tuple(domain[1:])]
        else:
            target_domain = value
        if origin_field._type == 'reference':
            target_domain.append(
                (self.field, 'like', Model.__name__ + ',%'))
        rule_domain = Rule.domain_get(Target.__name__, mode='read')
        if rule_domain:
            target_domain = [target_domain, rule_domain]
        if self.filter:
            target_domain = [target_domain, self.filter]
        target_tables = {
            None: (target, None),
            }
        tables, expression = Target.search_domain(
            target_domain, tables=target_tables)
        query_table = convert_from(None, target_tables)
        if use_in:
            query = query_table.select(origin, where=expression)
            expression = table.id.in_(query)
        else:
            query = query_table.select(
                Literal(1), where=expression & (origin == table.id))
            expression = Exists(query)

        if operator == 'not where':
            expression = ~expression
        elif operator.startswith('!') or operator.startswith('not '):
            if use_in:
                expression |= ~table.id.in_(target.select(origin))
            else:
                expression |= ~Exists(target.select(
                        Literal(1), where=origin == table.id))
        return expression

    def definition(self, model, language):
        encoder = PYSONEncoder()
        definition = super().definition(model, language)
        if self.add_remove is not None:
            definition['add_remove'] = encoder.encode(self.add_remove)
        definition['datetime_field'] = self.datetime_field
        if self.filter:
            definition['domain'] = encoder.encode(
                ['AND', self.domain, self.filter])
        definition['relation'] = self.model_name
        if self.field:
            definition['relation_field'] = self.field
        definition['search_context'] = encoder.encode(self.search_context)
        definition['search_order'] = encoder.encode(self.search_order)
        if self.size is not None:
            definition['size'] = encoder.encode(self.size)
        definition['order'] = (
            getattr(self.get_target(), '_order', None)
            if self.order is None else self.order)
        return definition

    def sortable(self, model):
        return super().sortable(model) and hasattr(model, f'order_{self.name}')
