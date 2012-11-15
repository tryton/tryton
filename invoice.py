# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta

__all__ = ['InvoiceLine']
__metaclass__ = PoolMeta


class InvoiceLine:
    __name__ = 'account.invoice.line'
    asset = fields.Many2One('account.asset', 'Asset', domain=[
            ('state', '=', 'running'),
            ('product', '=', Eval('product')),
            ],
        states={
            'invisible': (~Eval('is_assets_depreciable', False)
                | (Eval('_parent_invoice', {}).get('type',
                        Eval('invoice_type')) != 'out_invoice')),
            },
        on_change=['asset', 'unit'],
        depends=['product', 'is_assets_depreciable'])
    is_assets_depreciable = fields.Function(fields.Boolean(
            'Is Assets depreciable', on_change_with=['product']),
        'on_change_with_is_assets_depreciable')

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        cls._sql_constraints += [
            ('asset_uniq', 'UNIQUE(asset)',
                'Asset can be used only once on invoice line!'),
            ]

    def on_change_product(self):
        new_values = super(InvoiceLine, self).on_change_product()
        if (not self.product
                or self.invoice.type not in ('in_invoice', 'in_credit_note')):
            return new_values

        if self.product.type == 'assets' and self.product.depreciable:
            new_values['account'] = self.product.account_asset_used.id
            new_values['account.rec_name'] = \
                self.product.account_asset_used.rec_name
        return new_values

    def on_change_asset(self):
        Uom = Pool().get('product.uom')

        if self.asset:
            quantity = self.asset.quantity
            if self.unit:
                quantity = Uom.compute_qty(self.asset.unit, quantity,
                    self.unit)
                return {
                    'quantity': quantity,
                    }
            else:
                return {
                    'quantity': quantity,
                    'unit': self.unit.id,
                    'unit.rec_name': self.unit.rec_name,
                    }
        return {}

    def on_change_with_is_assets_depreciable(self, name=None):
        if self.product:
            return self.product.type == 'assets' and self.product.depreciable
        return False

    def get_move_line(self):
        Asset = Pool().get('account.asset')
        if self.asset:
            Asset.close([self.asset], account=self.account)
        return super(InvoiceLine, self).get_move_line()
