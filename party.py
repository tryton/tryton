#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV
import logging

HAS_VATNUMBER = False
VAT_COUNTRIES = [('', '')]
try:
    import vatnumber
    HAS_VATNUMBER = True
    for country in vatnumber.countries():
        VAT_COUNTRIES.append((country, country))
except ImportError:
    logging.getLogger('relationship').warning(
            'Unable to import vatnumber. VAT number validation disable.')

STATES = {
    'readonly': "active == False",
}

def mult_add(a, b):
    '''
    Sum each digits of the multiplication of a and b.
    '''
    mult = a * b
    res = 0
    for i in range(len(str(mult))):
        res += int(str(mult)[i])
    return res


class PartyType(OSV):
    "Party Type"

    _name = 'relationship.party.type'
    _description = __doc__
    name = fields.Char('Name', required=True, size=None, translate=True)
    # TODO add into localisation modules: http://en.wikipedia.org/wiki/Types_of_companies

    def __init__(self):
        super(PartyType, self).__init__()
        self._order.insert(0, ('name', 'ASC'))

PartyType()


class Party(OSV):
    "Party"
    _description = __doc__
    _name = "relationship.party"

    name = fields.Char('Name', size=None, required=True, select=1,
           states=STATES)
    code = fields.Char('Code', size=None, required=True, select=1,
            readonly=True, order_field="%(table)s.code_length %(order)s, " \
                    "%(table)s.code %(order)s")
    code_length = fields.Integer('Code Length', select=1, readonly=True)
    type = fields.Many2One("relationship.party.type", "Type",
           states=STATES)
    lang = fields.Many2One("ir.lang", 'Language',
           states=STATES)
    vat_number = fields.Char('VAT Number',size=None,
            help="Value Added Tax number", states=STATES)
    vat_country = fields.Selection(VAT_COUNTRIES, 'VAT Country', states=STATES,
        help="Setting VAT country will enable verification of the VAT number.")
    vat_code = fields.Function('get_vat_code', type='char', string="VAT Code")
    website = fields.Char('Website',size=None,
           states=STATES)
    addresses = fields.One2Many('relationship.address', 'party',
           'Addresses',states=STATES)
    categories = fields.Many2Many(
            'relationship.category', 'relationship_category_rel',
            'party', 'category', 'Categories',
            states=STATES)
    active = fields.Boolean('Active', select=1)

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
        self._order.insert(0, ('name', 'DESC'))

    def default_active(self, cursor, user, context=None):
        return True

    def get_vat_code(self, cursor, user, ids, name, arg, context=None):
        if not ids:
            return []
        res = {}
        for party in self.browse(cursor, user, ids, context=context):
            res[party.id] = (party.vat_country or '') + (party.vat_number or '')
        return res

    def create(self, cursor, user, values, context=None):
        values = values.copy()
        if not values.get('code'):
            values['code'] = self.pool.get('ir.sequence').get(
                    cursor, user, 'relationship.party')
        values['code_length'] = len(values['code'])
        return super(Party, self).create(cursor, user, values, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if vals.get('code'):
            vals = vals.copy()
            vals['code_length'] = len(vals['code'])
        return super(Party, self).write(cursor, user, ids, vals, context=context)

    def copy(self, cursor, user, object_id, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default['code'] = False
        return super(Party, self).copy(cursor, user, object_id, default=default,
                context=context)

    def name_search(self, cursor, user, name, args=None, operator='ilike',
            context=None, limit=None):
        if not args:
            args = []
        ids = self.search(cursor, user, [('code', '=', name)] + args,
                limit=limit, context=context)
        if ids:
            return self.name_get(cursor, user, ids, context=context)
        return super(Party, self).name_search(cursor, user, name,
                args=args, operator=operator, context=context, limit=limit)

    def address_get(self, cursor, user, party_id, type=None, context=None):
        """
        Try to find an address for the given type, if no type match
        the first address is return.
        """
        address_obj = self.pool.get("relationship.address")
        address_ids = address_obj.search(
            cursor, user, [("party","=",party_id),("active","=",True)],
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
