# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = ['PurchaseLine']
__metaclass__ = PoolMeta


class PurchaseLine:
    __name__ = 'purchase.line'

    @classmethod
    def __setup__(cls):
        super(PurchaseLine, cls).__setup__()
        cls._error_messages.update({
                'missing_account_asset': ('It misses '
                    'an "Account Asset" on product "%s"!'),
                })

    def get_invoice_line(self, invoice_type):
        invoice_lines = super(PurchaseLine, self).get_invoice_line(
            invoice_type)
        if (self.product
                and self.product.type == 'assets'
                and self.product.depreciable):
            for invoice_line in invoice_lines:
                if invoice_line.product == self.product:
                    invoice_line.account = self.product.account_asset_used
                    if not invoice_line.account:
                        self.raise_user_error('missing_account_asset',
                            error_args=(self.product.rec_name,))
        return invoice_lines
