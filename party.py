# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby

import stdnum.eu.vat as vat
import stdnum.exceptions
from sql import Null, Column
from sql.functions import CharLength

from trytond.model import ModelView, ModelSQL, fields, Unique, sequence_ordered
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond import backend

__all__ = ['Party', 'PartyCategory', 'PartyIdentifier',
    'CheckVIESResult', 'CheckVIES',
    'PartyReplace', 'PartyReplaceAsk']

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
    tax_identifier = fields.Function(fields.Many2One(
            'party.identifier', 'Tax Identifier'),
        'get_tax_identifier', searcher='search_tax_identifier')
    addresses = fields.One2Many('party.address', 'party',
        'Addresses', states=STATES, depends=DEPENDS)
    contact_mechanisms = fields.One2Many('party.contact_mechanism', 'party',
        'Contact Mechanisms', states=STATES, depends=DEPENDS)
    categories = fields.Many2Many('party.party-party.category',
        'party', 'category', 'Categories', states=STATES, depends=DEPENDS)
    active = fields.Boolean('Active', select=True, states={
            'readonly': Bool(Eval('replaced_by')),
            },
        depends=['replaced_by'])
    replaced_by = fields.Many2One('party.party', "Replaced By", readonly=True,
        states={
            'invisible': ~Eval('replaced_by'),
            })
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
        return [{}]

    @staticmethod
    def default_code_readonly():
        Configuration = Pool().get('party.configuration')
        config = Configuration(1)
        return bool(config.party_sequence)

    def get_code_readonly(self, name):
        return True

    @classmethod
    def _tax_identifier_types(cls):
        return ['eu_vat']

    def get_tax_identifier(self, name):
        types = self._tax_identifier_types()
        for identifier in self.identifiers:
            if identifier.type in types:
                return identifier.id

    @classmethod
    def search_tax_identifier(cls, name, clause):
        _, operator, value = clause
        types = cls._tax_identifier_types()
        domain = [
            ('identifiers', 'where', [
                    ('code', operator, value),
                    ('type', 'in', types),
                    ]),
            ]
        # Add party without tax identifier
        if ((operator == '=' and value is None)
                or (operator == 'in' and None in value)):
            domain = ['OR',
                domain, [
                    ('identifiers', 'not where', [
                            ('type', 'in', types),
                            ]),
                    ],
                ]
        return domain

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


class PartyIdentifier(sequence_ordered(), ModelSQL, ModelView):
    'Party Identifier'
    __name__ = 'party.identifier'
    _rec_name = 'code'
    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
        required=True, select=True)
    type = fields.Selection('get_types', 'Type')
    type_string = type.translated('type')
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

    @fields.depends('type', 'party', 'code')
    def check_code(self):
        if self.type == 'eu_vat':
            if not vat.is_valid(self.code):
                if self.party and self.party.id > 0:
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


class PartyReplace(Wizard):
    "Replace Party"
    __name__ = 'party.replace'
    start_state = 'ask'
    ask = StateView('party.replace.ask', 'party.replace_ask_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Replace", 'replace', 'tryton-find-replace', default=True),
            ])
    replace = StateTransition()

    @classmethod
    def __setup__(cls):
        super(PartyReplace, cls).__setup__()
        cls._error_messages.update({
                'different_name': ("Parties have different names: "
                    "%(source_name)s vs %(destination_name)s."),
                'different_tax_identifier': (
                    "Parties have different Tax Identifier: "
                    "%(source_code)s vs %(destination_code)s."),
                })

    def check_similarity(self):
        source = self.ask.source
        destination = self.ask.destination
        if source.name != destination.name:
            key = 'party.replace name %s %s' % (source.id, destination.id)
            self.raise_user_warning(key, 'different_name', {
                    'source_name': source.name,
                    'destination_name': destination.name,
                    })
        source_code = (source.tax_identifier.code
            if source.tax_identifier else '')
        destination_code = (destination.tax_identifier.code
            if destination.tax_identifier else '')
        if source_code != destination_code:
            key = 'party.replace tax_identifier %s %s' % (
                source.id, destination.id)
            self.raise_user_warning(key, 'different_tax_identifier', {
                    'source_code': source_code,
                    'destination_code': destination_code,
                    })

    def transition_replace(self):
        pool = Pool()
        Address = pool.get('party.address')
        ContactMechanism = pool.get('party.contact_mechanism')
        transaction = Transaction()

        self.check_similarity()
        source = self.ask.source
        destination = self.ask.destination

        Address.write(list(source.addresses), {
                'active': False,
                })
        ContactMechanism.write(list(source.contact_mechanisms), {
                'active': False,
                })
        source.replaced_by = destination
        source.active = False
        source.save()

        cursor = transaction.connection.cursor()
        for model_name, field_name in self.fields_to_replace():
            Model = pool.get(model_name)
            table = Model.__table__()
            column = Column(table, field_name)
            where = column == source.id

            if transaction.database.has_returning():
                returning = [table.id]
            else:
                cursor.execute(*table.select(table.id, where=where))
                ids = [x[0] for x in cursor]
                returning = None

            cursor.execute(*table.update(
                    [column],
                    [destination.id],
                    where=where,
                    returning=returning))

            if transaction.database.has_returning():
                ids = [x[0] for x in cursor]

            Model._insert_history(ids)
        return 'end'

    @classmethod
    def fields_to_replace(cls):
        return [
            ('party.address', 'party'),
            ('party.contact_mechanism', 'party'),
            ]


class PartyReplaceAsk(ModelView):
    "Replace Party"
    __name__ = 'party.replace.ask'
    source = fields.Many2One('party.party', "Source", required=True)
    destination = fields.Many2One('party.party', "Destination", required=True,
        domain=[
            ('id', '!=', Eval('source', -1)),
            ],
        depends=['source'])

    @classmethod
    def default_source(cls):
        context = Transaction().context
        if context.get('active_model') == 'party.party':
            return context.get('active_id')

    @fields.depends('source')
    def on_change_source(self):
        if self.source and self.source.replaced_by:
            self.destination = self.source.replaced_by
