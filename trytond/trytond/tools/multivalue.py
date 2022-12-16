# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from sql import Table, Column, Literal, Union, Null
from sql.aggregate import Max

from trytond import backend
from trytond.pool import Pool
from trytond.transaction import Transaction


def migrate_property(
        model_name, field_names, ValueModel, value_names,
        parent=None, fields=None):
    "Migrate property from model_name.field_name to ValueModel.value_name"
    pool = Pool()
    Field = pool.get('ir.model.field')
    Model = pool.get('ir.model')
    if not backend.TableHandler.table_exist('ir_property'):
        return
    cursor = Transaction().connection.cursor()
    field = Field.__table__()
    model = Model.__table__()
    table = ValueModel.__table__()

    if fields is None:
        fields = []
    if isinstance(field_names, str):
        field_names = [field_names]
    if isinstance(value_names, str):
        value_names = [value_names]

    def split_value(value):
        return value.split(',')[1]
    cast_funcs = {
        'numeric': lambda v: Decimal(split_value(v)) if v else None,
        'integer': lambda v: int(split_value(v)) if v else None,
        'float': lambda v: float(split_value(v)) if v else None,
        'char': lambda v: split_value(v) if v else None,
        'selection': lambda v: split_value(v) if v else None,
        'many2one': lambda v: int(split_value(v)) if v else None,
        'reference': lambda v: v,
        }

    casts = []
    queries = []
    for field_name, value_name in zip(field_names, value_names):
        value_field = getattr(ValueModel, value_name)
        casts.append(cast_funcs[value_field._type])

        property_ = Table('ir_property')
        columns = [
            Literal(None).as_(f) if f != value_name
            else property_.value.as_(value_name)
            for f in value_names]
        if parent:
            columns.append(property_.res.as_(parent))
            where = property_.res.like(model_name + ',%')
        else:
            where = property_.res == Null
        columns.extend([Column(property_, f).as_(f) for f in fields])
        query = property_.join(field,
            condition=property_.field == field.id
            ).join(model,
                condition=field.model == model.id
                ).select(*columns,
                    where=where
                    & (field.name == field_name)
                    & (model.model == model_name))
        queries.append(query)

    union = Union(*queries)
    columns = [Max(Column(union, f)).as_(f) for f in value_names]
    if parent:
        columns.append(Column(union, parent).as_(parent))
        pcolumns = [Column(union, parent)]
    else:
        pcolumns = []
    vcolumns = [Column(union, f).as_(f) for f in fields]
    cursor.execute(
        *union.select(*(columns + vcolumns), group_by=pcolumns + vcolumns))

    columns = [Column(table, f) for f in value_names]
    if parent:
        pcolumns = [Column(table, parent)]
    else:
        pcolumns = []
    vcolumns = [Column(table, f) for f in fields]
    values = []
    length = len(value_names)
    for row in cursor:
        value = [c(v) for v, c in zip(row, casts)]
        if parent:
            value.append(
                int(row[length].split(',')[1])
                if row[length] else None)
            i = 1
        else:
            i = 0
        value.extend(row[length + i:])
        values.append(value)
    if (values and not (
                # No property defined
                len(values) == 1
                and all(x is None for x in values[0][:len(columns)]))):

        # Delete previous migrated values
        cursor.execute(*table.delete())

        cursor.execute(*table.insert(
                columns + pcolumns + vcolumns, values=values))
