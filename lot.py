"Wharehouse"
from trytond.osv import fields, OSV
import time

class Lot(OSV):
    "Stock Lot"
    _name = 'stock.lot'
    _order = 'id DESC'
    _description = __doc__
    _rec_name = 'code'

    code = fields.Char("Code", size=64, select=1, readonly=1)
    creation_date = fields.DateTime("Created at")
    moves = fields.One2Many("stock.move", "lot", "Stock Moves")


    def default_creation_date(self, cursor, user, context):
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def create(self, cursor, user, values, context):
        values['code'] = self.pool.get('ir.sequence').get(cursor, user, 'stock.lot')
        return super(Lot,self).create(cursor, user, values, context)

Lot()
