#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.

from trytond.osv import OSV, fields

class Cache(OSV):
    "Cache"
    _name = 'ir.cache'
    _description = __doc__
    name = fields.Char('Name', required=True)
    timestamp = fields.DateTime('Timestamp')

Cache()
