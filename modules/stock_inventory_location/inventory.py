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
    empty_quantity = fields.Selection(
        'get_empty_quantities', "Empty Quantity",
        help="How lines without a quantity are handled.")
    complete_lines = fields.Boolean(
        "Complete",
        help="Add an inventory line for each missing product.")
    locations = fields.Many2Many('stock.location', None, None,
            'Locations', required=True, domain=[('type', '=', 'storage')])

    @classmethod
    def default_date(cls):
        return Pool().get('ir.date').today()

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def get_empty_quantities(cls):
        pool = Pool()
        Inventory = pool.get('stock.inventory')
        return Inventory.fields_get(
            ['empty_quantity'])['empty_quantity']['selection']

    @classmethod
    def default_empty_quantity(cls):
        pool = Pool()
        Inventory = pool.get('stock.inventory')
        try:
            return Inventory.default_empty_quantity()
        except AttributeError:
            return

    @classmethod
    def default_complete_lines(cls):
        return True


class CreateInventories(Wizard):
    'Create Inventories'
    __name__ = 'stock.inventory.create'
    start = StateView('stock.inventory.create.start',
        'stock_inventory_location.inventory_create_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('stock.act_inventory_form')

    def get_inventory(self, location, Inventory):
        return Inventory(
            location=location,
            date=self.start.date,
            company=self.start.company,
            empty_quantity=self.start.empty_quantity)

    def do_create_(self, action):
        pool = Pool()
        Inventory = pool.get('stock.inventory')

        inventories = [
            self.get_inventory(location, Inventory)
            for location in self.start.locations]
        Inventory.save(inventories)

        if self.start.complete_lines:
            Inventory.complete_lines(inventories)

        data = {'res_id': [i.id for i in inventories]}
        return action, data
