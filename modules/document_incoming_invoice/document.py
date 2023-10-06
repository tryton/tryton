# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import fields
from trytond.modules.document_incoming.exceptions import (
    DocumentIncomingProcessError)
from trytond.pool import Pool, PoolMeta


class IncomingConfiguration(metaclass=PoolMeta):
    __name__ = 'document.incoming.configuration'

    default_supplier = fields.Many2One('party.party', "Default Supplier")


class Incoming(metaclass=PoolMeta):
    __name__ = 'document.incoming'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.type.selection.append(
            ('supplier_invoice', "Supplier Invoice"))

    @classmethod
    def _get_results(cls):
        return super()._get_results() | {'account.invoice'}

    def _process_supplier_invoice(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Configuration = pool.get('document.incoming.configuration')
        config = Configuration(1)
        invoice = Invoice(
            type='in',
            company=self.company or self.supplier_invoice_company)
        if invoice.company:
            invoice.currency = invoice.company.currency
        else:
            raise DocumentIncomingProcessError(gettext(
                    'document_incoming_invoice'
                    '.msg_supplier_invoice_company',
                    document=self.rec_name))
        # set party id after company for context
        party = self.supplier_invoice_party or config.default_supplier
        invoice.party = party.id if party else None
        invoice.set_journal()
        invoice.on_change_party()
        return invoice

    @property
    def supplier_invoice_company(self):
        pass

    @property
    def supplier_invoice_party(self):
        pass
