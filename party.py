# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby

import stdnum.eu.vat as vat
import stdnum.exceptions
from sql import Null
from sql.functions import CharLength

from trytond.model import ModelView, ModelSQL, fields, Unique
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond import backend

__all__ = ['Party', 'PartyCategory', 'PartyIdentifier',
    'CheckVIESResult', 'CheckVIES']

VAT_COUNTRIES = [('', '')]
STATES = {
    'readonly': ~Eval('active', True),
}
DEPENDS = ['active']


class Party(ModelSQL, ModelView):
    "Party"
    __name__ = 'party.party'

    name = fields.Char('Name', select=True, states=STATES, depends=DEPENDS)
    code = fields.Char('Code', required=True, select=True,
        states={
            'readonly': Eval('code_readonly', True),
            },
        depends=['code_readonly'])
    code_readonly = fields.Function(fields.Boolean('Code Readonly'),
        'get_code_readonly')
    lang = fields.Property(fields.Many2One("ir.lang", 'Language',
            states=STATES, depends=DEPENDS))
    identifiers = fields.One2Many('party.identifier', 'party', 'Identifiers',
        states=STATES, depends=DEPENDS)
    vat_code = fields.Function(fields.Char('VAT Code'),
        'get_vat_code', searcher='search_vat_code')
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
        t = cls.__table__()
        cls._sql_constraints = [
            ('code_uniq', Unique(t, t.code),
             'The code of the party must be unique.')
        ]
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Property = pool.get('ir.property')
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        table = cls.__table__()

        super(Party, cls).__register__(module_name)

        table_h = TableHandler(cls, module_name)
        if table_h.column_exist('lang'):
            cursor.execute(*table.select(table.id, table.lang,
                    order_by=table.lang))
            for lang_id, group in groupby(cursor.fetchall(), lambda r: r[1]):
                ids = [id_ for id_, _ in group]
                if lang_id is not None:
                    value = '%s,%s' % (cls.lang.model_name, lang_id)
                else:
                    value = None
                Property.set('lang', cls.__name__, ids, value)
            table_h.drop_column('lang')

        # Migration from 3.8
        table_h.not_null_action('name', 'remove')

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
    def default_code_readonly():
        Configuration = Pool().get('party.configuration')
        config = Configuration(1)
        return bool(config.party_sequence)

    def get_code_readonly(self, name):
        return True

    @classmethod
    def _vat_types(cls):
        return ['eu_vat']

    def get_vat_code(self, name):
        types = self._vat_types()
        for identifier in self.identifiers:
            if identifier.type in types:
                return identifier.code

    @classmethod
    def search_vat_code(cls, name, clause):
        return [
            ('identifiers.code',) + tuple(clause[1:]),
            ('identifiers.type', 'in', cls._vat_types()),
            ]

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

    def get_rec_name(self, name):
        if not self.name:
            return '[' + self.code + ']'
        return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('code',) + tuple(clause[1:]),
            ('identifiers.code',) + tuple(clause[1:]),
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


class PartyCategory(ModelSQL):
    'Party - Category'
    __name__ = 'party.party-party.category'
    _table = 'party_category_rel'
    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
            required=True, select=True)
    category = fields.Many2One('party.category', 'Category',
        ondelete='CASCADE', required=True, select=True)


class PartyIdentifier(ModelSQL, ModelView):
    'Party Identifier'
    __name__ = 'party.identifier'
    _rec_name = 'code'
    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
        required=True, select=True)
    type = fields.Selection('get_types', 'Type')
    code = fields.Char('Code', required=True)

    @classmethod
    def __setup__(cls):
        super(PartyIdentifier, cls).__setup__()
        cls._error_messages.update({
                'invalid_vat': ('Invalid VAT number "%(code)s" '
                    'on party "%(party)s".'),
                })

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Party = pool.get('party.party')
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        party = Party.__table__()

        super(PartyIdentifier, cls).__register__(module_name)

        party_h = TableHandler(Party, module_name)
        if (party_h.column_exist('vat_number')
                and party_h.column_exist('vat_country')):
            identifiers = []
            cursor.execute(*party.select(
                    party.id, party.vat_number, party.vat_country,
                    where=(party.vat_number != Null)
                    | (party.vat_country != Null)))
            for party_id, number, country in cursor.fetchall():
                code = (country or '') + (number or '')
                if not code:
                    continue
                type = None
                if vat.is_valid(code):
                    type = 'eu_vat'
                identifiers.append(
                    cls(party=party_id, code=code, type=type))
            cls.save(identifiers)
            party_h.drop_column('vat_number')
            party_h.drop_column('vat_country')

    @classmethod
    def get_types(cls):
        return [
            (None, ''),
            ('eu_vat', 'VAT'),
            ]

    @fields.depends('type', 'code')
    def on_change_with_code(self):
        if self.type == 'eu_vat':
            try:
                return vat.compact(self.code)
            except stdnum.exceptions.ValidationError:
                pass
        return self.code

    def pre_validate(self):
        super(PartyIdentifier, self).pre_validate()
        self.check_code()

    def check_code(self):
        if self.type == 'eu_vat':
            if not vat.is_valid(self.code):
                if self.party.id > 0:
                    party = self.party.rec_name
                else:
                    party = ''
                self.raise_user_error('invalid_vat', {
                        'code': self.code,
                        'party': party,
                        })


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

    @classmethod
    def __setup__(cls):
        super(CheckVIES, cls).__setup__()
        cls._error_messages.update({
                'vies_unavailable': ('The VIES service is unavailable, '
                    'try again later.'),
                })

    def transition_check(self):
        Party = Pool().get('party.party')

        parties_succeed = []
        parties_failed = []
        parties = Party.browse(Transaction().context.get('active_ids'))
        for party in parties:
            for identifier in party.identifiers:
                if identifier.type != 'eu_vat':
                    continue
                try:
                    if not vat.check_vies(identifier.code):
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
