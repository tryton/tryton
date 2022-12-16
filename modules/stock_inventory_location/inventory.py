# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.transaction import Transaction
from trytond.pool import Pool


class CreateInventoriesStart(ModelView):
    'Create Inventories'
    __name__ = 'stock.inventory.create.start'
    date = fields.Date('Date', required=True)
    company = fields.Many2One('company.company', 'Company', required=True,
            select=True)
    locations = fields.Many2Many('stock.location', None, None,
            'Locations', required=True, domain=[('type', '=', 'storage')])

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


class CreateInventories(Wizard):
    'Create Inventories'
    __name__ = 'stock.inventory.create'
    start = StateView('stock.inventory.create.start',
        'stock_inventory_location.inventory_create_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('stock.act_inventory_form')

    def do_create_(self, action):
        Inventory = Pool().get('stock.inventory')

        to_create = []
        for location in self.start.locations:
            to_create.append({
                        'location': location.id,
                        'date': self.start.date,
                        'company': self.start.company.id,
                        })
        if to_create:
            inventories = Inventory.create(to_create)

        Inventory.complete_lines(inventories)

        data = {'res_id': [i.id for i in inventories]}
        return action, data
