# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import re

from trytond.pool import PoolMeta


class Identifier(metaclass=PoolMeta):
    __name__ = 'party.identifier'

    @property
    def unece_code(self):
        if self.type and re.match(r'[a-z]{2}_vat', self.type):
            return 'VAT'
