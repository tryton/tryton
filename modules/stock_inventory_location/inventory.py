#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, fields
from trytond.wizard import Wizard


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

    def default_lost_found(self, cursor, user, context=None):
        location_obj = self.pool.get('stock.location')
        location_ids = location_obj.search(cursor, user,
                self.lost_found.domain, context=context)
        if len(location_ids) == 1:
            return location_ids[0]
        return False

    def default_company(self, cursor, user, context=None):
        if context is None:
            context = {}
        return context.get('company', False)

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

    def _action_create_inventory(self, cursor, user, data, context=None):
        inventory_obj = self.pool.get('stock.inventory')
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')

        inventory_ids = []
        location_ids = data['form']['locations'][0][1] or []

        for location_id in location_ids:
            inventory_ids.append(inventory_obj.create(cursor, user, {
                'location': location_id,
                'date': data['form']['date'],
                'lost_found': data['form']['lost_found'],
                'company': data['form']['company'],
                }, context=context))

        inventory_obj.complete_lines(cursor, user, inventory_ids,
                context=context)

        act_window_id = model_data_obj.get_id(cursor, user, 'stock',
                'act_inventory_form', context=context)
        res = act_window_obj.read(cursor, user, act_window_id, context=context)
        res['res_id'] = inventory_ids
        return res

CreateInventories()
