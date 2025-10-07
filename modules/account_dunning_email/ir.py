# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Table
from sql.operators import Concat

from trytond import backend, config
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction


class Email(metaclass=PoolMeta):
    __name__ = 'ir.email'

    dunning_level = fields.Many2One(
        'account.dunning.level', "Level", readonly=True,
        states={
            'invisible': ~Eval('dunning_level'),
            })

    @classmethod
    def __register__(cls, module):
        table = cls.__table__()
        log_name = 'account.dunning.email.log'
        log_table_name = config.get(
            'table', log_name, default=log_name.replace('.', '_'))
        log = Table(log_table_name)

        cursor = Transaction().connection.cursor()

        super().__register__(module)

        # Migration from 6.8: merge dunning email log with email
        if backend.TableHandler.table_exist(log_table_name):
            query = table.insert(
                [table.create_uid, table.create_date,
                    table.write_uid, table.write_date,
                    table.recipients, table.recipients_secondary,
                    table.recipients_hidden,
                    table.resource,
                    table.dunning_level],
                log.select(
                    log.create_uid, log.create_date,
                    log.write_uid, log.write_date,
                    log.recipients, log.recipients_secondary,
                    log.recipients_hidden,
                    Concat('account.dunning,', log.dunning),
                    log.level))
            cursor.execute(*query)
            backend.TableHandler.drop_table(log_name, log_table_name)

    def get_user(self, name):
        user = super().get_user(name)
        if self.dunning_level:
            user = None
        return user
