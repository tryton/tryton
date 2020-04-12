# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from itertools import chain

from sql import Cast, Literal, Null
from sql.functions import Substring, Position
from sql.conditionals import Coalesce

from trytond.pyson import PYSONEncoder
from .field import (Field, size_validate, instanciate_values, domain_validate,
    search_order_validate, context_validate, instantiate_context)
from ...pool import Pool
from ...tools import grouped_slice
from ...transaction import Transaction


class Many2Many(Field):
    '''
    Define many2many field (``list``).
    '''
    _type = 'many2many'

    def __init__(self, relation_name, origin, target, string='', order=None,
            datetime_field=None, size=None, search_order=None,
            search_context=None, help='', required=False, readonly=False,
            domain=None, filter=None, states=None, on_change=None,
            on_change_with=None, depends=None, context=None, loading='lazy'):
        '''
        :param relation_name: The name of the relation model
            or the name of the target model for ModelView only.
        :param origin: The name of the field to store origin ids.
        :param target: The name of the field to store target ids.
        :param order:  a list of tuples that are constructed like this:
            ``('field name', 'DESC|ASC')``
            allowing to specify the order of result
        :param datetime_field: The name of the field that contains the datetime
            value to read the target records.
        :param search_order: The order to use when searching for a record
        :param search_context: The context to use when searching for a record
        :param filter: A domain to filter target records.
        '''
        if datetime_field:
            if depends:
                depends.append(datetime_field)
            else:
                depends = [datetime_field]
        super(Many2Many, self).__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        self.relation_name = relation_name
        self.origin = origin
        self.target = target
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

    @property
    def filter(self):
        return self.__filter

    @filter.setter
    def filter(self, value):
        if value is not None:
            domain_validate(value)
        self.__filter = value

    @property
    def add_remove(self):
        return self.domain

    def sql_type(self):
        return None

    def get(self, ids, model, name, values=None):
        '''
        Return target records ordered.
        '''
        if values is None:
            values = {}
        res = {}
        if not ids:
            return res
        for i in ids:
            res[i] = []

        if self.order is None:
            order = [(self.target, 'ASC')]
        else:
            order = self.order

        Relation = self.get_relation()
        origin_field = Relation._fields[self.origin]

        relations = []
        for sub_ids in grouped_slice(ids):
            if origin_field._type == 'reference':
                references = ['%s,%s' % (model.__name__, x) for x in sub_ids]
                clause = [(self.origin, 'in', references)]
            else:
                clause = [(self.origin, 'in', list(sub_ids))]
            clause += [(self.target, '!=', None)]
            if self.filter:
                clause.append((self.target, 'where', self.filter))
            relations.append(Relation.search(clause, order=order))
        relations = list(chain(*relations))

        for relation in relations:
            origin_id = getattr(relation, self.origin).id
            res[origin_id].append(getattr(relation, self.target).id)
        return dict((key, tuple(value)) for key, value in res.items())

    def set(self, Model, name, ids, values, *args):
        '''
        Set the values.

        values: A list of tuples:
            (``create``, ``[{<field name>: value}, ...]``),
            (``write``, [``<ids>``, ``{<field name>: value}``, ...]),
            (``delete``, ``<ids>``),
            (``remove``, ``<ids>``),
            (``add``, ``<ids>``),
            (``copy``, ``<ids>``, ``[{<field name>: value}, ...]``)
        '''
        Relation = self.get_relation()
        Target = self.get_target()
        origin_field = Relation._fields[self.origin]
        relation_to_create = []
        relation_to_delete = []
        target_to_write = []
        target_to_delete = []

        def search_clause(ids):
            if origin_field._type == 'reference':
                references = ['%s,%s' % (Model.__name__, x) for x in ids]
                return (self.origin, 'in', references)
            else:
                return (self.origin, 'in', ids)

        def field_value(record_id):
            if origin_field._type == 'reference':
                return '%s,%s' % (Model.__name__, record_id)
            else:
                return record_id

        def create(ids, vlist):
            for record_id in ids:
                for new in Target.create(vlist):
                    relation_to_create.append({
                            self.origin: field_value(record_id),
                            self.target: new.id,
                            })

        def write(_, *args):
            actions = iter(args)
            target_to_write.extend(sum(((Target.browse(ids), values)
                        for ids, values in zip(actions, actions)), ()))

        def delete(_, target_ids):
            target_to_delete.extend(Target.browse(target_ids))

        def add(ids, target_ids):
            target_ids = list(map(int, target_ids))
            if not target_ids:
                return
            existing_ids = set()
            for sub_ids in grouped_slice(target_ids):
                relations = Relation.search([
                        search_clause(ids),
                        (self.target, 'in', list(sub_ids)),
                        ])
                for relation in relations:
                    existing_ids.add((
                            getattr(relation, self.origin).id,
                            getattr(relation, self.target).id))
            for new_id in target_ids:
                for record_id in ids:
                    if (record_id, new_id) in existing_ids:
                        continue
                    relation_to_create.append({
                            self.origin: field_value(record_id),
                            self.target: new_id,
                            })

        def remove(ids, target_ids):
            target_ids = list(map(int, target_ids))
            if not target_ids:
                return
            for sub_ids in grouped_slice(target_ids):
                relation_to_delete.extend(Relation.search([
                            search_clause(ids),
                            (self.target, 'in', list(sub_ids)),
                            ]))

        def copy(ids, copy_ids, default=None):
            copy_ids = list(map(int, copy_ids))

            if default is None:
                default = {}
            default = default.copy()
            copies = Target.browse(copy_ids)
            for new in Target.copy(copies, default=default):
                for record_id in ids:
                    relation_to_create.append({
                            self.origin: field_value(record_id),
                            self.target: new.id,
                            })

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
        if relation_to_delete:
            Relation.delete(relation_to_delete)
        if target_to_delete:
            Target.delete(target_to_delete)
        if target_to_write:
            Target.write(*target_to_write)
        if relation_to_create:
            Relation.create(relation_to_create)

    def get_relation(self):
        "Return the relation model"
        return Pool().get(self.relation_name)

    def get_target(self):
        'Return the target model'
        Relation = self.get_relation()
        if not self.target:
            return Relation
        return Relation._fields[self.target].get_target()

    def __set__(self, inst, value):
        Target = self.get_target()
        ctx = instantiate_context(self, inst)
        with Transaction().set_context(ctx):
            records = instanciate_values(Target, value)
        super(Many2Many, self).__set__(inst, records)

    def delete(self, inst, records):
        records = set(records)
        if inst._deleted is None:
            inst._deleted = defaultdict(set)
        inst._deleted[self.name].update(map(int, records))
        setattr(
            inst, self.name,
            [r for r in getattr(inst, self.name) if r not in records])

    def convert_domain_tree(self, domain, tables):
        Target = self.get_target()
        table, _ = tables[None]
        name, operator, ids = domain
        ids = set(ids)  # Ensure it is a set for concatenation

        def get_child(ids):
            if not ids:
                return set()
            children = Target.search([
                    (name, 'in', ids),
                    (name, '!=', None),
                    ], order=[])
            child_ids = get_child(set(c.id for c in children))
            return ids | child_ids

        def get_parent(ids):
            if not ids:
                return set()
            parent_ids = set()
            for parent in Target.browse(ids):
                parent_ids.update(p.id for p in getattr(parent, name))
            return ids | get_parent(parent_ids)

        if operator.endswith('child_of'):
            ids = list(get_child(ids))
        else:
            ids = list(get_parent(ids))
        if not ids:
            expression = Literal(False)
        else:
            expression = table.id.in_(ids)
        if operator.startswith('not'):
            return ~expression
        return expression

    def convert_domain(self, domain, tables, Model):
        from ..modelsql import convert_from
        pool = Pool()
        Rule = pool.get('ir.rule')
        Target = self.get_target()
        Relation = self.get_relation()
        transaction = Transaction()
        table, _ = tables[None]
        name, operator, value = domain[:3]
        assert operator not in {'where', 'not where'} or '.' not in name

        if Relation._history and transaction.context.get('_datetime'):
            relation = Relation.__table_history__()
            history_where = (
                Coalesce(relation.write_date, relation.create_date)
                <= transaction.context['_datetime'])
        else:
            relation = Relation.__table__()
            history_where = None
        origin_field = Relation._fields[self.origin]
        origin = getattr(Relation, self.origin).sql_column(relation)
        origin_where = None
        if origin_field._type == 'reference':
            origin_where = origin.like(Model.__name__ + ',%')
            origin = Cast(Substring(origin,
                    Position(',', origin) + Literal(1)),
                Relation.id.sql_type().base)

        target = getattr(Relation, self.target).sql_column(relation)
        if '.' not in name:
            if operator.endswith('child_of') or operator.endswith('parent_of'):
                if Target != Model:
                    if operator.endswith('child_of'):
                        target_operator = 'child_of'
                    else:
                        target_operator = 'parent_of'
                    target_domain = [
                        (domain[3], target_operator, value),
                        ]
                    if self.filter:
                        target_domain.append(self.filter)
                    query = Target.search(target_domain, order=[], query=True)
                    where = (target.in_(query) & (origin != Null))
                    if history_where:
                        where &= history_where
                    if origin_where:
                        where &= origin_where
                    query = relation.select(origin, where=where)
                    expression = table.id.in_(query)
                    if operator.startswith('not'):
                        return ~expression
                    return expression
                if isinstance(value, str):
                    target_domain = [('rec_name', 'ilike', value)]
                    if self.filter:
                        target_domain.append(self.filter)
                    targets = Target.search(target_domain, order=[])
                    ids = [t.id for t in targets]
                else:
                    if not isinstance(value, (list, tuple)):
                        ids = [value]
                    else:
                        ids = value
                    if self.filter:
                        targets = Target.search(
                            [('id', 'in', ids), self.filter], order=[])
                        ids = [t.id for t in targets]
                if not ids:
                    expression = Literal(False)
                    if operator.startswith('not'):
                        return ~expression
                    return expression
                else:
                    return self.convert_domain_tree(
                        (name, operator, ids), tables)

            if value is None:
                where = origin != value
                if history_where:
                    where &= history_where
                if origin_where:
                    where &= origin_where
                if self.filter:
                    query = Target.search(self.filter, order=[], query=True)
                    where &= target.in_(query)
                query = relation.select(origin, where=where)
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
            relation_domain = [('%s.%s' % (self.target, target_name),)
                + tuple(domain[1:])]
            if origin_field._type == 'reference':
                relation_domain.append(
                    (self.origin, 'like', Model.__name__ + ',%'))
        else:
            relation_domain = [self.target, operator, value]
        rule_domain = Rule.domain_get(Relation.__name__, mode='read')
        if rule_domain:
            relation_domain = [relation_domain, rule_domain]
        if self.filter:
            relation_domain = [
                relation_domain,
                (self.target, 'where', self.filter),
                ]
        relation_tables = {
            None: (relation, None),
            }
        tables, expression = Relation.search_domain(
            relation_domain, tables=relation_tables)
        query_table = convert_from(None, relation_tables)
        query = query_table.select(origin, where=expression)
        return table.id.in_(query)

    def definition(self, model, language):
        encoder = PYSONEncoder()
        definition = super().definition(model, language)
        if self.add_remove is not None:
            definition['add_remove'] = encoder.encode(self.add_remove)
        definition['datetime_field'] = self.datetime_field
        if self.filter:
            definition['domain'] = encoder.encode(
                ['AND', self.domain, self.filter])
        definition['relation'] = self.get_target().__name__
        definition['search_context'] = encoder.encode(self.search_context)
        definition['search_order'] = encoder.encode(self.search_order)
        definition['sortable'] &= hasattr(model, 'order_' + self.name)
        definition['order'] = encoder.encode(
            getattr(model, '_order', None)
            if self.order is None else self.order)
        if self.size is not None:
            definition['size'] = encoder.encode(self.size)
        return definition
