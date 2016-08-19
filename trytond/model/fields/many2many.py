#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from itertools import chain
from sql import Cast, Literal
from sql.functions import Substring, Position

from .field import Field, size_validate
from ...pool import Pool
from ...tools import grouped_slice


class Many2Many(Field):
    '''
    Define many2many field (``list``).
    '''
    _type = 'many2many'

    def __init__(self, relation_name, origin, target, string='', order=None,
            datetime_field=None, size=None, help='', required=False,
            readonly=False, domain=None, states=None, on_change=None,
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

    __init__.__doc__ += Field.__init__.__doc__

    def _get_size(self):
        return self.__size

    def _set_size(self, value):
        size_validate(value)
        self.__size = value

    size = property(_get_size, _set_size)

    @property
    def add_remove(self):
        return self.domain

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

        Relation = Pool().get(self.relation_name)
        origin_field = Relation._fields[self.origin]

        relations = []
        for sub_ids in grouped_slice(ids):
            if origin_field._type == 'reference':
                references = ['%s,%s' % (model.__name__, x) for x in sub_ids]
                clause = [(self.origin, 'in', references)]
            else:
                clause = [(self.origin, 'in', list(sub_ids))]
            clause += [(self.target + '.id', '!=', None)]
            relations.append(Relation.search(clause, order=order))
        relations = list(chain(*relations))

        for relation in relations:
            origin_id = getattr(relation, self.origin).id
            res[origin_id].append(getattr(relation, self.target).id)
        return dict((key, tuple(value)) for key, value in res.iteritems())

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
        pool = Pool()
        Relation = pool.get(self.relation_name)
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
            target_ids = map(int, target_ids)
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
            target_ids = map(int, target_ids)
            if not target_ids:
                return
            for sub_ids in grouped_slice(target_ids):
                relation_to_delete.extend(Relation.search([
                            search_clause(ids),
                            (self.target, 'in', list(sub_ids)),
                            ]))

        def copy(ids, copy_ids, default=None):
            copy_ids = map(int, copy_ids)

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
        if relation_to_create:
            Relation.create(relation_to_create)
        if relation_to_delete:
            Relation.delete(relation_to_delete)
        if target_to_write:
            Target.write(*target_to_write)
        if target_to_delete:
            Target.delete(target_to_delete)

    def get_target(self):
        'Return the target model'
        Relation = Pool().get(self.relation_name)
        if not self.target:
            return Relation
        return Relation._fields[self.target].get_target()

    def __set__(self, inst, value):
        Target = self.get_target()

        def instance(data):
            if isinstance(data, Target):
                return data
            elif isinstance(data, dict):
                return Target(**data)
            else:
                return Target(data)
        value = [instance(x) for x in (value or [])]
        super(Many2Many, self).__set__(inst, value)

    def convert_domain_child(self, domain, tables):
        Target = self.get_target()
        table, _ = tables[None]
        name, operator, ids = domain
        ids = list(ids)  # Ensure it is a list for concatenation

        def get_child(ids):
            if not ids:
                return []
            children = Target.search([
                    (name, 'in', ids),
                    (name, '!=', None),
                    ], order=[])
            child_ids = get_child([c.id for c in children])
            return ids + child_ids
        expression = table.id.in_(ids + get_child(ids))
        if operator == 'not child_of':
            return ~expression
        return expression

    def convert_domain(self, domain, tables, Model):
        pool = Pool()
        Target = self.get_target()
        Relation = pool.get(self.relation_name)
        relation = Relation.__table__()
        table, _ = tables[None]
        name, operator, value = domain[:3]

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
            if operator in ('child_of', 'not child_of'):
                if Target != Model:
                    query = Target.search([(domain[3], 'child_of', value)],
                        order=[], query=True)
                    where = (target.in_(query) & (origin != None))
                    if origin_where:
                        where &= origin_where
                    query = relation.select(origin, where=where)
                    expression = table.id.in_(query)
                    if operator == 'not child_of':
                        return ~expression
                    return expression
                if isinstance(value, basestring):
                    targets = Target.search([('rec_name', 'ilike', value)],
                        order=[])
                    ids = [t.id for t in targets]
                elif not isinstance(value, (list, tuple)):
                    ids = [value]
                else:
                    ids = value
                if not ids:
                    expression = table.id.in_([None])
                    if operator == 'not child_of':
                        return ~expression
                    return expression
                else:
                    return self.convert_domain_child(
                        (name, operator, ids), tables)

            if value is None:
                where = origin != value
                if origin_where:
                    where &= origin_where
                query = relation.select(origin, where=where)
                expression = ~table.id.in_(query)
                if operator == '!=':
                    return ~expression
                return expression
            else:
                if isinstance(value, basestring):
                    target_name = 'rec_name'
                else:
                    target_name = 'id'
        else:
            _, target_name = name.split('.', 1)
        target_domain = [(target_name,) + tuple(domain[1:])]
        query = Target.search(target_domain, order=[], query=True)
        where = target.in_(query)
        if origin_where:
            where &= origin_where
        query = relation.select(origin, where=where)
        return table.id.in_(query)
