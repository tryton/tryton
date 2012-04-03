#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import logging
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.pyson import Bool, Eval
from trytond.transaction import Transaction
from trytond.pool import Pool

HAS_VATNUMBER = False
VAT_COUNTRIES = [('', '')]
try:
    import vatnumber
    HAS_VATNUMBER = True
    for country in vatnumber.countries():
        VAT_COUNTRIES.append((country, country))
except ImportError:
    logging.getLogger('party').warning(
            'Unable to import vatnumber. VAT number validation disabled.')

STATES = {
    'readonly': ~Eval('active', True),
}
DEPENDS = ['active']


class Party(ModelSQL, ModelView):
    "Party"
    _description = __doc__
    _name = "party.party"

    name = fields.Char('Name', required=True, select=True,
        states=STATES, depends=DEPENDS)
    code = fields.Char('Code', required=True, select=True,
        order_field="%(table)s.code_length %(order)s, " \
            "%(table)s.code %(order)s",
        states={
            'readonly': Eval('code_readonly', True),
            },
        depends=['code_readonly'])
    code_length = fields.Integer('Code Length', select=True, readonly=True)
    code_readonly = fields.Function(fields.Boolean('Code Readonly'),
        'get_code_readonly')
    lang = fields.Many2One("ir.lang", 'Language', states=STATES,
        depends=DEPENDS)
    vat_number = fields.Char('VAT Number', help="Value Added Tax number",
        states={
            'readonly': ~Eval('active', True),
            'required': Bool(Eval('vat_country')),
            },
        depends=['active', 'vat_country'])
    vat_country = fields.Selection(VAT_COUNTRIES, 'VAT Country', states=STATES,
        depends=DEPENDS,
        help="Setting VAT country will enable validation of the VAT number.",
        translate=False)
    vat_code = fields.Function(fields.Char('VAT Code',
        on_change_with=['vat_number', 'vat_country']), 'get_vat_code',
        searcher='search_vat_code')
    addresses = fields.One2Many('party.address', 'party',
        'Addresses', states=STATES, depends=DEPENDS)
    contact_mechanisms = fields.One2Many('party.contact_mechanism', 'party',
        'Contact Mechanisms', states=STATES, depends=DEPENDS)
    categories = fields.Many2Many('party.party-party.category',
        'party', 'category', 'Categories', states=STATES, depends=DEPENDS)
    active = fields.Boolean('Active', select=True)
    full_name = fields.Function(fields.Char('Full Name'), 'get_full_name')
    phone = fields.Function(fields.Char('Phone'), 'get_mechanism')
    mobile = fields.Function(fields.Char('Mobile'), 'get_mechanism')
    fax = fields.Function(fields.Char('Fax'), 'get_mechanism')
    email = fields.Function(fields.Char('E-Mail'), 'get_mechanism')
    website = fields.Function(fields.Char('Website'), 'get_mechanism')

    def __init__(self):
        super(Party, self).__init__()
        self._sql_constraints = [
            ('code_uniq', 'UNIQUE(code)',
             'The code of the party must be unique!')
        ]
        self._constraints += [
            ('check_vat', 'invalid_vat'),
        ]
        self._error_messages.update({
            'invalid_vat': 'Invalid VAT number!',
        })
        self._order.insert(0, ('name', 'ASC'))

    def default_active(self):
        return True

    def default_categories(self):
        return Transaction().context.get('categories', [])

    def default_addresses(self):
        address_obj = Pool().get('party.address')
        fields_names = list(x for x in set(address_obj._columns.keys()
                + address_obj._inherit_fields.keys())
                if x not in ['id', 'create_uid', 'create_date',
                    'write_uid', 'write_date'])
        return [address_obj.default_get(fields_names)]

    def default_lang(self):
        config_obj = Pool().get('party.configuration')
        config = config_obj.browse(1)
        return config.party_lang.id

    def default_code_readonly(self):
        config_obj = Pool().get('party.configuration')
        config = config_obj.browse(1)
        return bool(config.party_sequence)

    def get_code_readonly(self, ids, name):
        return dict((x, True) for x in ids)

    def on_change_with_vat_code(self, vals):
        return (vals.get('vat_country') or '') + (vals.get('vat_number') or '')

    def get_vat_code(self, ids, name):
        if not ids:
            return []
        res = {}
        for party in self.browse(ids):
            res[party.id] = ((party.vat_country or '')
                + (party.vat_number or ''))
        return res

    def search_vat_code(self, name, clause):
        res = []
        value = clause[2]
        for country, _ in VAT_COUNTRIES:
            if isinstance(value, basestring) \
                    and country \
                    and value.upper().startswith(country):
                res.append(('vat_country', '=', country))
                value = value[len(country):]
                break
        res.append(('vat_number', clause[1], value))
        return res

    def get_full_name(self, ids, name):
        if not ids:
            return []
        res = {}
        for party in self.browse(ids):
            res[party.id] = party.name
        return res

    def get_mechanism(self, ids, name):
        if not ids:
            return []
        res = {}
        for party in self.browse(ids):
            res[party.id] = ''
            for mechanism in party.contact_mechanisms:
                if mechanism.type == name:
                    res[party.id] = mechanism.value
                    break
        return res

    def create(self, values):
        sequence_obj = Pool().get('ir.sequence')
        config_obj = Pool().get('party.configuration')

        values = values.copy()
        if not values.get('code'):
            config = config_obj.browse(1)
            values['code'] = sequence_obj.get_id(config.party_sequence.id)

        values['code_length'] = len(values['code'])
        return super(Party, self).create(values)

    def write(self, ids, vals):
        if vals.get('code'):
            vals = vals.copy()
            vals['code_length'] = len(vals['code'])
        return super(Party, self).write(ids, vals)

    def copy(self, ids, default=None):
        address_obj = Pool().get('party.address')

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        if default is None:
            default = {}
        default = default.copy()
        default['code'] = None
        default['addresses'] = None
        new_ids = []
        for party in self.browse(ids):
            new_id = super(Party, self).copy(party.id, default=default)
            address_obj.copy([x.id for x in party.addresses],
                    default={
                        'party': new_id,
                        })
            new_ids.append(new_id)

        if int_id:
            return new_ids[0]
        return new_ids

    def search_rec_name(self, name, clause):
        ids = self.search([('code',) + clause[1:]], order=[])
        if ids:
            ids += self.search([('name',) + clause[1:]], order=[])
            return [('id', 'in', ids)]
        return [('name',) + clause[1:]]

    def address_get(self, party_id, type=None):
        """
        Try to find an address for the given type, if no type match
        the first address is return.
        """
        address_obj = Pool().get("party.address")
        address_ids = address_obj.search(
            [("party", "=", party_id), ("active", "=", True)],
            order=[('sequence', 'ASC'), ('id', 'ASC')])
        if not address_ids:
            return None
        default_address = address_ids[0]
        if not type:
            return default_address
        for address in address_obj.browse(address_ids):
            if address[type]:
                    return address.id
        return default_address

    def check_vat(self, ids):
        '''
        Check the VAT number depending of the country.
        http://sima-pc.com/nif.php
        '''
        if not HAS_VATNUMBER:
            return True
        for party in self.browse(ids):
            vat_number = party.vat_number

            if not party.vat_country:
                continue

            if not getattr(vatnumber, 'check_vat_' + \
                    party.vat_country.lower())(vat_number):

                #Check if user doesn't have put country code in number
                if vat_number.startswith(party.vat_country):
                    vat_number = vat_number[len(party.vat_country):]
                    self.write(party.id, {
                        'vat_number': vat_number,
                        })
                else:
                    return False
        return True

Party()


class PartyCategory(ModelSQL):
    'Party - Category'
    _name = 'party.party-party.category'
    _table = 'party_category_rel'
    _description = __doc__
    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
            required=True, select=True)
    category = fields.Many2One('party.category', 'Category',
        ondelete='CASCADE', required=True, select=True)

PartyCategory()


class CheckVIESNoResult(ModelView):
    'Check VIES'
    _name = 'party.check_vies.no_result'
    _description = __doc__

CheckVIESNoResult()


class CheckVIESResult(ModelView):
    'Check VIES'
    _name = 'party.check_vies.result'
    _description = __doc__
    parties_succeed = fields.Many2Many('party.party', None, None,
        'Parties Succeed', readonly=True, states={
            'invisible': ~Eval('parties_succeed'),
            })
    parties_failed = fields.Many2Many('party.party', None, None,
        'Parties Failed', readonly=True, states={
            'invisible': ~Eval('parties_failed'),
            })

CheckVIESResult()


class CheckVIES(Wizard):
    'Check VIES'
    _name = 'party.check_vies'
    start_state = 'check'

    check = StateTransition()
    result = StateView('party.check_vies.result',
        'party.check_vies_result', [
            Button('Ok', 'end', 'tryton-ok', True),
            ])
    no_result = StateView('party.check_vies.no_result',
        'party.check_vies_no_result', [
            Button('Ok', 'end', 'tryton-ok', True),
            ])

    def __init__(self):
        super(CheckVIES, self).__init__()
        self._error_messages.update({
            'vies_unavailable': 'The VIES service is unavailable, ' \
                    'try again later.',
            })

    def transition_check(self, session):
        party_obj = Pool().get('party.party')

        if not HAS_VATNUMBER or not hasattr(vatnumber, 'check_vies'):
            return 'no_result'

        parties_succeed = []
        parties_failed = []
        parties = party_obj.browse(Transaction().context.get('active_ids'))
        for party in parties:
            if not party.vat_code:
                continue
            try:
                if not vatnumber.check_vies(party.vat_code):
                    parties_failed.append(party.id)
                else:
                    parties_succeed.append(party.id)
            except Exception, e:
                if hasattr(e, 'faultstring') \
                        and hasattr(e.faultstring, 'find'):
                    if e.faultstring.find('INVALID_INPUT'):
                        parties_failed.append(party.id)
                        continue
                    if e.faultstring.find('SERVICE_UNAVAILABLE') \
                            or e.faultstring.find('MS_UNAVAILABLE') \
                            or e.faultstring.find('TIMEOUT') \
                            or e.faultstring.find('SERVER_BUSY'):
                        self.raise_user_error('vies_unavailable')
                raise
        session.result.parties_succeed = parties_succeed
        session.result.parties_failed = parties_failed
        return 'result'

    def default_result(self, session, fields):
        return {
            'parties_succeed': [p.id for p in session.result.parties_succeed],
            'parties_failed': [p.id for p in session.result.parties_failed],
            }

CheckVIES()
