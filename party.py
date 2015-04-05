# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
from importlib import import_module

from sql.functions import CharLength

from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.pyson import Bool, Eval
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['Party', 'PartyCategory', 'CheckVIESNoResult', 'CheckVIESResult',
           'CheckVIES']

logger = logging.getLogger(__name__)

HAS_VATNUMBER = False
VAT_COUNTRIES = [('', '')]
try:
    import vatnumber
    HAS_VATNUMBER = True
    for country in vatnumber.countries():
        VAT_COUNTRIES.append((country, country))
except ImportError:
    logger.warning(
        'Unable to import vatnumber. VAT number validation disabled.',
        exc_info=True)

STATES = {
    'readonly': ~Eval('active', True),
}
DEPENDS = ['active']


class Party(ModelSQL, ModelView):
    "Party"
    __name__ = 'party.party'

    name = fields.Char('Name', required=True, select=True,
        states=STATES, depends=DEPENDS)
    code = fields.Char('Code', required=True, select=True,
        states={
            'readonly': Eval('code_readonly', True),
            },
        depends=['code_readonly'])
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
    vat_code = fields.Function(fields.Char('VAT Code'),
        'on_change_with_vat_code', searcher='search_vat_code')
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

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._sql_constraints = [
            ('code_uniq', 'UNIQUE(code)',
             'The code of the party must be unique.')
        ]
        cls._error_messages.update({
                'invalid_vat': ('Invalid VAT number "%(vat)s" on party '
                    '"%(party)s".'),
                })
        cls._order.insert(0, ('name', 'ASC'))

    @staticmethod
    def order_code(tables):
        table, _ = tables[None]
        return [CharLength(table.code), table.code]

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_categories():
        return Transaction().context.get('categories', [])

    @staticmethod
    def default_addresses():
        if Transaction().user == 0:
            return []
        Address = Pool().get('party.address')
        fields_names = list(x for x in Address._fields.keys()
            if x not in ('id', 'create_uid', 'create_date',
                'write_uid', 'write_date'))
        return [Address.default_get(fields_names)]

    @staticmethod
    def default_lang():
        Configuration = Pool().get('party.configuration')
        config = Configuration(1)
        if config.party_lang:
            return config.party_lang.id

    @staticmethod
    def default_code_readonly():
        Configuration = Pool().get('party.configuration')
        config = Configuration(1)
        return bool(config.party_sequence)

    def get_code_readonly(self, name):
        return True

    @fields.depends('vat_country', 'vat_number')
    def on_change_with_vat_code(self, name=None):
        return (self.vat_country or '') + (self.vat_number or '')

    @fields.depends('vat_country', 'vat_number')
    def on_change_with_vat_number(self):
        if not self.vat_country:
            return self.vat_number
        code = self.vat_country.lower()
        vat_module = None
        try:
            module = import_module('stdnum.%s' % code)
            vat_module = getattr(module, 'vat', None)
            if not vat_module:
                vat_module = import_module('stdnum.%s.vat' % code)
        except ImportError:
            pass
        if vat_module:
            return vat_module.compact(self.vat_number)
        return self.vat_number

    @classmethod
    def search_vat_code(cls, name, clause):
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

    def get_full_name(self, name):
        return self.name

    def get_mechanism(self, name):
        for mechanism in self.contact_mechanisms:
            if mechanism.type == name:
                return mechanism.value
        return ''

    @classmethod
    def create(cls, vlist):
        Sequence = Pool().get('ir.sequence')
        Configuration = Pool().get('party.configuration')

        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('code'):
                config = Configuration(1)
                values['code'] = Sequence.get_id(config.party_sequence.id)
            values.setdefault('addresses', None)
        return super(Party, cls).create(vlist)

    @classmethod
    def copy(cls, parties, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['code'] = None
        return super(Party, cls).copy(parties, default=default)

    @classmethod
    def search_global(cls, text):
        for record, rec_name, icon in super(Party, cls).search_global(text):
            icon = icon or 'tryton-party'
            yield record, rec_name, icon

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('code',) + tuple(clause[1:]),
            ('name',) + tuple(clause[1:]),
            ]

    def address_get(self, type=None):
        """
        Try to find an address for the given type, if no type matches
        the first address is returned.
        """
        Address = Pool().get("party.address")
        addresses = Address.search(
            [("party", "=", self.id), ("active", "=", True)],
            order=[('sequence', 'ASC'), ('id', 'ASC')])
        if not addresses:
            return None
        default_address = addresses[0]
        if not type:
            return default_address
        for address in addresses:
            if getattr(address, type):
                return address
        return default_address

    @classmethod
    def validate(cls, parties):
        super(Party, cls).validate(parties)
        for party in parties:
            party.check_vat()

    def check_vat(self):
        '''
        Check the VAT number depending of the country.
        http://sima-pc.com/nif.php
        '''
        if not HAS_VATNUMBER:
            return

        if not self.vat_country:
            return

        vat_number = self.on_change_with_vat_number()
        if vat_number != self.vat_number:
            self.vat_number = vat_number
            self.save()

        if not getattr(vatnumber, 'check_vat_' +
                self.vat_country.lower())(vat_number):
            self.raise_user_error('invalid_vat', {
                    'vat': vat_number,
                    'party': self.rec_name,
                    })


class PartyCategory(ModelSQL):
    'Party - Category'
    __name__ = 'party.party-party.category'
    _table = 'party_category_rel'
    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
            required=True, select=True)
    category = fields.Many2One('party.category', 'Category',
        ondelete='CASCADE', required=True, select=True)


class CheckVIESNoResult(ModelView):
    'Check VIES'
    __name__ = 'party.check_vies.no_result'


class CheckVIESResult(ModelView):
    'Check VIES'
    __name__ = 'party.check_vies.result'
    parties_succeed = fields.Many2Many('party.party', None, None,
        'Parties Succeed', readonly=True, states={
            'invisible': ~Eval('parties_succeed'),
            })
    parties_failed = fields.Many2Many('party.party', None, None,
        'Parties Failed', readonly=True, states={
            'invisible': ~Eval('parties_failed'),
            })


class CheckVIES(Wizard):
    'Check VIES'
    __name__ = 'party.check_vies'
    start_state = 'check'

    check = StateTransition()
    result = StateView('party.check_vies.result',
        'party.check_vies_result', [
            Button('OK', 'end', 'tryton-ok', True),
            ])
    no_result = StateView('party.check_vies.no_result',
        'party.check_vies_no_result', [
            Button('OK', 'end', 'tryton-ok', True),
            ])

    @classmethod
    def __setup__(cls):
        super(CheckVIES, cls).__setup__()
        cls._error_messages.update({
                'vies_unavailable': ('The VIES service is unavailable, '
                    'try again later.'),
                })

    def transition_check(self):
        Party = Pool().get('party.party')

        if not HAS_VATNUMBER or not hasattr(vatnumber, 'check_vies'):
            return 'no_result'

        parties_succeed = []
        parties_failed = []
        parties = Party.browse(Transaction().context.get('active_ids'))
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
        self.result.parties_succeed = parties_succeed
        self.result.parties_failed = parties_failed
        return 'result'

    def default_result(self, fields):
        return {
            'parties_succeed': [p.id for p in self.result.parties_succeed],
            'parties_failed': [p.id for p in self.result.parties_failed],
            }
