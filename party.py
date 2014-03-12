#This file is part of Tryton. The COPYRIGHT file at the top level of this
#repository contains the full copyright notices and license terms.
from sql import Union, As, Column

from trytond.pool import Pool, PoolMeta
from trytond.model import ModelSQL, ModelView, fields

__all__ = ['RelationType', 'PartyRelation', 'PartyRelationAll', 'Party']
__metaclass__ = PoolMeta


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
                    (type.reverse != None)),
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

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Relation = pool.get('party.relation')
        return Relation.create(vlist)

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Relation = pool.get('party.relation')
        actions = iter(args)
        args = []
        for relations, values in zip(actions, actions):
            args.extend((cls.convert_instances(relations), values))
        return Relation.write(*args)

    @classmethod
    def delete(cls, relations):
        pool = Pool()
        Relation = pool.get('party.relation')
        return Relation.delete(cls.convert_instances(relations))


class Party:
    __name__ = 'party.party'

    relations = fields.One2Many('party.relation.all', 'from_', 'Relations')
