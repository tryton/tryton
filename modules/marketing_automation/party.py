# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta
from .mixin import MarketingAutomationMixin


class Party(MarketingAutomationMixin, metaclass=PoolMeta):
    __name__ = 'party.party'
