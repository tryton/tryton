#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Model, ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pyson import Eval
from trytond.pool import Pool
from trytond.transaction import Transaction


class Move(Model):
    _name = 'stock.move'

    def split(self, move, quantity, uom, count=None):
        """
        Split the move into moves of quantity.
        If count is not defined, the move will be split until the remainder is
        less than quantity.
        Return the split move ids
        """
        pool = Pool()
        uom_obj = pool.get('product.uom')

        moves = [move.id]
        remainder = uom_obj.compute_qty(move.uom, move.quantity, uom)
        if remainder <= quantity:
            return moves
        state = move.state
        self.write(move.id, {
                'state': 'draft',
                })
        self.write(move.id, {
                'quantity': quantity,
                'uom': uom.id,
                'state': state,
                })
        remainder -= quantity
        if count:
            count -= 1
        while (remainder > quantity
                and (count or count is None)):
            moves.append(self.copy(move.id, {
                        'quantity': quantity,
                        'uom': uom.id,
                        'state': state,
                        }))
            remainder -= quantity
            if count:
                count -= 1
        assert remainder >= 0
        if remainder:
            moves.append(self.copy(move.id, {
                        'quantity': remainder,
                        'uom': uom.id,
                        'state': state,
                        }))
        return moves

Move()


class SplitMoveStart(ModelView):
    'Split Move'
    _name = 'stock.move.split.start'
    _description = __doc__

    count = fields.Integer('Counts', help='The limit number of moves')
    quantity = fields.Float('Quantity', required=True,
        digits=(16, Eval('unit_digits', 2)),
        depends=['unit_digits'])
    uom = fields.Many2One('product.uom', 'Uom', required=True,
        domain=[
            ('category', '=', Eval('uom_category')),
            ],
        depends=['uom_category'])
    unit_digits = fields.Integer('Unit Digits', on_change_with=['uom'],
        readonly=True)
    uom_category = fields.Many2One('product.uom.category', 'Uom Category',
        readonly=True)

    def on_change_with_unit_digits(self, values):
        pool = Pool()
        uom_obj = pool.get('product.uom')
        if values.get('uom'):
            uom = uom_obj.browse(values['uom'])
            return uom.digits
        return 2

SplitMoveStart()


class SplitMove(Wizard):
    'Split Move'
    _name = 'stock.move.split'

    start = StateView('stock.move.split.start',
        'stock_split.split_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Split', 'split', 'tryton-ok', default=True),
            ])
    split = StateTransition()

    def default_start(self, session, fields):
        pool = Pool()
        move_obj = pool.get('stock.move')
        default = {}
        move = move_obj.browse(Transaction().context['active_id'])
        default['uom'] = move.uom.id
        default['unit_digits'] = move.unit_digits
        default['uom_category'] = move.uom.category.id
        return default

    def transition_split(self, session):
        pool = Pool()
        move_obj = pool.get('stock.move')
        move = move_obj.browse(Transaction().context['active_id'])
        move_obj.split(move, session.start.quantity, session.start.uom,
            session.start.count)
        return 'end'

SplitMove()
