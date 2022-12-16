#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Account Configuration'
    _name = 'account.configuration'
    _description = __doc__

    default_account_receivable = fields.Function(fields.Many2One(
        'account.account', 'Default Account Receivable',
        domain=[
                ('kind', '=', 'receivable'),
                ('company', '=', Eval('context', {}).get('company')),
                ]),
        'get_account', setter='set_account')
    default_account_payable = fields.Function(fields.Many2One(
        'account.account', 'Default Account Payable',
        domain=[
                ('kind', '=', 'payable'),
                ('company', '=', Eval('context', {}).get('company')),
                ]),
        'get_account', setter='set_account')

    def get_account(self, ids, name):
        property_obj = Pool().get('ir.property')
        model_field_obj = Pool().get('ir.model.field')
        company_id = Transaction().context.get('company')
        account_field_id, = model_field_obj.search([
            ('model.model', '=', 'party.party'),
            ('name', '=', name[8:]),
            ], limit=1)
        property_ids = property_obj.search([
            ('field', '=', account_field_id),
            ('res', '=', None),
            ('company', '=', company_id),
            ], limit=1)
        if property_ids:
            prop = property_obj.browse(property_ids[0])
            value = int(prop.value.split(',')[1])
        else:
            value = None
        return dict((x, value) for x in ids)

    def set_account(self, ids, name, value):
        property_obj = Pool().get('ir.property')
        model_field_obj = Pool().get('ir.model.field')
        company_id = Transaction().context.get('company')
        account_field_id, = model_field_obj.search([
            ('model.model', '=', 'party.party'),
            ('name', '=', name[8:]),
            ], limit=1)
        property_ids = property_obj.search([
            ('field', '=', account_field_id),
            ('res', '=', None),
            ('company', '=', company_id),
            ])
        with Transaction().set_user(0):
            property_obj.delete(property_ids)
            if value:
                property_obj.create({
                    'field': account_field_id,
                    'value': 'account.account,%s' % value,
                    'company': company_id,
                    })

Configuration()
