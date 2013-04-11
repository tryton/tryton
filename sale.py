#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from itertools import groupby
from functools import partial
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.const import OPERATORS

__all__ = ['Sale', 'SaleLine']
__metaclass__ = PoolMeta


class Sale:
    __name__ = 'sale.sale'

    drop_shipments = fields.Function(fields.One2Many('stock.shipment.drop',
            None, 'Drop Shipments',
            states={
                'invisible': ~Eval('drop_shipments'),
                }),
        'get_drop_shipments')

    def get_drop_shipments(self, name):
        DropShipment = Pool().get('stock.shipment.drop')
        return list(set(m.shipment.id for l in self.lines for m in l.moves
                if isinstance(m.shipment, DropShipment)))

    def create_shipment(self, shipment_type):
        shipments = super(Sale, self).create_shipment(shipment_type)
        if shipment_type == 'out':
            self.create_drop_shipment()
        return shipments

    def _get_drop_move_sale_line(self):
        '''
        Return a line of moves
        '''
        moves = []
        for line in self.lines:
            moves += line.get_drop_moves()
        return moves

    def _group_drop_shipment_key(self, moves, move):
        '''
        The key to group moves by shipments
        '''
        planned_date = max(m.planned_date for m in moves)
        return (
            ('planned_date', planned_date),
            ('supplier', move.purchase.party),
            )

    def create_drop_shipment(self):
        '''
        Create a drop shipment for the sale
        '''
        pool = Pool()
        Shipment = pool.get('stock.shipment.drop')

        moves = self._get_drop_move_sale_line()
        if not moves:
            return []
        keyfunc = partial(self._group_drop_shipment_key, moves)
        moves = sorted(moves, key=keyfunc)

        shipments = []
        for key, grouped_moves in groupby(moves, key=keyfunc):
            values = {
                'customer': self.party.id,
                'delivery_address': self.shipment_address.id,
                'reference': self.reference,
                'company': self.company.id,
                }
            values.update(dict(key))
            with Transaction().set_user(0, set_context=True):
                shipment = Shipment(**values)
                shipment.moves = [m for m in grouped_moves]
                shipment.save()
                shipments.append(shipment)
        with Transaction().set_user(0, set_context=True):
            Shipment.wait(shipments)
        return shipments


class SaleLine:
    __name__ = 'sale.line'

    def get_move(self, shipment_type):
        result = super(SaleLine, self).get_move(shipment_type)
        if (shipment_type == 'out'
                and self.supply_on_sale):
            with Transaction().set_user(0, set_context=True):
                # TODO make it works in bunch
                line = self.__class__(self.id)
                if (line.purchase_request and line.purchase_request.customer
                        and self.purchase_request_state != 'cancel'):
                    return {}
        return result

    def get_purchase_request(self):
        request = super(SaleLine, self).get_purchase_request()
        if request and request.party:
            drop_shipment = False
            if self.product and self.product.type in ('goods', 'assets'):
                # FIXME this doesn't ensure to find always the right
                # product_supplier
                for product_supplier in self.product.product_suppliers:
                    if product_supplier.party == request.party:
                        drop_shipment = product_supplier.drop_shipment
                        break
            if drop_shipment:
                request.customer = self.sale.party
                request.delivery_address = self.sale.shipment_address
        return request

    def get_move_done(self, name):
        result = super(SaleLine, self).get_move_done(name)
        with Transaction().set_user(0, set_context=True):
            # TODO make it work in bunch
            line = self.__class__(self.id)
            if (line.purchase_request
                    and line.purchase_request.customer):
                if line.purchase_request.purchase_line:
                    return line.purchase_request.purchase_line.move_done
                else:
                    return False
        return result

    def get_move_exception(self, name):
        result = super(SaleLine, self).get_move_exception(name)
        with Transaction().set_user(0, set_context=True):
            # TODO make it work in bunch
            line = self.__class__(self.id)
            if line.purchase_request and line.purchase_request.customer:
                return False
        return result

    def get_drop_moves(self):
        if (self.type != 'line'
                or not self.product):
            return []
        moves = []
        with Transaction().set_user(0, set_context=True):
            # TODO make it work in bunch
            line = self.__class__(self.id)
            if line.purchase_request and line.purchase_request.customer:
                if line.purchase_request.purchase_line:
                    moves = [m
                        for m in line.purchase_request.purchase_line.moves
                        if m.state == 'draft' and not m.shipment]
        return moves

    @classmethod
    def read(cls, ids, fields_names=None):
        # Add moves from purchase_request as they can have only one origin
        PurchaseRequest = Pool().get('purchase.request')
        added = False
        if 'moves' in fields_names or []:
            if 'purchase_request' not in fields_names:
                fields_names = fields_names[:]
                fields_names.append('purchase_request')
                added = True
        values = super(SaleLine, cls).read(ids, fields_names=fields_names)
        if 'moves' in fields_names or []:
            with Transaction().set_user(0, set_context=True):
                purchase_requests = PurchaseRequest.browse(
                    list(set(v['purchase_request']
                            for v in values if v['purchase_request'])))
                id2purchase_requests = dict((p.id, p)
                    for p in purchase_requests)
            for value in values:
                if value['purchase_request']:
                    purchase_request = id2purchase_requests[
                        value['purchase_request']]
                    if (purchase_request.customer
                            and purchase_request.purchase_line):
                        move_ids = tuple(m.id
                            for m in purchase_request.purchase_line.moves)
                        if value['moves'] is None:
                            value['moves'] = move_ids
                        else:
                            value['moves'] += move_ids
                if added:
                    del value['purchase_request']
        return values

    @classmethod
    def search(cls, domain, *args, **kwargs):
        def process(domain):
            domain = domain[:]
            i = 0
            while i < len(domain):
                arg = domain[i]
                if (isinstance(arg, tuple)
                        or (isinstance(arg, list)
                            and len(arg) > 2
                            and arg[1] in OPERATORS)):
                    if arg[0] == 'moves':
                        domain[i] = ['OR',
                            arg,
                            [
                                ('purchase_request.purchase_line.moves',) +
                                tuple(arg[1:]),
                                ('purchase_request.customer', '!=', None),
                                ]
                            ]
                elif isinstance(arg, list):
                    domain[i] = process(domain)
                i += 1
            return domain
        return super(SaleLine, cls).search(process(domain), *args, **kwargs)
