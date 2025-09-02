# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
from secrets import token_hex

from sql.conditionals import NullIf
from sql.operators import Equal

from trytond.i18n import gettext
from trytond.model import Exclude, ModelView, fields
from trytond.modules.sale.exceptions import SaleValidationError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    web_shop = fields.Many2One('web.shop', "Web Shop", ondelete='RESTRICT')
    web_id = fields.Char(
        "Web ID", strip=False,
        states={
            'required': Bool(Eval('web_shop')),
            'readonly': ~Eval('web_id'),
            })
    web_status_url = fields.Function(
        fields.Char(
            "Web Status URL",
            states={
                'invisible': ~Eval('web_status_url'),
                },
            help="The URL where the customer can check "
            "the order's current status."),
        'get_web_status_url')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('web_shop_id_unique',
                Exclude(t,
                    (t.web_shop, Equal),
                    (NullIf(t.web_id, ''), Equal)),
                'web_shop.msg_sale_web_shop_id_unique')
            ]
        cls._buttons.update({
                'web_shop_update': {
                    'invisible': ~Eval('web_shop', None),
                    'depends': ['web_shop'],
                    },
                })

    @classmethod
    def __register__(cls, module):
        table_h = cls.__table_handler__(module)
        super().__register__(module)

        # Migration from 7.4: replace web_id constraint by web_shop_id_unique
        table_h.drop_constraint('web_id')

    @fields.depends('web_shop', 'web_id')
    def on_change_web_shop(self, nbytes=None):
        if self.web_shop and not self.web_id:
            self.web_id = token_hex(nbytes)

    def get_web_status_url(self, name):
        pass

    @classmethod
    def copy(cls, sales, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('web_shop', None)
        default.setdefault('web_id', None)
        return super().copy(sales, default=default)

    @classmethod
    def validate_fields(cls, sales, field_names):
        pool = Pool()
        WebShop = pool.get('web.shop')
        super().validate_fields(sales, field_names)

        if field_names & {'state', 'party'}:
            web_shops = WebShop.search([])
            guests = {s.guest_party for s in web_shops}
            for sale in sales:
                if (sale.state not in {'draft', 'cancelled'}
                        and sale.party in guests):
                    raise SaleValidationError(
                        gettext('web_shop.msg_sale_invalid_party',
                            sale=sale.rec_name,
                            party=sale.party.rec_name))

    @classmethod
    @ModelView.button
    def web_shop_update(cls, sales):
        for web_shop, s_sales in groupby(sales, lambda s: s.web_shop):
            web_shop.update_sales(list(s_sales))
