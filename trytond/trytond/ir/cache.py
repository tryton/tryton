# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields


class Cache(ModelSQL):
    "Cache"
    __name__ = 'ir.cache'
    name = fields.Char('Name', required=True)
    timestamp = fields.DateTime('Timestamp')
