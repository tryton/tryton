# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ValueMixin, fields
from trytond.pool import PoolMeta


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    purchase_invoice_line_standalone = fields.MultiValue(
            fields.Boolean("Purchase Invoice Line Standalone"))
    purchase_invoice_lines_standalone = fields.One2Many(
        'party.party.purchase_invoice_line_standalone', 'party',
        "Purchase Invoice Lines Standalone")

    @classmethod
    def default_purchase_invoice_line_standalone(cls, **pattern):
        model = cls.multivalue_model('purchase_invoice_line_standalone')
        return model.default_purchase_invoice_line_standalone()


class PartyPurchaseInvoiceLineStandalone(ModelSQL, ValueMixin):
    __name__ = 'party.party.purchase_invoice_line_standalone'

    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE')
    purchase_invoice_line_standalone = fields.Boolean(
        "Invoice Line Standalone")

    @classmethod
    def default_purchase_invoice_line_standalone(cls):
        return False
