# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta


class Incoming(metaclass=PoolMeta):
    __name__ = 'document.incoming'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.type.selection.append(
            ('ubl_invoice', "UBL Invoice/Credit Note"))

    def _process_ubl_invoice(self):
        pool = Pool()
        Invoice = pool.get('edocument.ubl.invoice')
        return Invoice.parse(self.data)
