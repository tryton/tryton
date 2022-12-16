# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from .exceptions import GiftCardValidationError


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    gift_card = fields.Boolean(
        "Gift Card",
        states={
            'invisible': ~Eval('type').in_(['service', 'goods']),
            })

    @fields.depends('gift_card')
    def on_change_gift_card(self):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        if self.gift_card:
            self.default_uom = ModelData.get_id('product', 'uom_unit')

    @classmethod
    def validate_fields(cls, templates, field_names):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        UoM = pool.get('product.uom')
        super().validate_fields(templates, field_names)
        if field_names & {'gift_card', 'default_uom'}:
            unit = UoM(ModelData.get_id('product', 'uom_unit'))
            for template in templates:
                if template.gift_card and template.default_uom != unit:
                    raise GiftCardValidationError(
                        gettext('sale_gift_card.msg_gift_card_invalid_uom',
                            template=template.rec_name,
                            unit=unit.rec_name))

    @property
    def account_expense_used(self):
        pool = Pool()
        Config = pool.get('account.configuration')
        if self.gift_card:
            transaction = Transaction()
            with transaction.reset_context(), \
                    transaction.set_context(self._context):
                config = Config(1)
            return config.gift_card_account_expense
        return super().account_expense_used

    @property
    def account_revenue_used(self):
        pool = Pool()
        Config = pool.get('account.configuration')
        if self.gift_card:
            transaction = Transaction()
            with transaction.reset_context(), \
                    transaction.set_context(self._context):
                config = Config(1)
            return config.gift_card_account_revenue
        return super().account_revenue_used


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
