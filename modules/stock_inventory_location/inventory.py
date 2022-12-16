#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, fields
from trytond.wizard import Wizard
from trytond.transaction import Transaction
from trytond.pool import Pool


class CreateInventoriesInit(ModelView):
    'Create Inventories Init'
    _name = 'stock.inventory.create.init'
    _description = __doc__

    date = fields.Date('Date', required=True)
    lost_found = fields.Many2One(
        'stock.location', 'Lost and Found', required=True,
        domain=[('type', '=', 'lost_found')])
    company = fields.Many2One('company.company', 'Company', required=True)
    locations = fields.Many2Many('stock.location', None, None,
            'Locations', required=True, domain=[('type', '=', 'storage')])

    def default_lost_found(self):
        location_obj = Pool().get('stock.location')
        location_ids = location_obj.search(self.lost_found.domain)
        if len(location_ids) == 1:
            return location_ids[0]
        return False

    def default_company(self):
        return Transaction().context.get('company') or False

CreateInventoriesInit()


class CreateInventories(Wizard):
    'Create Inventories'
    _name = 'stock.inventory.create'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'stock.inventory.create.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('create', 'Create', 'tryton-ok', True),
                ],
            },
        },
        'create': {
            'result': {
                'type': 'action',
                'action': '_action_create_inventory',
                'state': 'end',
            },
        },
    }

    def _action_create_inventory(self, data):
        pool = Pool()
        inventory_obj = pool.get('stock.inventory')
        model_data_obj = pool.get('ir.model.data')
        act_window_obj = pool.get('ir.action.act_window')

        inventory_ids = []
        location_ids = data['form']['locations'][0][1] or []

        for location_id in location_ids:
            inventory_ids.append(inventory_obj.create({
                'location': location_id,
                'date': data['form']['date'],
                'lost_found': data['form']['lost_found'],
                'company': data['form']['company'],
                }))

        inventory_obj.complete_lines(inventory_ids)

        act_window_id = model_data_obj.get_id('stock', 'act_inventory_form')
        res = act_window_obj.read(act_window_id)
        res['res_id'] = inventory_ids
        return res

CreateInventories()
