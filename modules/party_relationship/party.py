# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Union, As, Column, Null

from trytond.pool import Pool, PoolMeta
from trytond.model import ModelSQL, ModelView, fields
from trytond.transaction import Transaction

__all__ = ['RelationType', 'PartyRelation', 'PartyRelationAll', 'Party']


class RelationType(ModelSQL, ModelView):
    'Relation Type'
    __name__ = 'party.relation.type'

    name = fields.Char('Name', required=True, translate=True)
    reverse = fields.Many2One('party.relation.type', 'Reverse Relation')


class PartyRelation(ModelSQL):
    'Party Relation'
    __name__ = 'party.relation'

    from_ = fields.Many2One('party.party', 'From', required=True, select=True,
        ondelete='CASCADE')
    to = fields.Many2One('party.party', 'To', required=True, select=True,
        ondelete='CASCADE')
    type = fields.Many2One('party.relation.type', 'Type', required=True,
        select=True)


class PartyRelationAll(PartyRelation, ModelView):
    'Party Relation'
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
                None: (type, (relation.type == type.id) &
                    (type.reverse != Null)),
                },
            }

        columns = []
        reverse_columns = []
        for name, field in Relation._fields.iteritems():
            if hasattr(field, 'get'):
                continue
            column, reverse_column = cls._get_column(tables, reverse_tables,
                name)
            columns.append(column)
            reverse_columns.append(reverse_column)

        def convert_from(table, tables):
            right, condition = tables[None]
            if table:
                table = table.join(right, condition=condition)
            else:
                table = right
            for k, sub_tables in tables.iteritems():
                if k is None:
                    continue
                table = convert_from(table, sub_tables)
            return table

        query = convert_from(None, tables).select(*columns)
        reverse_query = convert_from(None, reverse_tables).select(
            *reverse_columns)
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
        relations = Relation.create(vlist)
        return cls.browse([r.id * 2 for r in relations])

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Relation = pool.get('party.relation')
        RelationType = pool.get('party.relation.type')

        all_records = sum(args[0:None:2], [])

        # Increase transaction counter
        Transaction().counter += 1

        # Clean local cache
        for record in all_records:
            for record_id in (record.id, record.reverse_id):
                local_cache = record._local_cache.get(record_id)
                if local_cache:
                    local_cache.clear()

        # Clean cursor cache
        for cache in Transaction().cache.itervalues():
            if cls.__name__ in cache:
                for record in all_records:
                    for record_id in (record.id, record.reverse_id):
                        if record_id in cache[cls.__name__]:
                            cache[cls.__name__][record_id].clear()

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

    @classmethod
    def delete(cls, relations):
        pool = Pool()
        Relation = pool.get('party.relation')

        # Increase transaction counter
        Transaction().counter += 1

        # Clean cursor cache
        for cache in Transaction().cache.values():
            for cache in (cache, cache.get('_language_cache', {}).values()):
                if cls.__name__ in cache:
                    for record in relations:
                        for record_id in (record.id, record.reverse_id):
                            if record_id in cache[cls.__name__]:
                                del cache[cls.__name__][record_id]

        Relation.delete(cls.convert_instances(relations))


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    relations = fields.One2Many('party.relation.all', 'from_', 'Relations')
