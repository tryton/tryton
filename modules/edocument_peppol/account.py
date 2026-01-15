# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from .exceptions import InvoicePeppolError, InvoicePeppolRequired


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    peppol = fields.One2Many(
        'edocument.peppol', 'invoice', "Peppol", readonly=True,
        states={
            'invisible': ~Eval('peppol', []),
            })

    @property
    def peppol_required(self):
        def is_be_vat(identifier):
            return (identifier
                and (identifier.type == 'be_vat'
                    or (identifier.type == 'eu_vat'
                        and identifier.code_compact.startswith('BE'))))
        if (self.invoice_date
                and self.invoice_date.year >= 2026
                and is_be_vat(self.tax_identifier)
                and is_be_vat(self.party_tax_identifier)):
            return True
        return False

    @classmethod
    def _post(cls, invoices):
        pool = Pool()
        Peppol = pool.get('edocument.peppol')
        Warning = pool.get('res.user.warning')
        posted_invoices = {
            i for i in invoices if i.state in {'draft', 'validated'}}
        super()._post(invoices)
        peppol = []
        for invoice in posted_invoices:
            if invoice.type != 'out':
                continue
            peppol_types = invoice.party.get_multivalue(
                'peppol_types', company=invoice.company.id)
            if peppol_types and 'bis-billing-3' in peppol_types:
                invoice.check_peppol()
                peppol.append(Peppol(
                        direction='out',
                        company=invoice.company,
                        type='bis-billing-3',
                        invoice=invoice))
            elif invoice.peppol_required:
                warning_key = Warning.format(
                    'invoice_peppol_required', [
                        invoice.party, invoice.company])
                if Warning.check(warning_key):
                    raise InvoicePeppolRequired(warning_key, gettext(
                            'edocument_peppol'
                            '.msg_invoice_party_peppol_required',
                            party=invoice.party.rec_name,
                            invoice=invoice.rec_name))
        if peppol:
            Peppol.save(peppol)
            Peppol.submit(peppol)

    def check_peppol(self):
        "Check if the invoice is valid for Peppol"
        for line in self.lines:
            if line.type == 'line' and line.unit_price < 0:  # BR-27
                raise InvoicePeppolError(gettext(
                        'edocument_peppol.'
                        'msg_invoice_line_unit_price_not_negative',
                        invoice=self.rec_name,
                        line=line.rec_name))
