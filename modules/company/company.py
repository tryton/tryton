# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
import io
import logging
from string import Template

try:
    import PIL
except ImportError:
    PIL = None

import trytond.config as config
from trytond.i18n import gettext
from trytond.model import (
    MatchMixin, ModelSQL, ModelView, Unique, fields, sequence_ordered)
from trytond.model.exceptions import SQLConstraintError
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, If
from trytond.report import Report
from trytond.tools import timezone as tz
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard

from .exceptions import LogoValidationError

SIZE_MAX = config.getint('company', 'logo_size_max', default=2048)
TIMEZONES = [(z, z) for z in tz.available_timezones()]
TIMEZONES += [(None, '')]

Transaction.cache_keys.update({'company', 'employee'})
logger = logging.getLogger(__name__)

_SUBSTITUTION_HELP = (
    "The following placeholders can be used:\n"
    "- ${name}\n"
    "- ${phone}\n"
    "- ${mobile}\n"
    "- ${fax}\n"
    "- ${email}\n"
    "- ${website}\n"
    "- ${address}\n"
    "- ${tax_identifier}\n"
    )


class Company(ModelSQL, ModelView):
    __name__ = 'company.company'
    party = fields.Many2One(
        'party.party', 'Party', required=True, ondelete='CASCADE',
        states={
            'readonly': Eval('id', -1) >= 0,
            })
    header = fields.Text(
        'Header',
        help="The text to display on report headers.\n" + _SUBSTITUTION_HELP)
    footer = fields.Text(
        'Footer',
        help="The text to display on report footers.\n" + _SUBSTITUTION_HELP)
    logo = fields.Binary("Logo", readonly=not PIL)
    logo_cache = fields.One2Many(
        'company.company.logo.cache', 'company', "Cache", readonly=True)
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        help="The main currency for the company.")
    timezone = fields.Selection(TIMEZONES, 'Timezone', translate=False,
        help="Used to compute the today date.")
    employees = fields.One2Many('company.employee', 'company', 'Employees',
        help="Add employees to the company.")
    tax_identifiers = fields.One2Many(
        'company.company.tax_identifier', 'company', "Tax Identifiers",
        help="Uses the first identifier that matches the criteria.\n"
        "If none match, uses the party's tax identifier.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('party_unique', Unique(t, t.party),
                'company.msg_company_party_unique'),
            ]

    @property
    def header_used(self):
        return Template(self.header or '').safe_substitute(self._substitutions)

    @property
    def footer_used(self):
        return Template(self.footer or '').safe_substitute(self._substitutions)

    @property
    def _substitutions(self):
        address = self.party.address_get()
        tax_identifier = self.party.tax_identifier
        return {
            'name': self.party.name,
            'phone': self.party.phone,
            'mobile': self.party.mobile,
            'fax': self.party.fax,
            'email': self.party.email,
            'website': self.party.website,
            'address': (
                ' '.join(address.full_address.splitlines())
                if address else ''),
            'tax_identifier': tax_identifier.code if tax_identifier else '',
            }

    def get_rec_name(self, name):
        return self.party.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('party.rec_name',) + tuple(clause[1:])]

    @classmethod
    def preprocess_values(cls, mode, values):
        values = super().preprocess_values(mode, values)
        if logo := values.get('logo'):
            values['logo'] = cls._logo_convert(logo)
        return values

    @classmethod
    def on_modification(cls, mode, companies, field_names=None):
        pool = Pool()
        Rule = pool.get('ir.rule')
        super().on_modification(mode, companies, field_names=field_names)
        if mode == 'write':
            if not field_names or 'logo' in field_names:
                cls._logo_clear_cache(companies)
            Rule._domain_get_cache.clear()

    @classmethod
    def _logo_convert(cls, image, **_params):
        if not PIL:
            return image
        data = io.BytesIO()
        try:
            img = PIL.Image.open(io.BytesIO(image))
        except PIL.UnidentifiedImageError as e:
            raise LogoValidationError(gettext(
                    'company.msg_company_logo_error'), str(e)) from e
        img.thumbnail((SIZE_MAX, SIZE_MAX))
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        img.save(data, format='png', optimize=True, dpi=(300, 300), **_params)
        return data.getvalue()

    def get_logo(self, width, height):
        "Return logo image with mime-type and size in pixel"
        if not self.logo:
            raise ValueError("No logo")
        width, height = round(width), round(height)
        if not all(0 < s <= SIZE_MAX for s in [width, height]):
            raise ValueError(f"Invalid size {width} × {height}")
        cached_sizes = set()
        for cache in self.logo_cache:
            cached_sizes.add((cache.width, cache.height))
            if ((cache.width == width and cache.height <= height)
                    or (cache.width <= width and cache.height == height)):
                return cache.image, 'image/png', cache.width, cache.height

        try:
            with Transaction().new_transaction():
                image, width, height = self._logo_resize(width, height)
                if (width, height) not in cached_sizes:
                    cache = self._logo_store_cache(image, width, height)
                    # Save cache only if record is already committed
                    if self.__class__.search([('id', '=', self.id)]):
                        cache.save()
        except SQLConstraintError:
            logger.info("caching company logo failed", exc_info=True)
        return image, 'image/png', width, height

    def get_logo_cm(self, width, height):
        "Return logo image with mime-type and size in centimeter"
        width *= 300 / 2.54
        height *= 300 / 2.54
        image, mimetype, width, height = self.get_logo(width, height)
        width /= 300 / 2.54
        height /= 300 / 2.54
        return image, mimetype, f'{width}cm', f'{height}cm'

    def get_logo_in(self, width, height):
        "Return logo image with mime-type and size in inch"
        width *= 300
        height *= 300
        image, mimetype, width, height = self.get_logo(width, height)
        width /= 300
        height /= 300
        return image, mimetype, f'{width}in', f'{height}in'

    def _logo_resize(self, width, height, **_params):
        if not PIL:
            return self.logo, width, height
        data = io.BytesIO()
        img = PIL.Image.open(io.BytesIO(self.logo))
        img.thumbnail((width, height))
        img.save(data, format='png', optimize=True, dpi=(300, 300), **_params)
        return data.getvalue(), img.width, img.height

    def _logo_store_cache(self, image, width, height):
        Cache = self.__class__.logo_cache.get_target()
        return Cache(
            company=self,
            image=image,
            width=width,
            height=height)

    @classmethod
    def _logo_clear_cache(cls, companies):
        Cache = cls.logo_cache.get_target()
        caches = [c for r in companies for c in r.logo_cache]
        Cache.delete(caches)

    def get_tax_identifier(self, pattern=None):
        if pattern is None:
            pattern = {}
        for record in self.tax_identifiers:
            if record.match(pattern):
                return record.tax_identifier
        return self.party.tax_identifier


class CompanyTaxIdentifier(
        MatchMixin, sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'company.company.tax_identifier'

    company = fields.Many2One(
        'company.company', "Company", required=True, ondelete='CASCADE')
    company_party = fields.Function(
        fields.Many2One(
            'party.party', "Company Party",
            context={
                'company': Eval('company', None),
                }),
        'on_change_with_company_party')

    country = fields.Many2One(
        'country.country', "Country", ondelete='RESTRICT',
        states={
            'invisible': Bool(Eval('organization')),
            },
        help="Applies only to addresses in this country.")
    organization = fields.Many2One(
        'country.organization', "Organization",
        states={
            'invisible': Bool(Eval('country')),
            },
        help="Applies only to addresses in this organization.")

    tax_identifier = fields.Many2One(
        'party.identifier', "Tax Identifier",
        help="The identifier used for tax report.")

    @classmethod
    def __setup__(cls):
        pool = Pool()
        Party = pool.get('party.party')
        super().__setup__()
        cls.__access__.add('company')
        tax_identifier_types = Party.tax_identifier_types()
        cls.tax_identifier.domain = [
            ('party', '=', Eval('company_party', -1)),
            ('type', 'in', tax_identifier_types),
            ]

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @fields.depends('company', '_parent_company.party')
    def on_change_with_company_party(self, name=None):
        if self.company:
            return self.company.party

    def match(self, pattern, match_none=False):
        if 'country' in pattern:
            pattern = pattern.copy()
            country = pattern.pop('country')
            if country is not None or match_none:
                if self.country and self.country.id != country:
                    return False
                if (self.organization
                        and country not in [
                            c.id for c in self.organization.countries]):
                    return False
        return super().match(pattern, match_none=match_none)


class CompanyLogoCache(ModelSQL):
    __name__ = 'company.company.logo.cache'

    company = fields.Many2One(
        'company.company', "Company", required=True, ondelete='CASCADE')
    image = fields.Binary("Image", required=True)
    width = fields.Integer(
        "Width", required=True,
        domain=[
            ('width', '>', 0),
            ('width', '<=', SIZE_MAX),
            ])
    height = fields.Integer(
        "Height", required=True,
        domain=[
            ('height', '>', 0),
            ('height', '<=', SIZE_MAX),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('dimension_unique', Unique(t, t.company, t.width, t.height),
                'company.msg_company_logo_cache_size_unique'),
            ]


class Employee(ModelSQL, ModelView):
    __name__ = 'company.employee'
    party = fields.Many2One('party.party', 'Party', required=True,
        context={
            'company': If(
                Eval('company', -1) >= 0, Eval('company', None), None),
            },
        depends={'company'},
        help="The party which represents the employee.")
    company = fields.Many2One('company.company', 'Company', required=True,
        help="The company to which the employee belongs.")
    active = fields.Function(
        fields.Boolean("Active"),
        'on_change_with_active', searcher='search_active')
    start_date = fields.Date('Start Date',
        domain=[If((Eval('start_date')) & (Eval('end_date')),
                ('start_date', '<=', Eval('end_date')),
                (),
                )
            ],
        help="When the employee joins the company.")
    end_date = fields.Date('End Date',
        domain=[If((Eval('start_date')) & (Eval('end_date')),
                ('end_date', '>=', Eval('start_date')),
                (),
                )
            ],
        help="When the employee leaves the company.")
    supervisor = fields.Many2One(
        'company.employee', "Supervisor",
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        help="The employee who oversees this employee.")
    subordinates = fields.One2Many(
        'company.employee', 'supervisor', "Subordinates",
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        help="The employees to be overseen by this employee.")

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('start_date', 'end_date')
    def on_change_with_active(self, name=None):
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        date = context.get('date') or Date.today()
        start_date = self.start_date or dt.date.min
        end_date = self.end_date or dt.date.max
        return start_date <= date <= end_date

    @classmethod
    def search_active(cls, name, domain):
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        date = context.get('date') or Date.today()
        _, operator, value = domain
        if (operator == '=' and value) or (operator == '!=' and not value):
            domain = [
                ['OR',
                    ('start_date', '=', None),
                    ('start_date', '<=', date),
                    ],
                ['OR',
                    ('end_date', '=', None),
                    ('end_date', '>=', date),
                    ],
                ]
        elif (operator == '=' and not value) or (operator == '!=' and value):
            domain = ['OR',
                ('start_date', '>', date),
                ('end_date', '<', date),
                ]
        else:
            domain = []
        return domain

    def get_rec_name(self, name):
        return self.party.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('party.rec_name',) + tuple(clause[1:])]


class CompanyConfigStart(ModelView):
    __name__ = 'company.company.config.start'


class CompanyConfig(Wizard):
    __name__ = 'company.company.config'
    start = StateView('company.company.config.start',
        'company.company_config_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'company', 'tryton-ok', True),
            ])
    company = StateView('company.company',
        'company.company_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Add', 'add', 'tryton-ok', True),
            ])
    add = StateTransition()

    def transition_add(self):
        User = Pool().get('res.user')

        self.company.save()
        users = User.search([
                ('companies', '=', None),
                ])
        User.write(users, {
                'companies': [('add', [self.company.id])],
                'company': self.company.id,
                })
        return 'end'

    def end(self):
        return 'reload context'


class CompanyReport(Report):

    @classmethod
    def header_key(cls, record, data):
        return super().header_key(record, data) + (
            ('company', record.company),
            )

    @classmethod
    def get_context(cls, records, header, data):
        context = super().get_context(records, header, data)
        context['company'] = header.get('company')
        return context
