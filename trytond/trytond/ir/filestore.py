# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
from collections import defaultdict
from itertools import groupby
from operator import itemgetter

from sql import Column

from trytond import config
from trytond.filestore import filestore
from trytond.model import ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction


class Queue(
        fields.fmany2one(
            'model_ref', 'model', 'ir.model,name', "Model",
            required=True, ondelete='CASCADE'),
        fields.fmany2one(
            'field_ref', 'field,model', 'ir.model.field,name,model', "Field",
            required=True, ondelete='CASCADE',
            domain=[
                ('model_ref', '=', Eval('model_ref', -1)),
            ]),
        ModelSQL):
    __name__ = 'ir.filestore.queue'

    file_id = fields.Char("File ID", required=True)
    prefix = fields.Char("Prefix")
    model = fields.Char("Model", required=True)
    field = fields.Char("Field", required=True)

    @classmethod
    def remove(cls):
        pool = Pool()
        table = cls.__table__()
        transaction = Transaction()
        cursor = transaction.connection.cursor()

        now = datetime.datetime.now()
        retention_delay = datetime.timedelta(
            days=config.getint('attachment', 'retention_days', default=90))
        columns = [
            table.file_id, table.model, table.field, table.prefix]
        where = table.create_date < now - retention_delay
        if transaction.database.has_returning():
            cursor.execute(*table.delete(where=where, returning=columns))
            records = cursor.fetchall()
            records.sort(key=itemgetter(1, 2, 3))
        else:
            cursor.execute(*table.select(
                    *columns, where=where,
                    order_by=[table.model, table.field, table.prefix]))
            records = cursor.fetchall()
            cursor.execute(*table.delete(where=where))

        to_remove = defaultdict(list)
        for (model, fname, prefix), deleted in groupby(
                records, key=itemgetter(1, 2, 3)):
            Model = pool.get(model)
            model_tbl = Model.__table__()
            field = Model._fields[fname]
            if not field.file_id:
                continue
            file_id_col = Column(model_tbl, field.file_id)

            deleted_ids = {d[0] for d in deleted}
            active_ids = set()
            cursor.execute(*model_tbl.select(
                    file_id_col,
                    where=fields.SQL_OPERATORS['in'](
                        file_id_col, deleted_ids)))
            active_ids.update(r[0] for r in cursor)
            to_remove[prefix].extend(deleted_ids - active_ids)

        for store_prefix, to_delete in to_remove.items():
            filestore.delete_many(to_delete, prefix=store_prefix)
