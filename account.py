# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.operators import Concat
from sql.functions import Position

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['AccountTemplate']


class AccountTemplate:
    __metaclass__ = PoolMeta
    __name__ = 'account.account.template'

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        cursor = Transaction().connection.cursor()
        model_data = ModelData.__table__()

        # Migration from 3.4: translation of the account chart
        cursor.execute(*model_data.select(model_data.id,
                where=((model_data.fs_id == 'be')
                    & (model_data.module == 'account_be'))))
        if cursor.fetchone():
            cursor.execute(*model_data.update(
                    columns=[model_data.fs_id],
                    values=[Concat(model_data.fs_id, '_fr')],
                    where=((Position('_fr', model_data.fs_id) == 0)
                        & (model_data.module == 'account_be'))))

        super(AccountTemplate, cls).__register__(module_name)
