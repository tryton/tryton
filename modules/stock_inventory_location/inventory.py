#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.transaction import Transaction
from trytond.pool import Pool


class CreateInventoriesStart(ModelView):
    'Create Inventories'
    _name = 'stock.inventory.create.start'
    _description = __doc__

    date = fields.Date('Date', required=True)
    lost_found = fields.Many2One(
        'stock.location', 'Lost and Found', required=True,
        domain=[('type', '=', 'lost_found')])
    company = fields.Many2One('company.company', 'Company', required=True,
            select=True)
    locations = fields.Many2Many('stock.location', None, None,
            'Locations', required=True, domain=[('type', '=', 'storage')])

    def default_lost_found(self):
        location_obj = Pool().get('stock.location')
        location_ids = location_obj.search(self.lost_found.domain)
        if len(location_ids) == 1:
            return location_ids[0]

    def default_company(self):
        return Transaction().context.get('company')

CreateInventoriesStart()


class CreateInventories(Wizard):
    'Create Inventories'
    _name = 'stock.inventory.create'

    start = StateView('stock.inventory.create.start',
        'stock_inventory_location.inventory_create_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('stock.act_inventory_form')

    def do_create_(self, session, action):
        pool = Pool()
        inventory_obj = pool.get('stock.inventory')

        inventory_ids = []
        location_ids = [x.id for x in session.start.locations]

        for location_id in location_ids:
            inventory_ids.append(inventory_obj.create({
                        'location': location_id,
                        'date': session.start.date,
                        'lost_found': session.start.lost_found.id,
                        'company': session.start.company.id,
                        }))

        inventory_obj.complete_lines(inventory_ids)

        data = {'res_id': inventory_ids}
        return action, data

CreateInventories()
