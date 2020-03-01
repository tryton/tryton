# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
from trytond.model import fields, Unique
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'
    asset = fields.Many2One('account.asset', 'Asset', domain=[
            ('state', '=', 'running'),
            ('product', '=', Eval('product')),
            ],
        states={
            'invisible': (~Eval('is_assets_depreciable', False)
                | (Eval('_parent_invoice', {}).get('type',
                        Eval('invoice_type')) != 'out')),
            },
        depends=['product', 'is_assets_depreciable'])
    is_assets_depreciable = fields.Function(fields.Boolean(
            'Is Assets depreciable'),
        'on_change_with_is_assets_depreciable')

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('asset_uniq', Unique(table, table.asset),
                'account_asset.msg_invoice_line_asset_unique'),
            ]

    @classmethod
    def _account_domain(cls, type_):
        domain = super()._account_domain(type_)
        if type_ == 'in':
            domain.append(('type.fixed_asset', '=', True))
        return domain

    @fields.depends('product', 'invoice', 'invoice_type',
        '_parent_invoice.invoice_date', '_parent_invoice.accounting_date')
    def on_change_product(self):
        super(InvoiceLine, self).on_change_product()
        if self.invoice and self.invoice.type:
            type_ = self.invoice.type
        else:
            type_ = self.invoice_type

        if (self.product and type_ == 'in'
                and self.product.type == 'assets'
                and self.product.depreciable):
            date = (self.invoice.accounting_date or self.invoice.invoice_date
                if self.invoice else None)
            with Transaction().set_context(date=date):
                self.account = self.product.account_asset_used

    @fields.depends('asset', 'unit')
    def on_change_asset(self):
        Uom = Pool().get('product.uom')

        if self.asset:
            quantity = self.asset.quantity
            if self.unit:
                quantity = Uom.compute_qty(self.asset.unit, quantity,
                    self.unit)
                self.quantity = quantity
            else:
                self.quantity = quantity
                self.unit = self.unit

    @fields.depends('product')
    def on_change_with_is_assets_depreciable(self, name=None):
        if self.product:
            return self.product.type == 'assets' and self.product.depreciable
        return False

    def get_move_lines(self):
        Asset = Pool().get('account.asset')
        if self.asset:
            Asset.close([self.asset], account=self.account)
        return super(InvoiceLine, self).get_move_lines()
