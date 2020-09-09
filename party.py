# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from stdnum import get_cc_module
import stdnum.exceptions
from sql import Null, Column, Literal
from sql.functions import CharLength, Substring, Position

from trytond.i18n import gettext
from trytond.model import (ModelView, ModelSQL, MultiValueMixin, ValueMixin,
    DeactivableMixin, fields, Unique, sequence_ordered)
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond import backend
from trytond.tools.multivalue import migrate_property
from trytond.tools import lstrip_wildcard
from .exceptions import (
    InvalidIdentifierCode, VIESUnavailable, SimilarityWarning, EraseError)


class Party(DeactivableMixin, ModelSQL, ModelView, MultiValueMixin):
    "Party"
    __name__ = 'party.party'

    name = fields.Char(
        "Name", select=True,
        help="The main identifier of the party.")
    code = fields.Char('Code', required=True, select=True,
        states={
            'readonly': Eval('code_readonly', True),
            },
        depends=['code_readonly'],
        help="The unique identifier of the party.")
    code_readonly = fields.Function(fields.Boolean('Code Readonly'),
        'get_code_readonly')
    lang = fields.MultiValue(
        fields.Many2One('ir.lang', "Language",
            help="Used to translate communications with the party."))
    langs = fields.One2Many(
        'party.party.lang', 'party', "Languages")
    identifiers = fields.One2Many(
        'party.identifier', 'party', "Identifiers",
        help="Add other identifiers of the party.")
    tax_identifier = fields.Function(fields.Many2One(
            'party.identifier', 'Tax Identifier',
            help="The identifier used for tax report."),
        'get_tax_identifier', searcher='search_tax_identifier')
    addresses = fields.One2Many('party.address', 'party', "Addresses")
    contact_mechanisms = fields.One2Many(
        'party.contact_mechanism', 'party', "Contact Mechanisms")
    categories = fields.Many2Many(
        'party.party-party.category', 'party', 'category', "Categories",
        help="The categories the party belongs to.")
    replaced_by = fields.Many2One('party.party', "Replaced By", readonly=True,
        states={
            'invisible': ~Eval('replaced_by'),
            },
        help="The party replacing this one.")
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
            ('code_uniq', Unique(t, t.code), 'party.msg_party_code_unique')
            ]
        cls._order.insert(0, ('name', 'ASC'))
        cls.active.states.update({
                'readonly': Bool(Eval('replaced_by')),
                })
        cls.active.depends.append('replaced_by')

    @classmethod
    def __register__(cls, module_name):
        super(Party, cls).__register__(module_name)

        table_h = cls.__table_handler__(module_name)

        # Migration from 3.8
        table_h.not_null_action('name', 'remove')

    @staticmethod
    def order_code(tables):
        table, _ = tables[None]
        return [CharLength(table.code), table.code]

    @staticmethod
    def default_categories():
        return Transaction().context.get('categories', [])

    @staticmethod
    def default_addresses():
        if Transaction().user == 0:
            return []
        return [{}]

    @classmethod
    def default_lang(cls, **pattern):
        Configuration = Pool().get('party.configuration')
        config = Configuration(1)
        lang = config.get_multivalue('party_lang', **pattern)
        return lang.id if lang else None

    @classmethod
    def default_code_readonly(cls, **pattern):
        Configuration = Pool().get('party.configuration')
        config = Configuration(1)
        return bool(config.get_multivalue('party_sequence', **pattern))

    def get_code_readonly(self, name):
        return True

    @classmethod
    def tax_identifier_types(cls):
        return [
            'ad_nrt', 'al_nipt', 'ar_cuit', 'be_vat', 'bg_vat', 'ch_vat',
            'cl_rut', 'co_rut', 'cz_dic', 'de_vat', 'do_rnc',
            'dk_cvr', 'ec_ruc', 'ee_kmkr', 'es_cif', 'es_nie', 'es_nif',
            'eu_vat', 'fi_alv', 'fr_tva', 'gb_vat', 'gr_vat', 'gt_nit',
            'hu_anum', 'ie_vat', 'is_vsk', 'it_iva', 'jp_cn', 'lt_pvm',
            'lu_tva', 'lv_pvn', 'mc_tva', 'md_idno', 'mt_vat', 'mx_rfc',
            'nl_btw', 'no_mva', 'nz_ird', 'pe_ruc', 'pl_nip', 'pt_nif',
            'py_ruc', 'ro_cf', 'rs_pib', 'ru_inn', 'se_vat', 'si_ddv',
            'sk_dph', 'sm_coe', 'us_atin', 'us_ein', 'us_itin', 'us_ptin',
            'us_ssn', 'us_tin', 'uy_ruc', 've_rif', 'za_tin']

    def get_tax_identifier(self, name):
        types = self.tax_identifier_types()
        for identifier in self.identifiers:
            if identifier.type in types:
                return identifier.id

    @classmethod
    def search_tax_identifier(cls, name, clause):
        _, operator, value = clause
        types = cls.tax_identifier_types()
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
    def _new_code(cls, **pattern):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Configuration = pool.get('party.configuration')
        config = Configuration(1)
        sequence = config.get_multivalue('party_sequence', **pattern)
        if sequence:
            return Sequence.get_id(sequence.id)

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('code'):
                values['code'] = cls._new_code()
            values.setdefault('addresses', None)
        return super(Party, cls).create(vlist)

    @classmethod
    def copy(cls, parties, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('code', None)
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
        code_value = clause[2]
        if clause[1].endswith('like'):
            code_value = lstrip_wildcard(clause[2])
        return [bool_op,
            ('code', clause[1], code_value) + tuple(clause[3:]),
            ('identifiers.code', clause[1], code_value) + tuple(clause[3:]),
            ('name',) + tuple(clause[1:]),
            ('contact_mechanisms.rec_name',) + tuple(clause[1:]),
            ]

    def address_get(self, type=None):
        """
        Try to find an address for the given type, if no type matches
        the first address is returned.
        """
        default_address = None
        if self.addresses:
            default_address = self.addresses[0]
            if type:
                for address in self.addresses:
                    if getattr(address, type):
                        return address
        return default_address

    def contact_mechanism_get(self, types=None, usage=None):
        """
        Try to find a contact mechanism for the given types and usage, if no
        usage matches the first mechanism of the given types is returned.
        """
        default_mechanism = None
        if types:
            if isinstance(types, str):
                types = {types}
            mechanisms = [m for m in self.contact_mechanisms
                if m.type in types]
        else:
            mechanisms = self.contact_mechanisms
        if mechanisms:
            default_mechanism = mechanisms[0]
            if usage:
                for mechanism in mechanisms:
                    if getattr(mechanism, usage):
                        return mechanism
        return default_mechanism


class PartyLang(ModelSQL, ValueMixin):
    "Party Lang"
    __name__ = 'party.party.lang'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', select=True)
    lang = fields.Many2One('ir.lang', "Language")

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Party = pool.get('party.party')
        cursor = Transaction().connection.cursor()
        exist = backend.TableHandler.table_exist(cls._table)
        table = cls.__table__()
        party = Party.__table__()

        super(PartyLang, cls).__register__(module_name)

        if not exist:
            party_h = Party.__table_handler__(module_name)
            if party_h.column_exist('lang'):
                query = table.insert(
                    [table.party, table.lang],
                    party.select(party.id, party.lang))
                cursor.execute(*query)
                party_h.drop_column('lang')
            else:
                cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('lang')
        value_names.append('lang')
        migrate_property(
            'party.party', field_names, cls, value_names,
            parent='party', fields=fields)


class PartyCategory(ModelSQL):
    'Party - Category'
    __name__ = 'party.party-party.category'
    _table = 'party_category_rel'
    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
            required=True, select=True)
    category = fields.Many2One('party.category', 'Category',
        ondelete='CASCADE', required=True, select=True)


class Identifier(sequence_ordered(), ModelSQL, ModelView):
    'Party Identifier'
    __name__ = 'party.identifier'
    _rec_name = 'code'
    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
        required=True, select=True,
        help="The party identified by this record.")
    type = fields.Selection([
            (None, ''),
            ('ad_nrt', "Andorra Tax Number"),
            ('al_nipt', "Albanian VAT Number"),
            ('ar_cuit', "Argentinian Tax Number"),
            ('at_businessid', "Austrian Company Register"),
            ('at_tin', "Austrian Tax Identification"),
            ('au_abn', "Australian Business Number"),
            ('au_acn', "Australian Company Number"),
            ('au_tfn', "Australian Tax File Number"),
            ('be_vat', "Belgian Enterprise Number"),
            ('bg_egn', "Bulgarian Personal Identity Codes"),
            ('bg_pnf', "Bulgarian Number of a Foreigner"),
            ('bg_vat', "Bulgarian VAT Number"),
            ('br_cnpj', "Brazillian Company Identifier"),
            ('br_cpf', "Brazillian National Identifier"),
            ('ca_bn', "Canadian Business Number"),
            ('ca_sin', "Canadian Social Insurance Number"),
            ('ch_ssn', "Swiss Social Security Number"),
            ('ch_uid', "Swiss Business Identifier"),
            ('ch_vat', "Swiss VAT Number"),
            ('cl_rut', "Chilean National Tax Number"),
            ('cn_rit', "Chinese Resident Identity Card Number"),
            ('co_nit', "Colombian Identity Code"),
            ('co_rut', "Colombian Business Tax Number"),
            ('cr_cpf', "Costa Rica Physical Person ID Number"),
            ('cr_cr', "Costa Rica Foreigners ID Number"),
            ('cu_ni', "Cuban Identity Card Number"),
            ('cy_vat', "Cypriot VAT Number"),
            ('cz_dic', "Czech VAT Number"),
            ('cz_rc', "Czech National Identifier"),
            ('de_handelsregisternummer', "German Company Register Number"),
            ('de_idnr', "German Personal Tax Number"),
            ('de_stnr', "German Tax Number"),
            ('de_vat', "German VAT Number"),
            ('dk_cpr', "Danish Citizen Number"),
            ('dk_cvr', "Danish VAT Number"),
            ('do_cedula', "Dominican Republic National Identification Number"),
            ('do_rnc', "Dominican Republic Tax"),
            ('ec_ci', "Ecuadorian Personal Identity Code"),
            ('ec_ruc', "Ecuadorian Tax Identification"),
            ('ee_ik', "Estonian Personcal ID number"),
            ('ee_kmkr', "Estonian VAT Number"),
            ('ee_registrikood', "Estonian Organisation Registration Code"),
            ('es_cif', "Spanish Company Tax"),
            ('es_dni', "Spanish Personal Identity Codes"),
            ('es_nie', "Spanish Foreigner Number"),
            ('es_nif', "Spanish VAT Number"),
            ('eu_at_02', "SEPA Identifier of the Creditor (AT-02)"),
            ('eu_vat', "European VAT Number"),
            ('fi_alv', "Finnish VAT Number"),
            ('fi_associationid', "Finnish Association Identifier"),
            ('fi_hetu', "Finnish Personal Identity Code"),
            ('fi_veronumero', "Finnish individual tax number"),
            ('fi_ytunnus', "Finnish Business Identifier"),
            ('fr_nif', "French Tax Identification Number"),
            ('fr_nir', "French Personal Identification Number"),
            # TODO: remove from party_siren
            # ('fr_siren', "French Company Identification Number"),
            ('fr_tva', "French VAT Number"),
            ('gb_nhs',
                "United Kingdom National Health Service Patient Identifier"),
            ('gb_upn', "English Unique Pupil Number"),
            ('gb_vat', "United Kingdom (and Isle of Man) VAT Number"),
            ('gr_vat', "Greek VAT Number"),
            ('gt_nit', "Guatemala Tax Number"),
            ('hr_oib', "Croatian Identification Number"),
            ('hu_anum', "Hungarian VAT Number"),
            ('ie_pps', "Irish Personal Number"),
            ('ie_vat', "Irish VAT Number"),
            ('in_aadhaar', "Indian Digital Resident Personal Identity Number"),
            ('in_pan', "Indian Income Tax Identifier"),
            ('is_kennitala',
                "Icelandic Personal and Organisation Identity Code"),
            ('is_vsk', "Icelandic VAT Number"),
            ('it_codicefiscale', "Italian Tax Code for Individuals"),
            ('it_iva', "Italian VAT Number"),
            ('jp_cn', "Japanese Corporate Number"),
            ('lt_pvm', "Lithuanian VAT Number"),
            ('lu_tva', "Luxembourgian VAT Number"),
            ('lv_pvn', "Latvian VAT Number"),
            ('mc_tva', "Monacan VAT Number"),
            ('md_idno', "Moldavian Company Identification Number"),
            ('mt_vat', "Maltese VAT Number"),
            ('mu_nid', "Mauritian National Identifier"),
            ('mx_rfc', "Mexican Tax Number"),
            ('my_nric',
                "Malaysian National Registration Identity Card Number"),
            ('nl_brin', "Dutch School Identification Number"),
            ('nl_bsn', "Dutch Citizen Identification Number"),
            ('nl_btw', "Dutch VAT Number"),
            ('nl_onderwijsnummer', "Dutch student identification number"),
            ('no_mva', "Norwegian VAT Number"),
            ('no_orgnr', "Norwegian Organisation Number"),
            ('nz_ird', "New Zealand Inland Revenue Department Number"),
            ('pe_cui', "Peruvian Identity Number"),
            ('pe_ruc', "Peruvian Company Tax Number"),
            ('pl_nip', "Polish VAT Number"),
            ('pl_pesel', "Polish National Identification Number"),
            ('pl_regon', "Polish Register of Economic Units"),
            ('pt_nif', "Portuguese VAT Number"),
            ('py_ruc', "Paraguay Tax Number"),
            ('ro_cf', "Romanian VAT Number"),
            ('ro_cnp', "Romanian Numerical Personal Code"),
            ('rs_pib', "Serbian Tax Identification"),
            ('ru_inn', "Russian Tax identifier"),
            ('se_orgnr', "Swedish Company Number"),
            ('se_vat', "Swedish VAT Number"),
            ('si_ddv', "Slovenian VAT Number"),
            ('sk_dph', "Slovak VAT Number"),
            ('sk_rc', "Slovak Birth Number"),
            ('sm_coe', "San Marino National Tax Number"),
            ('tr_tckimlik', "Turkish Personal Identification Number"),
            ('us_atin', "U.S. Adoption Taxpayer Identification Number"),
            ('us_ein', "U.S. Employer Identification Number"),
            ('us_itin', "U.S. Individual Taxpayer Identification Number"),
            ('us_ptin', "U.S. Preparer Tax Identification Number"),
            ('us_ssn', "U.S. Social Security Number"),
            ('us_tin', "U.S. Taxpayer Identification Number"),
            ('uy_ruc', "Uruguay Tax Number"),
            ('ve_rif', "Venezuelan VAT Number"),
            ('za_idnr', "South African Identity Document Number"),
            ('za_tin', "South African Tax Identification Number"),
            ], 'Type')
    type_string = type.translated('type')
    code = fields.Char('Code', required=True)

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Party = pool.get('party.party')
        cursor = Transaction().connection.cursor()
        party = Party.__table__()

        super().__register__(module_name)

        party_h = Party.__table_handler__(module_name)
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
                for type in Party.tax_identifier_types():
                    module = get_cc_module(*type.split('_', 1))
                    if module.is_valid(code):
                        break
                else:
                    type = None
                identifiers.append(
                    cls(party=party_id, code=code, type=type))
            cls.save(identifiers)
            party_h.drop_column('vat_number')
            party_h.drop_column('vat_country')

    @fields.depends('type', 'code')
    def on_change_with_code(self):
        if self.type and '_' in self.type:
            module = get_cc_module(*self.type.split('_', 1))
            if module:
                try:
                    return module.compact(self.code)
                except stdnum.exceptions.ValidationError:
                    pass
        return self.code

    def pre_validate(self):
        super().pre_validate()
        self.check_code()

    @fields.depends('type', 'party', 'code')
    def check_code(self):
        if self.type and '_' in self.type:
            module = get_cc_module(*self.type.split('_', 1))
            if module:
                if not module.is_valid(self.code):
                    if self.party and self.party.id > 0:
                        party = self.party.rec_name
                    else:
                        party = ''
                    raise InvalidIdentifierCode(
                        gettext('party.msg_invalid_code',
                            type=self.type_string,
                            code=self.code,
                            party=party))


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

    def transition_check(self):
        parties_succeed = []
        parties_failed = []
        for party in self.records:
            for identifier in party.identifiers:
                if identifier.type != 'eu_vat':
                    continue
                eu_vat = get_cc_module('eu', 'vat')
                try:
                    if not eu_vat.check_vies(identifier.code)['valid']:
                        parties_failed.append(party.id)
                    else:
                        parties_succeed.append(party.id)
                except Exception as e:
                    if hasattr(e, 'faultstring') \
                            and hasattr(e.faultstring, 'find'):
                        if e.faultstring.find('INVALID_INPUT'):
                            parties_failed.append(party.id)
                            continue
                        if e.faultstring.find('SERVICE_UNAVAILABLE') \
                                or e.faultstring.find('MS_UNAVAILABLE') \
                                or e.faultstring.find('TIMEOUT') \
                                or e.faultstring.find('SERVER_BUSY'):
                            raise VIESUnavailable(
                                gettext('party.msg_vies_unavailable')) from e
                    raise
        self.result.parties_succeed = parties_succeed
        self.result.parties_failed = parties_failed
        return 'result'

    def default_result(self, fields):
        return {
            'parties_succeed': [p.id for p in self.result.parties_succeed],
            'parties_failed': [p.id for p in self.result.parties_failed],
            }


class Replace(Wizard):
    "Replace Party"
    __name__ = 'party.replace'
    start_state = 'ask'
    ask = StateView('party.replace.ask', 'party.replace_ask_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Replace", 'replace', 'tryton-launch', default=True),
            ])
    replace = StateTransition()

    def check_similarity(self):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        source = self.ask.source
        destination = self.ask.destination
        if source.name != destination.name:
            key = 'party.replace name %s %s' % (source.id, destination.id)
            if Warning.check(key):
                raise SimilarityWarning(
                    key,
                    gettext('party.msg_different_name',
                        source_name=source.name,
                        destination_name=destination.name))
        source_code = (source.tax_identifier.code
            if source.tax_identifier else '')
        destination_code = (destination.tax_identifier.code
            if destination.tax_identifier else '')
        if source_code != destination_code:
            key = 'party.replace tax_identifier %s %s' % (
                source.id, destination.id)
            if Warning.check(key):
                raise SimilarityWarning(
                    key,
                    gettext('party.msg_different_tax_identifier',
                        source_code=source_code,
                        destination_code=destination_code))

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


class ReplaceAsk(ModelView):
    "Replace Party"
    __name__ = 'party.replace.ask'
    source = fields.Many2One('party.party', "Source", required=True,
        help="The party to be replaced.")
    destination = fields.Many2One('party.party', "Destination", required=True,
        domain=[
            ('id', '!=', Eval('source', -1)),
            ],
        depends=['source'],
        help="The party that replaces.")

    @classmethod
    def default_source(cls):
        context = Transaction().context
        if context.get('active_model') == 'party.party':
            return context.get('active_id')

    @fields.depends('source')
    def on_change_source(self):
        if self.source and self.source.replaced_by:
            self.destination = self.source.replaced_by


class Erase(Wizard):
    "Erase Party"
    __name__ = 'party.erase'
    start_state = 'ask'
    ask = StateView('party.erase.ask', 'party.erase_ask_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Erase", 'erase', 'tryton-clear', default=True),
            ])
    erase = StateTransition()

    def transition_erase(self):
        pool = Pool()
        Party = pool.get('party.party')
        cursor = Transaction().connection.cursor()

        def convert_from(table, tables):
            right, condition = tables[None]
            if table:
                table = table.join(right, condition=condition)
            else:
                table = right
            for k, sub_tables in tables.items():
                if k is None:
                    continue
                table = convert_from(table, sub_tables)
            return table

        resources = self.get_resources()
        parties = replacing = [self.ask.party]
        with Transaction().set_context(active_test=False):
            while replacing:
                replacing = Party.search([
                        ('replaced_by', 'in', list(map(int, replacing))),
                        ])
                parties += replacing
        for party in parties:
            self.check_erase(party)
            to_erase = self.to_erase(party.id)
            for Model, domain, resource, columns, values in to_erase:
                assert issubclass(Model, ModelSQL)
                assert len(columns) == len(values)
                if 'active' in Model._fields:
                    records = Model.search(domain)
                    Model.write(records, {'active': False})

                tables, where = Model.search_domain(domain, active_test=False)
                from_ = convert_from(None, tables)
                table, _ = tables[None]
                query = from_.select(table.id, where=where)

                if columns:
                    model_tables = [Model.__table__()]
                    if Model._history:
                        model_tables.append(Model.__table_history__())
                    for table in model_tables:
                        sql_columns, sql_values = [], []
                        for column, value in zip(columns, values):
                            column = Column(table, column)
                            sql_columns.append(column)
                            sql_values.append(
                                value(column) if callable(value) else value)
                        cursor.execute(*table.update(
                                sql_columns, sql_values,
                                where=table.id.in_(query)))
                if resource:
                    for Resource in resources:
                        model_tables = [Resource.__table__()]
                        if Resource._history:
                            model_tables.append(Resource.__table_history__())
                        for table in model_tables:
                            cursor.execute(*table.delete(
                                    where=table.resource.like(
                                        Model.__name__ + ',%')
                                    & Model.id.sql_cast(
                                        Substring(table.resource,
                                            Position(',', table.resource)
                                            + Literal(1))).in_(query)))
        return 'end'

    def check_erase(self, party):
        if party.active:
            raise EraseError(gettext('party.msg_erase_active_party',
                    party=party.rec_name))

    def to_erase(self, party_id):
        pool = Pool()
        Party = pool.get('party.party')
        Identifier = pool.get('party.identifier')
        Address = pool.get('party.address')
        ContactMechanism = pool.get('party.contact_mechanism')
        return [
            (Party, [('id', '=', party_id)], True,
                ['name'],
                [None]),
            (Identifier, [('party', '=', party_id)], True,
                ['type', 'code'],
                [None, '****']),
            (Address, [('party', '=', party_id)], True,
                ['name', 'street', 'zip', 'city', 'country', 'subdivision'],
                [None, None, None, None, None, None]),
            (ContactMechanism, [('party', '=', party_id)], True,
                ['value', 'name', 'comment'],
                [None, None, None]),
            ]

    @classmethod
    def get_resources(cls):
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        Note = pool.get('ir.note')
        return [Attachment, Note]


class EraseAsk(ModelView):
    "Erase Party"
    __name__ = 'party.erase.ask'
    party = fields.Many2One('party.party', "Party", required=True,
        help="The party to be erased.")

    @classmethod
    def default_party(cls):
        context = Transaction().context
        if context.get('active_model') == 'party.party':
            return context.get('active_id')
