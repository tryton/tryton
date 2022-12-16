# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
from sql import Union, Column, Literal, Cast

from trytond.model import fields
from trytond.pool import Pool


class UnionMixin:
    'Mixin to combine models'
    __slots__ = ()

    @staticmethod
    def union_models():
        return []

    @classmethod
    def union_shard(cls, column, model):
        models = cls.union_models()
        length = len(models)
        i = models.index(model)
        return ((column * length) + i)

    @classmethod
    def union_unshard(cls, record_id):
        pool = Pool()
        models = cls.union_models()
        length = len(models)
        record_id, i = divmod(record_id, length)
        Model = pool.get(models[i])
        return Model(record_id)

    @classmethod
    def union_column(cls, name, field, table, Model):
        column = Literal(None)
        union_field = Model._fields.get(name)
        if union_field:
            column = Column(table, union_field.name)
            if (isinstance(field, fields.Many2One)
                    and field.model_name == cls.__name__):
                target_model = union_field.model_name
                if target_model in cls.union_models():
                    column = cls.union_shard(column, target_model)
                else:
                    column = Literal(None)
        return column

    @classmethod
    def union_columns(cls, model):
        pool = Pool()
        Model = pool.get(model)
        table = Model.__table__()
        columns = [cls.union_shard(table.id, model).as_('id')]
        for name in sorted(cls._fields.keys()):
            field = cls._fields[name]
            if name == 'id' or hasattr(field, 'set'):
                continue
            column = cls.union_column(name, field, table, Model)
            columns.append(field.sql_cast(column).as_(name))
        return table, columns

    @classmethod
    def table_query(cls):
        queries = []
        for model in cls.union_models():
            table, columns = cls.union_columns(model)
            queries.append(table.select(*columns))
        return Union(*queries)
