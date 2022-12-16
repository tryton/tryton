# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import ModelView, Workflow, fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval, If

from .exceptions import MoveGiftCardValidationError


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    gift_cards = fields.One2Many(
        'sale.gift_card', 'origin', "Gift Cards",
        size=If(Eval('gift_cards_required'),
            Eval('internal_quantity', 0), 0),
        add_remove=[
            ('origin', '=', None),
            ],
        domain=[
            ('company', '=', Eval('company', -1)),
            ('product', '=', Eval('product', -1)),
            ],
        states={
            'invisible': ~Eval('gift_cards_required', []),
            'required': (
                Eval('gift_cards_required', False)
                & (Eval('state') == 'done')),
            'readonly': Eval('state').in_(['cancel', 'done']),
            },
        depends={'internal_quantity'})
    gift_cards_required = fields.Function(
        fields.Boolean("Gift Cards Required"),
        'on_change_with_gift_cards_required')

    @fields.depends('product', 'to_location')
    def on_change_with_gift_cards_required(self, name=None):
        return (
            self.product and self.product.gift_card
            and self.to_location and self.to_location.type == 'customer')

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, moves):
        for move in moves:
            if not move.gift_cards_required:
                continue
            if len(move.gift_cards) != move.internal_quantity:
                raise MoveGiftCardValidationError(
                    gettext('sale_gift_card.msg_gift_card_move_quantity',
                        move=move.rec_name,
                        quantity=move.internal_quantity))
        super().do(moves)
