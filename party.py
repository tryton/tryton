#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
import logging

HAS_VATNUMBER = False
VAT_COUNTRIES = [('', '')]
try:
    import vatnumber
    HAS_VATNUMBER = True
    for country in vatnumber.countries():
        VAT_COUNTRIES.append((country, country))
except ImportError:
    logging.getLogger('party').warning(
            'Unable to import vatnumber. VAT number validation disable.')

STATES = {
    'readonly': "active == False",
}


class Party(ModelSQL, ModelView):
    "Party"
    _description = __doc__
    _name = "party.party"

    name = fields.Char('Name', required=True, select=1,
           states=STATES)
    code = fields.Char('Code', required=True, select=1,
            readonly=True, order_field="%(table)s.code_length %(order)s, " \
                    "%(table)s.code %(order)s")
    code_length = fields.Integer('Code Length', select=1, readonly=True)
    lang = fields.Many2One("ir.lang", 'Language', states=STATES)
    vat_number = fields.Char('VAT Number', help="Value Added Tax number",
            states=STATES)
    vat_country = fields.Selection(VAT_COUNTRIES, 'VAT Country', states=STATES,
        help="Setting VAT country will enable verification of the VAT number.",
        translate=False)
    vat_code = fields.Function('get_vat_code', type='char', string="VAT Code",
            fnct_search='search_vat_code')
    addresses = fields.One2Many('party.address', 'party',
           'Addresses', states=STATES)
    contact_mechanisms = fields.One2Many('party.contact_mechanism', 'party',
            'Contact Mechanisms', states=STATES)
    categories = fields.Many2Many(
            'party.category', 'party_category_rel',
            'party', 'category', 'Categories',
            states=STATES)
    active = fields.Boolean('Active', select=1)
    full_name = fields.Function('get_full_name', type='char')
    phone = fields.Function('get_mechanism', arg='phone', type='char',
            string='Phone')
    mobile = fields.Function('get_mechanism', arg='mobile', type='char',
            string='Mobile')
    fax = fields.Function('get_mechanism', arg='fax', type='char',
            string='Fax')
    email = fields.Function('get_mechanism', arg='email', type='char',
            string='E-Mail')
    website = fields.Function('get_mechanism', arg='website', type='char',
            string='Website')

    def __init__(self):
        super(Party, self).__init__()
        self._sql_constraints = [
            ('code_uniq', 'UNIQUE(code)',
             'The code of the party must be unique!')
        ]
        self._constraints += [
            ('check_vat', 'wrong_vat'),
        ]
        self._error_messages.update({
            'wrong_vat': 'Wrong VAT number!',
        })
        self._order.insert(0, ('name', 'ASC'))

    def default_active(self, cursor, user, context=None):
        return True

    def default_categories(self, cursor, user, context=None):
        if context is None:
            context = {}
        return context.get('categories', [])

    def get_vat_code(self, cursor, user, ids, name, arg, context=None):
        if not ids:
            return []
        res = {}
        for party in self.browse(cursor, user, ids, context=context):
            res[party.id] = (party.vat_country or '') + (party.vat_number or '')
        return res

    def search_vat_code(self, cursor, user, name, args, context=None):
        args2 = []
        i = 0
        while i < len(args):
            value = args[i][2]
            for country, _ in VAT_COUNTRIES:
                if value.startswith(country) and country:
                    args2.append(('vat_country', '=', country))
                    value = value[len(country):]
                    break
            args2.append(('vat_number', args[i][1], value))
            i += 1
        return args2

    def get_full_name(self, cursor, user, ids, name, arg, context=None):
        if not ids:
            return []
        res = {}
        for party in self.browse(cursor, user, ids, context=context):
            res[party.id] = party.name
        return res

    def get_mechanism(self, cursor, user, ids, name, arg, context=None):
        if not ids:
            return []
        res = {}
        for party in self.browse(cursor, user, ids, context=context):
            res[party.id] = ''
            for mechanism in party.contact_mechanisms:
                if mechanism.type == arg:
                    res[party.id] = mechanism.value
        return res

    def create(self, cursor, user, values, context=None):
        values = values.copy()
        if not values.get('code'):
            values['code'] = self.pool.get('ir.sequence').get(
                    cursor, user, 'party.party', context=context)
        values['code_length'] = len(values['code'])
        return super(Party, self).create(cursor, user, values, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if vals.get('code'):
            vals = vals.copy()
            vals['code_length'] = len(vals['code'])
        return super(Party, self).write(cursor, user, ids, vals, context=context)

    def copy(self, cursor, user, ids, default=None, context=None):
        address_obj = self.pool.get('party.address')

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        if default is None:
            default = {}
        default = default.copy()
        default['code'] = False
        default['addresses'] = False
        new_ids = []
        for party in self.browse(cursor, user, ids, context=context):
            new_id = super(Party, self).copy(cursor, user, party.id,
                    default=default, context=context)
            address_obj.copy(cursor, user, [x.id for x in party.addresses],
                    default={
                        'party': new_id,
                        }, context=context)
            new_ids.append(new_id)

        if int_id:
            return new_ids[0]
        return new_ids

    def search_rec_name(self, cursor, user, name, args, context=None):
        args2 = []
        i = 0
        while i < len(args):
            ids = self.search(cursor, user, [('code', '=', args[i][2])],
                    context=context)
            if ids:
                args2.append(('id', 'in', ids))
            else:
                args2.append(('name', args[i][1], args[i][2]))
            i += 1
        return args2

    def address_get(self, cursor, user, party_id, type=None, context=None):
        """
        Try to find an address for the given type, if no type match
        the first address is return.
        """
        address_obj = self.pool.get("party.address")
        address_ids = address_obj.search(
            cursor, user, [("party", "=", party_id), ("active", "=", True)],
            order=[('sequence', 'ASC'), ('id', 'ASC')], context=context)
        if not address_ids:
            return False
        default_address = address_ids[0]
        if not type:
            return default_address
        for address in address_obj.browse(cursor, user, address_ids,
                context=context):
            if address[type]:
                    return address.id
        return default_address

    def check_vat(self, cursor, user, ids):
        '''
        Check the VAT number depending of the country.
        http://sima-pc.com/nif.php
        '''
        if not HAS_VATNUMBER:
            return True
        for party in self.browse(cursor, user, ids):
            vat_number = party.vat_number

            if not (vat_number and party.vat_country):
                continue

            if not getattr(vatnumber, 'check_vat_' + \
                    party.vat_country.lower())(vat_number):

                #Check if user doesn't have put country code in number
                if vat_number.startswith(party.vat_country):
                    vat_number = vat_number[len(party.vat_country):]
                    self.write(cursor, user, party.id, {
                        'vat_number': vat_number,
                        })
                else:
                    return False
        return True

Party()
