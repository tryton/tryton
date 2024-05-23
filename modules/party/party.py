# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import logging

import stdnum.exceptions
from sql import Column, Literal
from sql.aggregate import Min
from sql.functions import CharLength
from stdnum import get_cc_module
from stdnum.eu.vat import MEMBER_STATES as EU_MEMBER_STATES

from trytond import backend
from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, Index, ModelSQL, ModelView, MultiValueMixin, Unique,
    ValueMixin, convert_from, fields, sequence_ordered)
from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.pyson import Bool, Eval
from trytond.tools import is_full_text, lstrip_wildcard
from trytond.transaction import Transaction, inactive_records
from trytond.wizard import Button, StateTransition, StateView, Wizard

from .contact_mechanism import _PHONE_TYPES, _ContactMechanismMixin
from .exceptions import (
    EraseError, InvalidIdentifierCode, SimilarityWarning, VIESUnavailable)

logger = logging.getLogger(__name__)


class Party(
        DeactivableMixin, _ContactMechanismMixin, ModelSQL, ModelView,
        MultiValueMixin):
    "Party"
    __name__ = 'party.party'

    _contact_mechanism_states = {
        'readonly': Eval('id', -1) >= 0,
        }

    name = fields.Char(
        "Name", strip=False,
        help="The main identifier of the party.")
    code = fields.Char(
        "Code", required=True,
        states={
            'readonly': Eval('code_readonly', True),
            },
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
    phone = fields.Function(
        fields.Char("Phone", states=_contact_mechanism_states),
        'get_contact_mechanism', setter='set_contact_mechanism')
    mobile = fields.Function(
        fields.Char("Mobile", states=_contact_mechanism_states),
        'get_contact_mechanism', setter='set_contact_mechanism')
    fax = fields.Function(
        fields.Char("Fax", states=_contact_mechanism_states),
        'get_contact_mechanism', setter='set_contact_mechanism')
    email = fields.Function(
        fields.Char("E-Mail", states=_contact_mechanism_states),
        'get_contact_mechanism', setter='set_contact_mechanism')
    website = fields.Function(
        fields.Char("Website", states=_contact_mechanism_states),
        'get_contact_mechanism', setter='set_contact_mechanism')
    distance = fields.Function(fields.Integer('Distance'), 'get_distance')

    del _contact_mechanism_states

    @classmethod
    def __setup__(cls):
        cls.code.search_unaccented = False
        super(Party, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('code_uniq', Unique(t, t.code), 'party.msg_party_code_unique')
            ]
        cls._sql_indexes.update({
                Index(t, (t.code, Index.Equality())),
                Index(t, (t.code, Index.Similarity())),
                })
        cls._order.insert(0, ('distance', 'ASC NULLS LAST'))
        cls._order.insert(1, ('name', 'ASC'))
        cls.active.states.update({
                'readonly': Bool(Eval('replaced_by')),
                })

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

    def _get_identifier(self, name, types):
        for identifier in self.identifiers:
            if identifier.type in types:
                return identifier.id

    @classmethod
    def _search_identifier(cls, name, clause, types):
        _, operator, value = clause
        nested = clause[0][len(name) + 1:]
        domain = [
            ('identifiers', 'where', [
                    (nested or 'rec_name', operator, value),
                    ('type', 'in', types),
                    ]),
            ]
        # Add party without identifier
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

    @classmethod
    def tax_identifier_types(cls):
        return TAX_IDENTIFIER_TYPES

    def get_tax_identifier(self, name):
        types = self.tax_identifier_types()
        return self._get_identifier(name, types)

    @classmethod
    def search_tax_identifier(cls, name, clause):
        types = cls.tax_identifier_types()
        return cls._search_identifier(name, clause, types)

    def get_full_name(self, name):
        return self.name

    def get_contact_mechanism(self, name):
        usage = Transaction().context.get('party_contact_mechanism_usage')
        mechanism = self.contact_mechanism_get(name, usage)
        return mechanism.value if mechanism else ''

    @classmethod
    def set_contact_mechanism(cls, parties, name, value):
        pool = Pool()
        ContactMechanism = pool.get('party.contact_mechanism')
        usage = Transaction().context.get('party_contact_mechanism_usage')
        contact_mechanisms = []
        for party in parties:
            if getattr(party, name):
                type_string = cls.fields_get([name])[name]['string']
                raise AccessError(gettext(
                        'party.msg_party_set_contact_mechanism',
                        party=party.rec_name,
                        field=type_string))
            if value:
                contact_mechanism = None
                if usage:
                    for contact_mechanism in party.contact_mechanisms:
                        if (contact_mechanism.type == name
                                and contact_mechanism.value == value):
                            break
                    else:
                        contact_mechanism = None
                if not contact_mechanism:
                    contact_mechanism = ContactMechanism(
                        party=party,
                        type=name,
                        value=value)
                if usage:
                    setattr(contact_mechanism, usage, True)
                contact_mechanisms.append(contact_mechanism)
        ContactMechanism.save(contact_mechanisms)

    @classmethod
    def _distance_query(cls, usages=None, party=None, depth=None):
        context = Transaction().context
        if party is None:
            party = context.get('related_party')

        if not party:
            return

        table = cls.__table__()
        return table.select(
            table.id.as_('to'),
            Literal(0).as_('distance'),
            where=(table.id == party))

    @classmethod
    def get_distance(cls, parties, name):
        distances = {p.id: None for p in parties}
        query = cls._distance_query()
        if query:
            cursor = Transaction().connection.cursor()
            cursor.execute(*query.select(
                    query.to.as_('to'),
                    Min(query.distance).as_('distance'),
                    group_by=[query.to]))
            distances.update(cursor)
        return distances

    @classmethod
    def order_distance(cls, tables):
        party, _ = tables[None]
        key = 'distance'
        if key not in tables:
            query = cls._distance_query()
            if not query:
                return []
            query = query.select(
                    query.to.as_('to'),
                    Min(query.distance).as_('distance'),
                    group_by=[query.to])
            join = party.join(query, type_='LEFT',
                condition=query.to == party.id)
            tables[key] = {
                None: (join.right, join.condition),
                }
        else:
            query, _ = tables[key][None]
        return [query.distance]

    @classmethod
    def index_set_field(cls, name):
        index = super().index_set_field(name)
        if name in _PHONE_TYPES:
            # Phone validation may need the address country
            index = cls.index_set_field('addresses') + 1
        return index

    @classmethod
    def _new_code(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('party.configuration')
        config = Configuration(1)
        sequence = config.get_multivalue('party_sequence', **pattern)
        if sequence:
            return sequence.get()

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
        _, operator, operand, *extra = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        code_value = operand
        if operator.endswith('like') and is_full_text(operand):
            code_value = lstrip_wildcard(operand)
        return [bool_op,
            ('code', operator, code_value, *extra),
            ('identifiers.code', operator, code_value, *extra),
            ('name', operator, operand, *extra),
            ('contact_mechanisms.rec_name', operator, operand, *extra),
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

    @classmethod
    def autocomplete(cls, text, domain=None, limit=None, order=None):
        pool = Pool()
        Configuration = pool.get('party.configuration')
        configuration = Configuration(1)

        result = super().autocomplete(
            text, domain=domain, limit=limit, order=order)

        identifier_types = dict(configuration.get_identifier_types())

        def add(type, code):
            result.append({
                    'id': None,
                    'name': code,
                    'defaults': {
                        'identifiers': [{
                                'type': type,
                                'code': code,
                                }],
                        },
                    })

        eu_vat = get_cc_module('eu', 'vat')
        if 'eu_vat' in identifier_types and eu_vat.is_valid(text):
            code = eu_vat.compact(text)
            add('eu_vat', code)
        else:
            for country in eu_vat.guess_country(text):
                if 'eu_vat' in identifier_types:
                    code = eu_vat.compact(country + text)
                    add('eu_vat', code)
                elif f'{country}_vat' in identifier_types:
                    vat = get_cc_module(country, 'vat')
                    code = vat.compact(text)
                    add(f'{country}_vat', code)
        return result

    @classmethod
    def default_get(cls, fields_names, with_rec_name=True):
        pool = Pool()
        Country = pool.get('country.country')

        values = super().default_get(fields_names, with_rec_name=with_rec_name)
        eu_vat = get_cc_module('eu', 'vat')
        eu_types = {'eu_vat'} | {f'{m}_vat' for m in EU_MEMBER_STATES}
        for identifier in values.get('identifiers') or []:
            if identifier.get('type') in eu_types and identifier.get('code'):
                code = identifier['code']
                if identifier['type'] != 'eu_vat':
                    code = identifier['type'][2:] + code
                try:
                    result = eu_vat.check_vies(code)
                except Exception:
                    logger.debug(
                        f"Fail to check {identifier['code']}", exc_info=True)
                    continue
                if result['valid']:
                    values['name'] = result['name']
                    for address in values.get('addresses') or []:
                        if not address:
                            break
                    else:
                        address = {}
                        values.setdefault('addresses', []).insert(0, address)
                    address['street'] = result['address']
                    country_code = code[:2]
                    countries = Country.search([
                            ('code', 'ilike', country_code),
                            ], limit=1)
                    if countries:
                        country, = countries
                        address['country'] = country.id
                        if with_rec_name:
                            address.setdefault('country.', {})['rec_name'] = (
                                country.rec_name)
                    break
        return values


class PartyLang(ModelSQL, ValueMixin):
    "Party Lang"
    __name__ = 'party.party.lang'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE')
    lang = fields.Many2One('ir.lang', "Language")


class PartyCategory(ModelSQL):
    'Party - Category'
    __name__ = 'party.party-party.category'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', required=True)
    category = fields.Many2One(
        'party.category', "Category", ondelete='CASCADE', required=True)

    @classmethod
    def __register__(cls, module):
        # Migration from 7.0: rename to standard name
        backend.TableHandler.table_rename('party_category_rel', cls._table)
        super().__register__(module)


IDENTIFIER_VAT = [
    'ad_nrt',
    'al_nipt',
    'ar_cuit',
    'at_uid',
    'au_abn',
    'br_cnpj',
    'by_unp',
    'ca_bn',
    'cl_rut',
    'cn_uscc',
    'co_nit',
    'cr_cpj',
    'cz_dic',
    'dk_cvr',
    'do_rnc',
    'dz_nif',
    'ec_ruc',
    'ee_kmkr',
    'eg_tn',
    'es_nif',
    'fi_alv',
    'fo_vn',
    'fr_tva',
    'gh_tin',
    'gn_nifp',
    'gt_nit',
    'hr_oib',
    'hu_anum',
    'id_npwp',
    'il_hp',
    'in_gstin',
    'is_vsk',
    'it_iva',
    'jp_cn',
    'ke_pin',
    'kr_brn',
    'lt_pvm',
    'lu_tva',
    'lv_pvn',
    'ma_ice',
    'mc_tva',
    'me_pib',
    'mk_edb',
    'mx_rfc',
    'nl_btw',
    'no_mva',
    'nz_ird',
    'pe_ruc',
    'pl_nip',
    'pt_nif',
    'py_ruc',
    'ro_cf',
    'rs_pib',
    'ru_inn',
    'sg_uen',
    'si_ddv',
    'sk_dph',
    'sm_coe',
    'sv_nit',
    'tn_mf',
    'tr_vkn',
    'tw_ubn',
    'uy_rut',
    've_rif',
    'vn_mst',
    ]


def replace_vat(code):
    if code in IDENTIFIER_VAT:
        code = code.split('_', 1)[0] + '_vat'
    return code


IDENTIFIER_TYPES = [
    ('ad_nrt', "Andorra Tax Number"),
    ('al_nipt', "Albanian VAT Number"),
    ('ar_cuit', "Argentinian Tax Number"),
    ('ar_dni', "Argentinian National Identity Number"),
    ('at_businessid', "Austrian Company Register"),
    ('at_tin', "Austrian Tax Identification"),
    ('at_uid', "Austrian Umsatzsteuer-Identifikationsnummer"),
    ('at_vnr', "Austrian Social Security Number"),
    ('au_abn', "Australian Business Number"),
    ('au_acn', "Australian Company Number"),
    ('au_tfn', "Australian Tax File Number"),
    ('be_bis', "Belgian BIS Number"),
    ('be_nn', "Belgian National Number"),
    ('be_vat', "Belgian Enterprise Number"),
    ('bg_egn', "Bulgarian Personal Identity Codes"),
    ('bg_pnf', "Bulgarian Number of a Foreigner"),
    ('bg_vat', "Bulgarian VAT Number"),
    ('br_cnpj', "Brazillian Company Identifier"),
    ('br_cpf', "Brazillian National Identifier"),
    ('by_unp', "Belarus VAT Number"),
    ('ca_bn', "Canadian Business Number"),
    ('ca_sin', "Canadian Social Insurance Number"),
    ('ch_ssn', "Swiss Social Security Number"),
    ('ch_uid', "Swiss Business Identifier"),
    ('ch_vat', "Swiss VAT Number"),
    ('cl_rut', "Chilean National Tax Number"),
    ('cn_ric', "Chinese Resident Identity Card Number"),
    ('cn_uscc', "Chinese Unified Social Credit Code"),
    ('co_nit', "Colombian Identity Code"),
    ('co_rut', "Colombian Business Tax Number"),
    ('cr_cpf', "Costa Rica Physical Person ID Number"),
    ('cr_cpj', "Costa Rica Tax Number"),
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
    ('dz_nif', "Algerian Tax Number"),
    ('ec_ci', "Ecuadorian Personal Identity Code"),
    ('ec_ruc', "Ecuadorian Tax Identification"),
    ('ee_ik', "Estonian Personal ID Number"),
    ('ee_kmkr', "Estonian VAT Number"),
    ('ee_registrikood', "Estonian Organisation Registration Code"),
    ('eg_tn', "Egyptian Tax Registration Number"),
    ('es_cif', "Spanish Company Tax"),
    ('es_dni', "Spanish Personal Identity Codes"),
    ('es_nie', "Spanish Foreigner Number"),
    ('es_nif', "Spanish VAT Number"),
    ('eu_at_02', "SEPA Identifier of the Creditor (AT-02)"),
    ('eu_oss', "European VAT on e-Commerce - One Stop Shop"),
    ('eu_vat', "European VAT Number"),
    ('fi_alv', "Finnish VAT Number"),
    ('fi_associationid', "Finnish Association Identifier"),
    ('fi_hetu', "Finnish Personal Identity Code"),
    ('fi_veronumero', "Finnish Individual Tax Number"),
    ('fi_ytunnus', "Finnish Business Identifier"),
    ('fo_vn', "Faroese Tax Number"),
    ('fr_nif', "French Tax Identification Number"),
    ('fr_nir', "French Personal Identification Number"),
    ('fr_siren', "French Company Identification Number"),
    ('fr_siret', "French Company Establishment Identification Number"),
    ('fr_tva', "French VAT Number"),
    ('gb_nhs',
        "United Kingdom National Health Service Patient Identifier"),
    ('gb_upn', "English Unique Pupil Number"),
    ('gb_vat', "United Kingdom (and Isle of Man) VAT Number"),
    ('gh_tin', "Ghanaian Taxpayer Identification Number"),
    ('gn_nifp', "Guinean Tax Number"),
    ('gr_amka', "Greek Social Security Number"),
    ('gr_vat', "Greek VAT Number"),
    ('gt_nit', "Guatemala Tax Number"),
    ('hr_oib', "Croatian Identification Number"),
    ('hu_anum', "Hungarian VAT Number"),
    ('id_npwp', "Indonesian VAT Number"),
    ('ie_pps', "Irish Personal Number"),
    ('ie_vat', "Irish VAT Number"),
    ('il_hp', "Israeli Company Number"),
    ('il_idnr', "Israeli Identity Number"),
    ('in_aadhaar', "Indian Digital Resident Personal Identity Number"),
    ('in_epic', "Indian Voter ID"),
    ('in_gstin', "Indian VAT number"),
    ('in_pan', "Indian Income Tax Identifier"),
    ('is_kennitala',
        "Icelandic Personal and Organisation Identity Code"),
    ('is_vsk', "Icelandic VAT Number"),
    ('it_codicefiscale', "Italian Tax Code for Individuals"),
    ('it_iva', "Italian VAT Number"),
    ('jp_cn', "Japanese Corporate Number"),
    ('kr_brn', "South Korea Business Registration Number"),
    ('kr_krn', "South Korean Resident Registration Number"),
    ('lt_asmens', "Lithuanian Personal Number"),
    ('lt_pvm', "Lithuanian VAT Number"),
    ('lu_tva', "Luxembourgian VAT Number"),
    ('lv_pvn', "Latvian VAT Number"),
    ('ma_ice', "Moroccan Tax Number"),
    ('mc_tva', "Monacan VAT Number"),
    ('md_idno', "Moldavian Company Identification Number"),
    ('mk_edb', "Macedonian Tax Number"),
    ('mt_vat', "Maltese VAT Number"),
    ('mu_nid', "Mauritian National Identifier"),
    ('mx_rfc', "Mexican Tax Number"),
    ('my_nric',
        "Malaysian National Registration Identity Card Number"),
    ('nl_brin', "Dutch School Identification Number"),
    ('nl_bsn', "Dutch Citizen Identification Number"),
    ('nl_btw', "Dutch VAT Number"),
    ('nl_onderwijsnummer', "Dutch Student Identification Number"),
    ('no_fodselsnummer',
        "Norwegian Birth Number, the National Identity Number"),
    ('no_mva', "Norwegian VAT Number"),
    ('no_orgnr', "Norwegian Organisation Number"),
    ('nz_ird', "New Zealand Inland Revenue Department Number"),
    ('pe_cui', "Peruvian Identity Number"),
    ('pe_ruc', "Peruvian Company Tax Number"),
    ('pk_cnic', "Pakistani Computerised National Identity Card Number"),
    ('pl_nip', "Polish VAT Number"),
    ('pl_pesel', "Polish National Identification Number"),
    ('pl_regon', "Polish Register of Economic Units"),
    ('pt_cc', "Portuguese Identity Number"),
    ('pt_nif', "Portuguese VAT Number"),
    ('py_ruc', "Paraguay Tax Number"),
    ('ro_cf', "Romanian VAT Number"),
    ('ro_cnp', "Romanian Numerical Personal Code"),
    ('ro_onrc', "Romanian ONRC Number"),
    ('rs_pib', "Serbian Tax Identification"),
    ('ru_inn', "Russian Tax identifier"),
    ('se_orgnr', "Swedish Company Number"),
    ('se_personnummer', "Swedish Personal Number"),
    ('se_vat', "Swedish VAT Number"),
    ('si_businessid', "Slovenian Corporate Registration Number"),
    ('si_ddv', "Slovenian VAT Number"),
    ('si_emso', "Slovenian Unique Master Citizen Number"),
    ('sk_dph', "Slovak VAT Number"),
    ('sk_rc', "Slovak Birth Number"),
    ('sm_coe', "San Marino National Tax Number"),
    ('th_moa', "Thai Memorandum of Association Number"),
    ('th_pin', "Thai Personal Identification Number"),
    ('th_tin', "Thai Taxpayer Identification Number"),
    ('tn_mf', "Tunisian Tax Number"),
    ('tr_tckimlik', "Turkish Personal Identification Number"),
    ('ua_edrpou', "Ukrainian Identifier for Enterprises and Organizations"),
    ('ua_rntrc', "Ukrainian Individual Taxpayer Registration Number"),
    ('us_atin', "U.S. Adoption Taxpayer Identification Number"),
    ('us_ein', "U.S. Employer Identification Number"),
    ('us_itin', "U.S. Individual Taxpayer Identification Number"),
    ('us_ptin', "U.S. Preparer Tax Identification Number"),
    ('us_ssn', "U.S. Social Security Number"),
    ('us_tin', "U.S. Taxpayer Identification Number"),
    ('uy_ruc', "Uruguay Tax Number"),
    ('ve_rif', "Venezuelan VAT Number"),
    ('vn_mst', "Vietnam Tax Number"),
    ('za_idnr', "South African Identity Document Number"),
    ('za_tin', "South African Tax Identification Number"),
    ]

IDENTIFIER_TYPES = list(map(
        lambda x: (replace_vat(x[0]), x[1]),
        IDENTIFIER_TYPES))

TAX_IDENTIFIER_TYPES = [
    'ad_nrt',
    'al_nipt',
    'ar_cuit',
    'at_uid',
    'au_abn',
    'au_acn',
    'be_vat',
    'bg_vat',
    'by_unp',
    'ch_vat',
    'cl_rut',
    'cn_uscc',
    'co_rut',
    'cr_cpj',
    'cz_dic',
    'de_vat',
    'dk_cvr',
    'do_rnc',
    'dz_nif',
    'ec_ruc',
    'ee_kmkr',
    'eg_tn',
    'es_nif',
    'eu_vat',
    'fi_alv',
    'fo_vn',
    'fr_tva',
    'gb_vat',
    'gh_tin',
    'gn_nifp',
    'gr_vat',
    'gt_nit',
    'hu_anum',
    'id_npwp',
    'ie_vat',
    'il_hp',
    'in_gstin',
    'is_vsk',
    'it_iva',
    'jp_cn',
    'kr_brn',
    'lt_pvm',
    'lu_tva',
    'lv_pvn',
    'ma_ice',
    'mc_tva',
    'md_idno',
    'mk_edb',
    'mt_vat',
    'mx_rfc',
    'nl_btw',
    'no_mva',
    'nz_ird',
    'pe_ruc',
    'pl_nip',
    'pt_nif',
    'py_ruc',
    'ro_cf',
    'rs_pib',
    'ru_inn',
    'se_vat',
    'si_ddv',
    'sk_dph',
    'sm_coe',
    'th_tin',
    'tn_mf',
    'ua_edrpou',
    'ua_rntrc',
    'us_atin',
    'us_ein',
    'us_itin',
    'us_ptin',
    'us_ssn',
    'us_tin',
    'uy_ruc',
    've_rif',
    'vn_mst',
    'za_tin',
    ]

TAX_IDENTIFIER_TYPES = list(map(replace_vat, TAX_IDENTIFIER_TYPES))


class Identifier(sequence_ordered(), DeactivableMixin, ModelSQL, ModelView):
    'Party Identifier'
    __name__ = 'party.identifier'
    _rec_name = 'code'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', required=True,
        help="The party identified by this record.")
    address = fields.Many2One(
        'party.address', "Address", ondelete='CASCADE',
        states={
            'required': Eval('type_address', False),
            'invisible': ~Eval('type_address', True),
            },
        domain=[
            ('party', '=', Eval('party', -1)),
            ],
        help="The address identified by this record.")
    type = fields.Selection('get_types', 'Type')
    type_string = type.translated('type')
    type_address = fields.Function(
        fields.Boolean("Type of Address"), 'on_change_with_type_address')
    code = fields.Char('Code', required=True)

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table__()

        super().__register__(module_name)

        # Migration from 5.8: Rename cn_rit into cn_ric
        cursor.execute(*table.update([table.type], ['cn_ric'],
                where=(table.type == 'cn_rit')))

        # Migration from 6.8: Use vat alias
        for old in IDENTIFIER_VAT:
            new = replace_vat(old)
            cursor.execute(*table.update(
                    [table.type], [new],
                    where=table.type == old))

    @classmethod
    def get_types(cls):
        pool = Pool()
        Configuration = pool.get('party.configuration')
        configuration = Configuration(1)
        return [(None, '')] + configuration.get_identifier_types()

    @classmethod
    def _type_addresses(cls):
        return {'fr_siret'}

    @fields.depends('address', '_parent_address.party')
    def on_change_address(self):
        if self.address:
            self.party = self.address.party

    @fields.depends('type')
    def on_change_with_type_address(self, name=None):
        return self.type in self._type_addresses()

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

    @fields.depends(methods=['_notify_duplicate'])
    def on_change_notify(self):
        notifications = super().on_change_notify()
        notifications.extend(self._notify_duplicate())
        return notifications

    @fields.depends('code', methods=['on_change_with_code'])
    def _notify_duplicate(self):
        cls = self.__class__
        if self.code:
            code = self.on_change_with_code()
            others = cls.search([
                    ('id', '!=', self.id),
                    ('type', '!=', None),
                    ('code', '=', code),
                    ], limit=1)
            if others:
                other, = others
                yield ('warning', gettext(
                        'party.msg_party_identifier_duplicate',
                        party=other.party.rec_name,
                        type=other.type_string,
                        code=other.code))


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
                    for msg in e.args:
                        if msg == 'INVALID_INPUT':
                            parties_failed.append(party.id)
                            break
                        elif msg in {
                                'SERVICE_UNAVAILABLE',
                                'MS_UNAVAILABLE',
                                'MS_MAX_CONCURRENT_REQ',
                                'GLOBAL_MS_MAX_CONCURRENT_REQ',
                                'TIMEOUT',
                                'SERVER_BUSY',
                                }:
                            raise VIESUnavailable(
                                gettext('party.msg_vies_unavailable')) from e
                    else:
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
        Identifier = pool.get('party.identifier')
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
        Identifier.write(list(source.identifiers), {
                'active': False,
                })
        source.replaced_by = destination
        source.active = False
        source.save()

        cursor = transaction.connection.cursor()
        for model_name, field_name in self.fields_to_replace():
            Model = pool.get(model_name)
            field = getattr(Model, field_name)
            table = Model.__table__()
            column = Column(table, field_name)
            if field._type == 'reference':
                source_value = str(source)
                destination_value = str(destination)
            else:
                source_value = source.id
                destination_value = destination.id
            where = column == source_value

            if transaction.database.has_returning():
                returning = [table.id]
            else:
                cursor.execute(*table.select(table.id, where=where))
                ids = [x[0] for x in cursor]
                returning = None

            cursor.execute(*table.update(
                    [column],
                    [destination_value],
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
            ('party.identifier', 'party'),
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
        transaction = Transaction()
        cursor = transaction.connection.cursor()

        resources = self.get_resources()
        parties = replacing = [self.ask.party]
        with inactive_records():
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
                from_ = convert_from(None, tables, type_='INNER')
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
                        model_tables = [
                            (Resource.__table__(), Resource.resource)]
                        if Resource._history:
                            model_tables.append(
                                (Resource.__table_history__(),
                                    Resource.resource))
                        for (table, resource_field) in model_tables:
                            cursor.execute(*table.delete(
                                    where=table.resource.like(
                                        Model.__name__ + ',%')
                                    & resource_field.sql_id(
                                        table.resource, Model).in_(query)))
        transaction.counter += 1
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
                ['name', 'street', 'postal_code', 'city',
                    'country', 'subdivision'],
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
        Avatar = pool.get('ir.avatar')
        return [Attachment, Note, Avatar]


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
