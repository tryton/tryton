# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
from operator import itemgetter

from sql.operators import Concat

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.tools import grouped_slice, reduce_ids

__all__ = ['Move']


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'account.move'

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        StatementLine = pool.get('account.statement.line')
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()

        super(Move, cls).__register__(module_name)

        # Migration from 3.4:
        # account.statement.line origin changed to account.statement
        statement_line = StatementLine.__table__()
        cursor.execute(*sql_table.join(statement_line,
                condition=(
                    Concat(StatementLine.__name__ + ',', statement_line.id)
                    == sql_table.origin
                    )
                ).select(sql_table.id, statement_line.statement,
                order_by=(sql_table.id, statement_line.statement)))
        for statement_id, values in groupby(cursor.fetchall(), itemgetter(1)):
            ids = [x[0] for x in values]
            for sub_ids in grouped_slice(ids):
                red_sql = reduce_ids(sql_table.id, sub_ids)
                cursor.execute(*sql_table.update(
                        columns=[sql_table.origin],
                        values=['account.statement,%s' % statement_id],
                        where=red_sql))

    @classmethod
    def _get_origin(cls):
        return super(Move, cls)._get_origin() + ['account.statement']
