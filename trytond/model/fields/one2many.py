# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import chain
from sql import Cast, Literal
from sql.functions import Substring, Position
from sql.conditionals import Coalesce

from .field import (Field, size_validate, instanciate_values, domain_validate,
    search_order_validate, context_validate)
from ...pool import Pool
from ...tools import grouped_slice
from ...transaction import Transaction


class One2Many(Field):
    '''
    Define one2many field (``list``).
    '''
    _type = 'one2many'

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
        if datetime_field:
            if depends:
                depends.append(datetime_field)
            else:
                depends = [datetime_field]
        super(One2Many, self).__init__(string=string, help=help,
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
        pool = Pool()
        Relation = pool.get(self.model_name)
        field = Relation._fields[self.field]
        res = {}
        for i in ids:
            res[i] = []

        targets = []
        for sub_ids in grouped_slice(ids):
            if field._type == 'reference':
                references = ['%s,%s' % (model.__name__, x) for x in sub_ids]
                clause = [(self.field, 'in', references)]
            else:
                clause = [(self.field, 'in', list(sub_ids))]
            if self.filter:
                clause.append(self.filter)
            targets.append(Relation.search(clause, order=self.order))
        targets = list(chain(*targets))

        for target in targets:
            origin_id = getattr(target, self.field).id
            res[origin_id].append(target.id)
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
                to_write.extend((targets, {
                            self.field: field_value(record_id),
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
        super(One2Many, self).__set__(inst, instanciate_values(Target, value))

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
            origin = Cast(Substring(origin,
                    Position(',', origin) + Literal(1)),
                Target.id.sql_type().base)

        if '.' not in name:
            if value is None:
                where = origin != value
                if history_where:
                    where &= history_where
                if origin_where:
                    where &= origin_where
                if self.filter:
                    query = Target.search(self.filter, order=[], query=True)
                    where &= origin.in_(query)
                query = target.select(origin, where=where)
                expression = ~table.id.in_(query)
                if operator == '!=':
                    return ~expression
                return expression
            else:
                if isinstance(value, str):
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
        query = query_table.select(origin, where=expression)
        expression = table.id.in_(query)

        if operator == 'not where':
            expression = ~expression
        elif operator.startswith('!') or operator.startswith('not '):
            expression |= ~table.id.in_(target.select(origin))
        return expression
