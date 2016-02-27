# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['Move', 'SplitMoveStart', 'SplitMove']


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'stock.move'

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls._buttons.update({
                'split_wizard': {
                    'readonly': ~Eval('state').in_(['draft', 'assigned']),
                    },
                })

    @classmethod
    @ModelView.button_action('stock_split.wizard_split_move')
    def split_wizard(cls, moves):
        pass

    def split(self, quantity, uom, count=None):
        """
        Split the move into moves of quantity.
        If count is not defined, the move will be split until the remainder is
        less than quantity.
        Return the split moves
        """
        pool = Pool()
        Uom = pool.get('product.uom')

        moves = [self]
        remainder = Uom.compute_qty(self.uom, self.quantity, uom)
        if remainder <= quantity:
            return moves
        state = self.state
        self.write([self], {
                'state': 'draft',
                })
        self.write([self], {
                'quantity': quantity,
                'uom': uom.id,
                })
        remainder -= quantity
        if count:
            count -= 1
        while (remainder > quantity
                and (count or count is None)):
            moves.extend(self.copy([self], {
                        'quantity': quantity,
                        'uom': uom.id,
                        }))
            remainder -= quantity
            remainder = uom.round(remainder)
            if count:
                count -= 1
        assert remainder >= 0
        if remainder:
            moves.extend(self.copy([self], {
                        'quantity': remainder,
                        'uom': uom.id,
                        }))
        self.write(moves, {
                'state': state,
                })
        return moves


class SplitMoveStart(ModelView):
    'Split Move'
    __name__ = 'stock.move.split.start'
    count = fields.Integer('Counts', help='The limit number of moves')
    quantity = fields.Float('Quantity', required=True,
        digits=(16, Eval('unit_digits', 2)),
        depends=['unit_digits'])
    uom = fields.Many2One('product.uom', 'Uom', required=True,
        domain=[
            ('category', '=', Eval('uom_category')),
            ],
        depends=['uom_category'])
    unit_digits = fields.Integer('Unit Digits', readonly=True)
    uom_category = fields.Many2One('product.uom.category', 'Uom Category',
        readonly=True)

    @fields.depends('uom')
    def on_change_with_unit_digits(self):
        if self.uom:
            return self.uom.digits
        return 2


class SplitMove(Wizard):
    'Split Move'
    __name__ = 'stock.move.split'
    start = StateView('stock.move.split.start',
        'stock_split.split_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Split', 'split', 'tryton-ok', default=True),
            ])
    split = StateTransition()

    def default_start(self, fields):
        pool = Pool()
        Move = pool.get('stock.move')
        default = {}
        move = Move(Transaction().context['active_id'])
        default['uom'] = move.uom.id
        default['unit_digits'] = move.unit_digits
        default['uom_category'] = move.uom.category.id
        return default

    def transition_split(self):
        pool = Pool()
        Move = pool.get('stock.move')
        move = Move(Transaction().context['active_id'])
        move.split(self.start.quantity, self.start.uom, self.start.count)
        return 'end'
