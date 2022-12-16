#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from itertools import chain
from sql import Cast, Literal, Column
from sql.functions import Substring, Position

from .field import Field, size_validate
from ...transaction import Transaction
from ...pool import Pool


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
        for i in range(0, len(ids), Transaction().cursor.IN_MAX):
            sub_ids = ids[i:i + Transaction().cursor.IN_MAX]
            if origin_field._type == 'reference':
                references = ['%s,%s' % (model.__name__, x) for x in sub_ids]
                clause = [(self.origin, 'in', references)]
            else:
                clause = [(self.origin, 'in', sub_ids)]
            clause += [(self.target + '.id', '!=', None)]
            relations.append(Relation.search(clause, order=order))
        relations = list(chain(*relations))

        for relation in relations:
            origin_id = getattr(relation, self.origin).id
            res[origin_id].append(getattr(relation, self.target).id)
        return dict((key, tuple(value)) for key, value in res.iteritems())

    def set(self, ids, model, name, values):
        '''
        Set the values.

        values: A list of tuples:
            (``create``, ``[{<field name>: value}, ...]``),
            (``write``, ``<ids>``, ``{<field name>: value}``),
            (``delete``, ``<ids>``),
            (``delete_all``),
            (``unlink``, ``<ids>``),
            (``add``, ``<ids>``),
            (``unlink_all``),
            (``set``, ``<ids>``)
        '''
        pool = Pool()
        if not values:
            return
        Relation = pool.get(self.relation_name)
        Target = self.get_target()
        origin_field = Relation._fields[self.origin]

        def search_clause(ids):
            if origin_field._type == 'reference':
                references = ['%s,%s' % (model.__name__, x) for x in ids]
                return (self.origin, 'in', references)
            else:
                return (self.origin, 'in', ids)

        def field_value(record_id):
            if origin_field._type == 'reference':
                return '%s,%s' % (model.__name__, record_id)
            else:
                return record_id

        for act in values:
            if act[0] == 'create':
                to_create = []
                for record_id in ids:
                    for new in Target.create(act[1]):
                        to_create.append({
                                self.origin: field_value(record_id),
                                self.target: new.id,
                                })
                if to_create:
                    Relation.create(to_create)
            elif act[0] == 'write':
                Target.write(Target.browse(act[1]), act[2])
            elif act[0] == 'delete':
                Target.delete(Target.browse(act[1]))
            elif act[0] == 'delete_all':
                relations = Relation.search([
                        search_clause(ids),
                        ])
                Target.delete([getattr(r, self.target) for r in relations
                        if getattr(r, self.target)])
            elif act[0] == 'unlink':
                if isinstance(act[1], (int, long)):
                    target_ids = [act[1]]
                else:
                    target_ids = list(act[1])
                if not target_ids:
                    continue
                relations = []
                for i in range(0, len(target_ids),
                        Transaction().cursor.IN_MAX):
                    sub_ids = target_ids[i:i + Transaction().cursor.IN_MAX]
                    relations += Relation.search([
                            search_clause(ids),
                            (self.target, 'in', sub_ids),
                            ])
                Relation.delete(relations)
            elif act[0] == 'add':
                target_ids = list(act[1])
                if not target_ids:
                    continue
                existing_ids = []
                for i in range(0, len(target_ids),
                        Transaction().cursor.IN_MAX):
                    sub_ids = target_ids[i:i + Transaction().cursor.IN_MAX]
                    relations = Relation.search([
                            search_clause(ids),
                            (self.target, 'in', sub_ids),
                            ])
                    for relation in relations:
                        existing_ids.append(getattr(relation, self.target).id)
                to_create = []
                for new_id in (x for x in target_ids if x not in existing_ids):
                    for record_id in ids:
                        to_create.append({
                                self.origin: field_value(record_id),
                                self.target: new_id,
                                })
                if to_create:
                    Relation.create(to_create)
            elif act[0] == 'unlink_all':
                targets = Relation.search([
                        search_clause(ids),
                        (self.target + '.id', '!=', None),
                        ])
                Relation.delete(targets)
            elif act[0] == 'set':
                if not act[1]:
                    target_ids = []
                else:
                    target_ids = list(act[1])
                targets2 = Relation.search([
                        search_clause(ids),
                        (self.target + '.id', '!=', None),
                        ])
                Relation.delete(targets2)

                to_create = []
                for new_id in target_ids:
                    for record_id in ids:
                        to_create.append({
                                self.origin: field_value(record_id),
                                self.target: new_id,
                                })
                if to_create:
                    Relation.create(to_create)
            else:
                raise Exception('Bad arguments')

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
        origin = Column(relation, self.origin)
        origin_where = None
        if origin_field._type == 'reference':
            origin_where = origin.like(Model.__name__ + ',%')
            origin = Cast(Substring(origin,
                    Position(',', origin) + Literal(1)),
                Relation.id.sql_type().base)

        if '.' not in name:
            if operator in ('child_of', 'not child_of'):
                if Target != Model:
                    query = Target.search([(domain[3], 'child_of', value)],
                        order=[], query=True)
                    where = (Column(relation, self.target).in_(query)
                        & (Column(relation, self.origin) != None))
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
        where = Column(relation, self.target).in_(query)
        if origin_where:
            where &= origin_where
        query = relation.select(origin, where=where)
        return table.id.in_(query)
