#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Model, fields
from trytond.pyson import Eval, Bool


class Configuration(Model):
    _name = 'account.configuration'

    stock_journal = fields.Property(fields.Many2One(
            'account.journal', 'Stock Journal',
            states={
                'required': Bool(Eval('context', {}).get('company')),
                }))

Configuration()
