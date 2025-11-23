# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import ModelView, Workflow, fields
from trytond.modules.stock.exceptions import MoveValidationError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Location(metaclass=PoolMeta):
    __name__ = 'stock.location'

    rental_location = fields.Many2One(
        'stock.location', "Rental",
        states={
            'invisible': Eval('type') != 'warehouse',
            'required': Eval('type') == 'warehouse',
            },
        domain=[
            ('type', '=', 'rental'),
            ],
        help="The destination location for stock rent.")
    rental_picking_location = fields.Many2One(
        'stock.location', "Rental Picking",
        states={
            'invisible': Eval('type') != 'warehouse',
            },
        domain=[
            ('type', '=', 'storage'),
            ('parent', 'child_of', [Eval('id', -1)]),
            ],
        help="Where the rented assets are picked from.\n"
        "Leave empty to use the warehouse storage location.")
    rental_return_location = fields.Many2One(
        'stock.location', "Rental Return",
        states={
            'invisible': Eval('type') != 'warehouse',
            },
        domain=[
            ('type', '=', 'storage'),
            ('parent', 'child_of', [Eval('id', -1)]),
            ],
        help="Where the rented assets are returned to.\n"
        "Leave empty to use the warehouse storage location.")


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    sale_rental_lines_outgoing = fields.Many2Many(
        'sale.rental.line-outgoing-stock.move', 'move', 'line',
        "Outgoing Rental Lines", readonly=True,
        states={
            'invisible': ~Eval('sale_rental_lines_outgoing'),
            })
    sale_rental_lines_incoming = fields.Many2Many(
        'sale.rental.line-incoming-stock.move', 'move', 'line',
        "Incoming Rental Lines", readonly=True,
        states={
            'invisible': ~Eval('sale_rental_lines_incoming'),
            })

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() + ['sale.rental']

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//page[@id="sale_rental"]', 'states', {
                    'invisible': (
                        ~Eval('sale_rental_lines_outgoing')
                        & ~Eval('sale_rental_lines_incoming')),
                    }),
            ]

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, moves):
        pool = Pool()
        SaleRental = pool.get('sale.rental')
        super().do(moves)
        sale_rentals = {
            m.origin for m in moves if isinstance(m.origin, SaleRental)}
        if sale_rentals:
            sale_rentals = SaleRental.browse(list(sale_rentals))
            SaleRental.try_picked_up(sale_rentals)
            SaleRental.try_done(sale_rentals)

    @classmethod
    def validate_fields(cls, moves, field_names):
        super().validate_fields(moves, field_names)
        cls.check_rental_quantities(moves, field_names)

    @classmethod
    def check_rental_quantities(cls, moves, field_names):
        pool = Pool()
        Lang = pool.get('ir.lang')
        SaleRental = pool.get('sale.rental')
        SaleRentalLine = pool.get('sale.rental.line')
        UoM = pool.get('product.uom')

        if field_names and not (field_names & {
                    'state', 'origin', 'quantity', 'unit'}):
            return

        sale_rental_lines = set()
        for move in moves:
            if move.state != 'done' or not isinstance(move.origin, SaleRental):
                continue
            for lines in filter(None, [
                        move.sale_rental_lines_outgoing,
                        move.sale_rental_lines_incoming]):
                sale_rental_lines.update(lines)
                quantity = move.unit.round(sum(
                        UoM.compute_qty(
                            l.unit, l.quantity, move.unit, round=False)
                        for l in lines))
                if quantity != move.quantity:
                    lang = Lang.get()
                    raise MoveValidationError(gettext(
                            'sale_rental.msg_stock_move_rental_lines_quantity',
                            move=move.rec_name,
                            quantity=lang.format_number_symbol(
                                quantity, move.unit)))
        if sale_rental_lines:
            sale_rental_lines = SaleRentalLine.browse(list(sale_rental_lines))
            SaleRentalLine._validate(
                sale_rental_lines, ['actual_start', 'actual_end'])
