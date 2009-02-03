#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.wizard import Wizard, WizardOSV
from trytond.osv import fields


class CreateInventoriesInit(WizardOSV):
    'Create Inventories Init'
    _name = 'stock.inventory.create.init'
    _description = __doc__

    date = fields.Date('Date')
    lost_found = fields.Many2One(
        'stock.location', 'Lost and Found', required=True,
        domain=[('type', '=', 'lost_found')])
    company = fields.Many2One('company.company', 'Company', required=True)
    locations = fields.Many2Many('stock.location', None, None, None,
            'Locations', required=True, domain=[('type', '=', 'storage')])
    products = fields.Many2Many('product.product', None, None, None,
            'Products', domain=[('type', '=', 'stockable')])
    categories = fields.Many2Many('product.category', None, None, None,
            'Categories')

    def default_lost_found(self, cursor, user, context=None):
        location_obj = self.pool.get('stock.location')
        location_ids = location_obj.search(cursor, user,
                self.lost_found.domain, context=context)
        if len(location_ids) == 1:
            return location_obj.name_get(cursor, user, location_ids,
                    context=context)[0]
        return False

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
                    context=context)[0]
        return False

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
        category_obj = self.pool.get('product.category')
        product_obj = self.pool.get('product.product')
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')

        inventory_ids = []
        location_ids = data['form']['locations'][0][1] or []
        product_ids = data['form']['products'][0][1] or []
        category_ids = data['form']['categories'][0][1] or []

        if category_ids:
            child_category_ids = category_obj.search(cursor, user,
                    [('parent', 'child_of', category_ids)], context=context)
            cat_product_ids = product_obj.search(cursor, user, [
                ('category', 'in', child_category_ids),
                ('type', '=', 'stockable'),
                ], context=context)
            if cat_product_ids:
                product_ids += cat_product_ids

        for location_id in location_ids:
            inventory_ids.append(inventory_obj.create(cursor, user, {
                'location': location_id,
                'date': data['form']['date'],
                'lost_found': data['form']['lost_found'],
                'company': data['form']['company'],
                }, context=context))

        inventory_obj.complete_lines(cursor, user, inventory_ids,
            product_ids=product_ids, context=context)

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_inventory_form'),
            ('module', '=', 'stock'),
            ('inherit', '=', False),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['res_id'] = inventory_ids
        return res

CreateInventories()
