# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.config import config
from trytond.model import fields
from trytond.pool import PoolMeta

rate_decimal = config.getint('currency', 'rate_decimal', default=6)


class Configuration(metaclass=PoolMeta):
    __name__ = 'ir.configuration'
    currency_rate_decimal = fields.Integer("Currency Rate Decimal")

    @classmethod
    def default_currency_rate_decimal(cls):
        return rate_decimal

    def check(self):
        super().check()
        if self.currency_rate_decimal != rate_decimal:
            raise ValueError(
                "The rate_decimal %s in the [currency] configuration section "
                "is different from the value %s in 'ir.configuration'." % (
                    rate_decimal, self.currency_rate_decimal))


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.method.selection.append(
            ('currency.cron|update', "Update Currency Rates"))
