# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.model import Model
from trytond.rpc import RPC


class Date(Model):
    'Date'
    __name__ = 'ir.date'

    @classmethod
    def __setup__(cls):
        super(Date, cls).__setup__()
        cls.__rpc__.update({
                'today': RPC(),
                })

    @staticmethod
    def today(timezone=None):
        '''
        Return the current date
        '''
        return datetime.datetime.now(timezone).date()
