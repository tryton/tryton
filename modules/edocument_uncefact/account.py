# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta


class InvoiceEdocumentStart(metaclass=PoolMeta):
    __name__ = 'account.invoice.edocument.start'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.format.selection.append(
            ('edocument.uncefact.invoice', "UN/CEFACT"))

    @fields.depends('format')
    def get_templates(self):
        templates = super().get_templates()
        if self.format == 'edocument.uncefact.invoice':
            templates.append(('16B-CII', '16B-CII'))
        return templates
