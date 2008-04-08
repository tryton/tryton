"Packing"
from trytond.osv import fields, OSV
import time

STATES = {
    'readonly': "state in ('cancel', 'done')",
}


class Packing(OSV):
    "Packing"
    _name = 'stock.packing'
    _order = 'id DESC'
    _description = __doc__
    _rec_name = 'code'

    effective_date =fields.DateTime('Effective Date', readonly=True)
    planned_date = fields.DateTime('Planned Date', readonly=True)
    moves = fields.One2Many('stock.move', 'packing', 'Move lines', states=STATES,)
    code = fields.Char("Code", size=None, select=1, readonly=True,)
    state = fields.Selection([('draft','Draft'),('done','Done'),('cancel','Cancel'),('waiting','Waiting')], 'State', readonly=True)

Packing()

class PackingIn(OSV):
    "Supplier Packing"
    _name = 'stock.packing.in'
    _order = 'id DESC'
    _description = __doc__
    _inherits = {'stock.packing':'packing'}

    packing = fields.Many2One('stock.packing', 'Generic Packing', required=True, ondelete='cascade',)

    def __init__(self):
        super(PackingIn, self).__init__()
        self._rpc_allowed += [
            'set_state_done',
            'set_state_waiting',
            'set_state_draft',
            'set_state_cancel',
            ]

    def default_creation_date(self, cursor, user, context=None):
        return time.strftime('%Y-%m-%d %H:%M:%S')

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def set_state_done(self, cursor, user, ids, context=None):
        move_obj = self.pool.get('stock.move')
        packings = self.browse(cursor, user, ids, context=context)
        moves = reduce(lambda l, p: l+ [m.id for m in p.moves], packings, [])
        move_obj.set_state_done(cursor, user, moves, context)
        self.write(cursor, user, ids, {'state':'done'}, context=context)

    def set_state_cancel(self, cursor, user, ids, context=None):
        move_obj = self.pool.get('stock.move')
        packings = self.browse(cursor, user, ids, context=context)
        moves = reduce(lambda l, p: l+ [m.id for m in p.moves], packings, [])
        move_obj.set_state_cancel(cursor, user, moves, context)
        self.write(cursor, user, ids, {'state':'cancel'}, context=context)

    def set_state_waiting(self, cursor, user, ids, context=None):
        move_obj = self.pool.get('stock.move')
        packings = self.browse(cursor, user, ids, context=context)
        moves = reduce(lambda l, p: l+ [m.id for m in p.moves], packings, [])
        move_obj.set_state_waiting(cursor, user, moves, context)
        self.write(cursor, user, ids, {'state':'waiting'}, context=context)

    def set_state_draft(self, cursor, user, ids, context=None):
        move_obj = self.pool.get('stock.move')
        packings = self.browse(cursor, user, ids, context=context)
        moves = reduce(lambda l, p: l+ [m.id for m in p.moves], packings, [])
        move_obj.set_state_draft(cursor, user, moves, context)
        self.write(cursor, user, ids, {'state':'draft'}, context=context)

    def create(self, cursor, user, values, context):
        values['code'] = self.pool.get('ir.sequence').get(cursor, user, 'stock.packing.in')
        super(PackingIn, self).create(cursor, user, values, context=context)

PackingIn()


class PackingOut(OSV):
    "Customer Packing"
    _name = 'stock.packing.out'
    _order = 'id DESC'
    _description = __doc__
    _inherits = {'stock.packing':'packing'}

    packing = fields.Many2One('stock.packing', 'Generic Packing', required=True, ondelete='cascade')

    def __init__(self):
        super(PackingOut, self).__init__()
        self._rpc_allowed += [
            'set_state_done',
            'set_state_waiting',
            'set_state_draft',
            'set_state_cancel',
            ]

    def default_creation_date(self, cursor, user, context=None):
        return time.strftime('%Y-%m-%d %H:%M:%S')

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def set_state_done(self, cursor, user, ids, context=None):
        move_obj = self.pool.get('stock.move')
        packings = self.browse(cursor, user, ids, context=context)
        moves = reduce(lambda l, p: l+ [m.id for m in p.moves], packings, [])
        move_obj.set_state_done(cursor, user, moves, context)
        self.write(cursor, user, ids, {'state':'done'}, context=context)

    def set_state_cancel(self, cursor, user, ids, context=None):
        move_obj = self.pool.get('stock.move')
        packings = self.browse(cursor, user, ids, context=context)
        moves = reduce(lambda l, p: l+ [m.id for m in p.moves], packings, [])
        move_obj.set_state_cancel(cursor, user, moves, context)
        self.write(cursor, user, ids, {'state':'cancel'}, context=context)

    def set_state_waiting(self, cursor, user, ids, context=None):
        move_obj = self.pool.get('stock.move')
        packings = self.browse(cursor, user, ids, context=context)
        moves = reduce(lambda l, p: l+ [m.id for m in p.moves], packings, [])
        move_obj.set_state_waiting(cursor, user, moves, context)
        self.write(cursor, user, ids, {'state':'waiting'}, context=context)

    def set_state_draft(self, cursor, user, ids, context=None):
        move_obj = self.pool.get('stock.move')
        packings = self.browse(cursor, user, ids, context=context)
        moves = reduce(lambda l, p: l+ [m.id for m in p.moves], packings, [])
        move_obj.set_state_draft(cursor, user, moves, context)
        self.write(cursor, user, ids, {'state':'draft'}, context=context)

    def create(self, cursor, user, values, context):
        values['code'] = self.pool.get('ir.sequence').get(cursor, user, 'stock.packing.out')
        super(PackingOut, self).create(cursor, user, values, context=context)

PackingOut()
