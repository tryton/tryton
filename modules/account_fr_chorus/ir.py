# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.method.selection.extend([
                ('account.invoice.chorus|send', "Send invoices to Chorus"),
                ('account.invoice.chorus|update',
                    "Update invoices from Chorus"),
                ])
        cls.methods_company_needed.update({
                'account.invoice.chorus|send',
                'account.invoice.chorus|update',
                })
