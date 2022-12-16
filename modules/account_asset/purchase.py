# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pool import PoolMeta

from trytond.modules.account_product.exceptions import AccountError


class Line(metaclass=PoolMeta):
    __name__ = 'purchase.line'

    def get_invoice_line(self):
        invoice_lines = super().get_invoice_line()
        if (self.product
                and self.product.type == 'assets'
                and self.product.depreciable):
            for invoice_line in invoice_lines:
                if invoice_line.product == self.product:
                    invoice_line.account = self.product.account_asset_used
                    if not invoice_line.account:
                        raise AccountError(
                            gettext('account_asset'
                                '.msg_purchase_product_missing_account_asset',
                                purchase=self.purchase.rec_name,
                                product=self.product.rec_name))
        return invoice_lines
