# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
import json
from functools import partial

from sql import As, Column, Literal, Null, Union, With
from sql.aggregate import Min
from sql.conditionals import Coalesce

import trytond.config as config
from trytond.model import Index, ModelSQL, ModelView, convert_from, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction

dumps = partial(json.dumps, separators=(',', ':'), sort_keys=True)


class RelationType(ModelSQL, ModelView):
    __name__ = 'party.relation.type'

    name = fields.Char('Name', required=True, translate=True,
        help="The main identifier of the relation type.")
    reverse = fields.Many2One('party.relation.type', 'Reverse Relation',
        help="Create automatically the reverse relation.")
    usages = fields.MultiSelection([], "Usages")

    @classmethod
    def view_attributes(cls):
        attributes = super().view_attributes()
        if not cls.usages.selection:
            attributes.extend([
                    ('//separator[@name="usages"]',
                        'states', {'invisible': True}),
                    ('//field[@name="usages"]', 'invisible', 1),
                    ])
        return attributes


class Relation(ModelSQL):
    __name__ = 'party.relation'

    from_ = fields.Many2One(
        'party.party', "From", required=True, ondelete='CASCADE')
    to = fields.Many2One(
        'party.party', "To", required=True, ondelete='CASCADE')
    type = fields.Many2One(
        'party.relation.type', 'Type', required=True)
    start_date = fields.Date(
        "Start Date",
        domain=[
            If(Eval('start_date') & Eval('end_date'),
                ('start_date', '<=', Eval('end_date', None)),
                ()),
            ])
    end_date = fields.Date(
        "End Date",
        domain=[
            If(Eval('start_date') & Eval('end_date'),
                ('end_date', '>=', Eval('start_date', None)),
                ()),
            ])
    active = fields.Function(fields.Boolean("Active"), 'get_active')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        if not callable(cls.table_query):
            t = cls.__table__()
            cls._sql_indexes.update({
                    Index(t, (t.from_, Index.Range())),
                    Index(t, (t.to, Index.Range())),
                    })

    def get_active(self, name):
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        date = context.get('date') or Date.today()
        start_date = self.start_date or dt.date.min
        end_date = self.end_date or dt.date.max
        return start_date <= date <= end_date

    @classmethod
    def domain_active(cls, domain, tables):
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        date = context.get('date') or Date.today()
        table, _ = tables[None]
        _, operator, value = domain

        start_date = Coalesce(table.start_date, dt.date.min)
        end_date = Coalesce(table.end_date, dt.date.max)
        expression = (start_date <= date) & (end_date >= date)

        if operator in {'=', '!='}:
            if (operator == '=') != value:
                expression = ~expression
        elif operator in {'in', 'not in'}:
            if True in value and False not in value:
                pass
            elif False in value and True not in value:
                expression = ~expression
            else:
                expression = Literal(True)
        else:
            expression = Literal(True)
        return expression

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('from_',) + tuple(clause[1:]),
            ('to',) + tuple(clause[1:]),
            ('type',) + tuple(clause[1:]),
            ]


class RelationAll(Relation, ModelView):
    __name__ = 'party.relation.all'

    @classmethod
    def table_query(cls):
        pool = Pool()
        Relation = pool.get('party.relation')
        Type = pool.get('party.relation.type')

        relation = Relation.__table__()
        type = Type.__table__()

        tables = {
            None: (relation, None)
            }
        reverse_tables = {
            None: (relation, None),
            'type': {
                None: (type, (relation.type == type.id)
                    & (type.reverse != Null)),
                },
            }

        columns = []
        reverse_columns = []
        for name, field in Relation._fields.items():
            if hasattr(field, 'get'):
                continue
            column, reverse_column = cls._get_column(tables, reverse_tables,
                name)
            columns.append(column)
            reverse_columns.append(reverse_column)

        query = convert_from(None, tables, type_='INNER').select(*columns)
        reverse_query = convert_from(
            None, reverse_tables, type_='INNER').select(*reverse_columns)
        return Union(query, reverse_query, all_=True)

    @classmethod
    def _get_column(cls, tables, reverse_tables, name):
        table, _ = tables[None]
        reverse_table, _ = reverse_tables[None]
        if name == 'id':
            return As(table.id * 2, name), As(reverse_table.id * 2 + 1, name)
        elif name == 'from_':
            return table.from_, reverse_table.to.as_(name)
        elif name == 'to':
            return table.to, reverse_table.from_.as_(name)
        elif name == 'type':
            reverse_type, _ = reverse_tables[name][None]
            return table.type, reverse_type.reverse.as_(name)
        else:
            return Column(table, name), Column(reverse_table, name)

    @staticmethod
    def convert_instances(relations):
        "Converts party.relation.all instances to party.relation "
        pool = Pool()
        Relation = pool.get('party.relation')
        return Relation.browse([x.id // 2 for x in relations])

    @property
    def reverse_id(self):
        if self.id % 2:
            return self.id - 1
        else:
            return self.id + 1

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Relation = pool.get('party.relation')
        vlist = cls._before_create(vlist)
        relations = Relation.create(vlist)
        return cls.browse(cls._after_create([r.id * 2 for r in relations]))

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Relation = pool.get('party.relation')
        RelationType = pool.get('party.relation.type')

        ids, field_names, on_write, trigger_eligibles, *args = (
            cls._before_write(*args))

        relations = cls.browse(ids)
        # Clean local cache of reverse
        for relation in relations:
            relation._local_cache.pop(relation.reverse_id, None)
        # Clean cursor cache of reverse
        for cache in Transaction().cache.values():
            if cls.__name__ in cache:
                cache_cls = cache[cls.__name__]
                for relation in relations:
                    cache_cls.pop(relation.reverse_id, None)

        actions = iter(args)
        args = []
        for relations, values in zip(actions, actions):
            reverse_values = values.copy()
            if 'from_' in values and 'to' in values:
                reverse_values['from_'], reverse_values['to'] = \
                    reverse_values['to'], reverse_values['from_']
            elif 'from_' in values:
                reverse_values['to'] = reverse_values.pop('from_')
            elif 'to' in values:
                reverse_values['from_'] = reverse_values.pop('to')
            if values.get('type'):
                type_ = RelationType(values['type'])
                reverse_values['type'] = (type_.reverse.id
                    if type_.reverse else None)
            straight_relations = [r for r in relations if not r.id % 2]
            reverse_relations = [r for r in relations if r.id % 2]
            if straight_relations:
                args.extend(
                    (cls.convert_instances(straight_relations), values))
            if reverse_relations:
                args.extend(
                    (cls.convert_instances(reverse_relations), reverse_values))
        Relation.write(*args)

        cls._after_write(ids, field_names, on_write, trigger_eligibles)

    @classmethod
    def delete(cls, relations):
        pool = Pool()
        Relation = pool.get('party.relation')
        ids, on_delete = cls._before_delete(relations)

        # Clean cursor cache of reverse
        for cache in list(Transaction().cache.values()):
            if cls.__name__ in cache:
                cache_cls = cache[cls.__name__]
                for relation in relations:
                    cache_cls.pop(relation.reverse_id, None)

        Relation.delete(cls.convert_instances(relations))
        cls._after_delete(ids, on_delete)


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    relations = fields.One2Many('party.relation.all', 'from_', 'Relations')

    @classmethod
    def _distance_query(cls, usages=None, party=None, depth=None):
        pool = Pool()
        RelationAll = pool.get('party.relation.all')
        RelationType = pool.get('party.relation.type')

        transaction = Transaction()
        context = transaction.context
        database = transaction.database

        query = super()._distance_query(
            usages=usages, party=party, depth=depth)

        if usages is None:
            usages = context.get('relation_usages', [])
        if party is None:
            party = context.get('related_party')
        if depth is None:
            depth = context.get(
                'depth',
                config.getint('party_relationship', 'depth', default=7))

        if not party:
            return query

        all_relations = RelationAll.__table__()

        if usages:
            relation_type = RelationType.__table__()
            try:
                usages_clause = database.json_any_keys_exist(
                    relation_type.usages, list(usages))
            except NotImplementedError:
                usages_clause = Literal(False)
                for usage in usages:
                    usages_clause |= relation_type.usages.like(
                        '%' + dumps(usage) + '%')
            relations = (all_relations
                .join(relation_type,
                    condition=all_relations.type == relation_type.id)
                .select(
                    Column(all_relations, '*'),
                    where=usages_clause))
        else:
            relations = all_relations

        active_clause = RelationAll.domain_active(
            ('active', '=', True), {None: (relations, None)})

        distance = With('from_', 'to', 'distance', recursive=True)
        distance.query = relations.select(
            Column(relations, 'from_'),
            relations.to,
            Literal(1).as_('distance'),
            where=(Column(relations, 'from_') == party) & active_clause)
        distance.query |= (distance
            .join(relations,
                condition=distance.to == Column(relations, 'from_'))
            .select(
                distance.from_,
                relations.to,
                (distance.distance + Literal(1)).as_('distance'),
                where=(relations.to != party)
                & (distance.distance < depth)))
        distance.query.all_ = True

        relation_distance = distance.select(
            distance.to, Min(distance.distance).as_('distance'),
            group_by=[distance.to], with_=[distance])
        if query:
            relation_distance |= query
        return relation_distance
