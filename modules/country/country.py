# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt

from sql import Literal
from sql.conditionals import Coalesce

from trytond import backend
from trytond.model import DeactivableMixin, ModelSQL, ModelView, fields, tree
from trytond.pool import Pool
from trytond.pyson import Eval, If
from trytond.tools import is_full_text, lstrip_wildcard
from trytond.transaction import Transaction


class Organization(ModelSQL, ModelView):
    "Organization"
    __name__ = 'country.organization'

    name = fields.Char("Name", required=True, translate=True)
    code = fields.Char("Code")
    members = fields.One2Many(
        'country.organization.member', 'organization', "Members",
        filter=[
            ('active', 'in', [True, False]),
            ])
    countries = fields.Many2Many(
        'country.organization.member', 'organization', 'country', "Countries",
        readonly=True)


class OrganizationMember(ModelSQL, ModelView):
    "Organization Member"
    __name__ = 'country.organization.member'

    organization = fields.Many2One(
        'country.organization', "Organization", required=True)
    country = fields.Many2One(
        'country.country', "Country", required=True)
    from_date = fields.Date(
        "From Date",
        domain=[
            If(Eval('from_date') & Eval('to_date'),
                ('from_date', '<=', Eval('to_date')),
                ()),
            ])
    to_date = fields.Date(
        "To Date",
        domain=[
            If(Eval('from_date') & Eval('to_date'),
                ('to_date', '>=', Eval('from_date')),
                ()),
            ])
    active = fields.Function(fields.Boolean("Active"), 'on_change_with_active')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('country', None))
        cls._order.insert(1, ('from_date', 'ASC NULLS FIRST'))
        cls.__access__.add('organization')

    @classmethod
    def default_active(cls):
        return True

    @fields.depends('from_date', 'to_date')
    def on_change_with_active(self, name=None):
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        date = context.get('date', Date.today())

        from_date = self.from_date or dt.date.min
        to_date = self.to_date or dt.date.max
        return from_date <= date <= to_date

    @classmethod
    def domain_active(cls, domain, tables):
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        table, _ = tables[None]
        _, operator, operand = domain
        date = context.get('date', Date.today())

        from_date = Coalesce(table.from_date, dt.date.min)
        to_date = Coalesce(table.to_date, dt.date.max)

        expression = (from_date <= date) & (to_date >= date)

        if operator in {'=', '!='}:
            if (operator == '=') != operand:
                expression = ~expression
        elif operator in {'in', 'not in'}:
            if True in operand and False not in operand:
                pass
            elif False in operand and True not in operand:
                expression = ~expression
            else:
                expression = Literal(True)
        else:
            expression = Literal(True)
        return expression


class Region(tree(), ModelSQL, ModelView):
    "Region"
    __name__ = 'country.region'

    name = fields.Char("Name", required=True, translate=True)
    code_numeric = fields.Char(
        "Numeric Code", size=3,
        help="UN M49 region code.")
    parent = fields.Many2One('country.region', "Parent")
    subregions = fields.One2Many('country.region', 'parent', "Subregions")
    countries = fields.One2Many(
        'country.country', 'region', "Countries",
        add_remove=[
            ('region', '=', None),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('name', 'ASC'))

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
            ('name',) + tuple(clause[1:]),
            ('code_numeric', clause[1], code_value) + tuple(clause[3:]),
            ]


class Country(DeactivableMixin, ModelSQL, ModelView):
    'Country'
    __name__ = 'country.country'
    name = fields.Char(
        "Name", required=True, translate=True,
        help="The main identifier of the country.")
    code = fields.Char(
        "Code", size=2,
        help="The 2 chars ISO country code.")
    code3 = fields.Char(
        "3-letters Code", size=3,
        help="The 3 chars ISO country code.")
    code_numeric = fields.Char(
        "Numeric Code",
        help="The ISO numeric country code.")
    flag = fields.Function(fields.Char("Flag"), 'on_change_with_flag')
    region = fields.Many2One(
        'country.region', "Region", ondelete='SET NULL')
    subdivisions = fields.One2Many('country.subdivision',
            'country', 'Subdivisions')
    members = fields.One2Many(
        'country.organization.member', 'country', "Members",
        filter=[
            ('active', 'in', [True, False]),
            ])
    organizations = fields.Many2Many(
        'country.organization.member', 'country', 'organization',
        "Organizations", readonly=True)

    @classmethod
    def __setup__(cls):
        super(Country, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Data = pool.get('ir.model.data')
        data = Data.__table__()
        cursor = Transaction().connection.cursor()

        super(Country, cls).__register__(module_name)

        # Migration from 5.2: remove country data
        cursor.execute(*data.delete(where=(data.module == 'country')
                & (data.model == cls.__name__)))

    @fields.depends('code')
    def on_change_with_flag(self, name=None):
        if self.code:
            return ''.join(map(chr, map(lambda c: 127397 + ord(c), self.code)))

    def get_rec_name(self, name):
        name = self.name
        if self.flag:
            name = ' '.join([self.flag, self.name])
        return name

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
            ('name', operator, operand, *extra),
            ('code', operator, code_value, *extra),
            ('code3', operator, code_value, *extra),
            ('code_numeric', operator, code_value, *extra),
            ]

    def is_member(self, organization, date=None):
        """Return if the country is in the organization at the date
        organization can be an XML id"""
        pool = Pool()
        Date = pool.get('ir.date')
        ModelData = pool.get('ir.model.data')
        Organization = pool.get('country.organization')
        if date is None:
            date = Date.today()
        if isinstance(organization, str):
            organization = ModelData.get_id(organization)
        with Transaction().set_context(date=date):
            organization = Organization(organization)
        return self in organization.countries

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            for code in {'code', 'code3', 'code_numeric'}:
                if code in vals and vals[code]:
                    vals[code] = vals[code].upper()
        return super(Country, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        args = []
        for countries, values in zip(actions, actions):
            for code in {'code', 'code3', 'code_numeric'}:
                if values.get(code):
                    values = values.copy()
                    values[code] = values[code].upper()
            args.extend((countries, values))
        super(Country, cls).write(*args)


class Subdivision(DeactivableMixin, ModelSQL, ModelView):
    "Subdivision"
    __name__ = 'country.subdivision'
    country = fields.Many2One(
        'country.country', "Country", required=True,
        help="The country where this subdivision is.")
    name = fields.Char(
        "Name", required=True, translate=True,
        help="The main identifier of the subdivision.")
    code = fields.Char(
        "Code",
        help="The ISO code of the subdivision.")
    flag = fields.Function(fields.Char("Flag"), 'on_change_with_flag')
    type = fields.Selection([
        (None, ""),
        ('administration', 'Administration'),
        ('administrative area', 'Administrative area'),
        ('administrative atoll', 'Administrative atoll'),
        ('administrative precinct', 'Administrative precinct'),
        ('administrative region', 'Administrative Region'),
        ('administrative territory', 'Administrative Territory'),
        ('area', 'Area'),
        ('atoll', 'Atoll'),
        ('arctic region', 'Arctic Region'),
        ('autonomous city', 'Autonomous City'),
        ('autonomous city in north africa', 'Autonomous city in north africa'),
        ('autonomous commune', 'Autonomous Commune'),
        ('autonomous communities', 'Autonomous communities'),
        ('autonomous community', 'Autonomous community'),
        ('autonomous district', 'Autonomous District'),
        ('autonomous island', 'Autonomous island'),
        ('autonomous monastic state', 'Autonomous monastic state'),
        ('autonomous municipality', 'Autonomous municipality'),
        ('autonomous province', 'Autonomous Province'),
        ('autonomous region', 'Autonomous Region'),
        ('autonomous republic', 'Autonomous republic'),
        ('autonomous sector', 'Autonomous sector'),
        ('autonomous territory', 'Autonomous territory'),
        ('autonomous territorial unit', 'Autonomous territorial unit'),
        ('borough', 'Borough'),
        ('canton', 'Canton'),
        ('capital', 'Capital'),
        ('capital city', 'Capital city'),
        ('capital district', 'Capital District'),
        ('capital metropolitan city', 'Capital Metropolitan City'),
        ('capital territory', 'Capital Territory'),
        ('chain (of islands)', 'Chain (of islands)'),
        ('chains (of islands)', 'Chains (of islands)'),
        ('city', 'City'),
        ('city corporation', 'City corporation'),
        ('city municipality', 'City municipality'),
        ('city with county rights', 'City with county rights'),
        ('commune', 'Commune'),
        ('constitutional province', 'Constitutional province'),
        ('council area', 'Council area'),
        ('country', 'Country'),
        ('county', 'County'),
        ('decentralized regional entity', 'Decentralized regional entity'),
        ('department', 'Department'),
        ('dependency', 'Dependency'),
        ('development region', 'Development region'),
        ('district', 'District'),
        ('district council area', 'District council area'),
        ('district municipality', 'District municipality'),
        ('districts under republic administration',
            'Districts under republic administration'),
        ('district with special status', 'District with special status'),
        ('division', 'Division'),
        ('economic prefecture', 'Economic Prefecture'),
        ('economic region', 'Economic region'),
        ('emirate', 'Emirate'),
        ('entity', 'Entity'),
        ('federal capital territory', 'Federal capital territory'),
        ('federal dependency', 'Federal Dependency'),
        ('federal district', 'Federal District'),
        ('federal territory', 'Federal Territory'),
        ('federal territories', 'Federal Territories'),
        ('free municipal consortium', 'Free municipal consortium'),
        ('geographical entity', 'Geographical entity'),
        ('geographical region', 'Geographical region'),
        ('geographical unit', 'Geographical unit'),
        ('governorate', 'Governorate'),
        ('group of islands (20 inhabited islands)',
            'Group of islands (20 inhabited islands)'),
        ('included for completeness', 'Included for completeness'),
        ('indigenous region', 'Indigenous region'),
        ('island', 'Island'),
        ('island council', 'Island council'),
        ('island group', 'Island group'),
        ('islands, groups of islands', 'Islands, groups of islands'),
        ('land', 'Land'),
        ('local council', 'Local council'),
        ('london borough', 'London borough'),
        ('metropolitan administration', 'Metropolitan administration'),
        ('metropolitan city', 'Metropolitan city'),
        ('metropolitan cities', 'Metropolitan cities'),
        ('metropolitan collectivity with special status',
            'Metropolitan collectivity with special status'),
        ('metropolitan department', 'Metropolitan department'),
        ('metropolitan district', 'Metropolitan district'),
        ('metropolitan region', 'Metropolitan region'),
        ('municipalities', 'Municipalities'),
        ('municipality', 'Municipality'),
        ('nation', 'Nation'),
        ('oblast', 'Oblast'),
        ('outlying area', 'Outlying area'),
        ('overseas collectivity', 'Overseas collectivity'),
        ('overseas collectivity with special status',
            'Overseas collectivity with special status'),
        ('overseas department', 'Overseas department'),
        ('overseas region', 'Overseas region'),
        ('overseas region/department', 'Overseas region/department'),
        ('overseas territory', 'Overseas territory'),
        ('overseas territorial collectivity',
            'Overseas territorial collectivity'),
        ('pakistan administered area', 'Pakistan administered area'),
        ('parish', 'Parish'),
        ('popularate', 'Popularate'),
        ('popularates', 'Popularates'),
        ('prefecture', 'Prefecture'),
        ('principality', 'Principality'),
        ('province', 'Province'),
        ('quarter', 'Quarter'),
        ('rayon', 'Rayon'),
        ('region', 'Region'),
        ('regional council', 'Regional council'),
        ('regional state', 'Regional state'),
        ('republic', 'Republic'),
        ('republican city', 'Republican City'),
        ('rural municipality', 'Rural municipality'),
        ('self-governed part', 'Self-governed part'),
        ('special administrative city', 'Special administrative city'),
        ('special administrative region', 'Special administrative region'),
        ('special city', 'Special city'),
        ('special district', 'Special District'),
        ('special island authority', 'Special island authority'),
        ('special municipality', 'Special Municipality'),
        ('special region', 'Special Region'),
        ('special self-governing city', 'Special self-governing city'),
        ('special self-governing province', 'Special self-governing province'),
        ('special zone', 'Special zone'),
        ('state', 'State'),
        ('territorial unit', 'Territorial unit'),
        ('territory', 'Territory'),
        ('town', 'Town'),
        ('town council', 'Town council'),
        ('two-tier county', 'Two-tier county'),
        ('union territory', 'Union territory'),
        ('unitary authority', 'Unitary authority'),
        ('unitary authority (england)', 'Unitary authority (england)'),
        ('unitary authority (wales)', 'Unitary authority (wales)'),
        ('urban community', 'Urban community'),
        ('urban municipality', 'Urban municipality'),
        ('voivodship', 'Voivodship'),
        ('ward', 'Ward'),
        ('zone', 'zone'),
        ], "Type")
    parent = fields.Many2One('country.subdivision', 'Parent',
        domain=[
            ('country', '=', Eval('country', -1)),
            ],
        help="Add subdivision below the parent.")

    @classmethod
    def __setup__(cls):
        super(Subdivision, cls).__setup__()
        cls._order.insert(0, ('code', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Data = pool.get('ir.model.data')
        data = Data.__table__()
        cursor = Transaction().connection.cursor()

        super().__register__(module_name)

        table_h = cls.__table_handler__(module_name)

        # Migration from 5.2: remove country data
        cursor.execute(*data.delete(where=(data.module == 'country')
                & (data.model == cls.__name__)))

        # Migration from 6.2: remove type required
        table_h.not_null_action('type', action='remove')

        # Migration from 6.4: remove required on code
        table_h.not_null_action('code', action='remove')

    @fields.depends('code')
    def on_change_with_flag(self, name=None):
        if self.code:
            return '🏴' + ''.join(map(chr, map(
                        lambda c: 917504 + ord(c),
                        self.code.replace('-', '').lower()))) + '\U000e007f'

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
            ('name', operator, operand, *extra),
            ('code', operator, code_value, *extra),
            ]

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if 'code' in vals and vals['code']:
                vals['code'] = vals['code'].upper()
        return super(Subdivision, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        args = []
        for subdivisions, values in zip(actions, actions):
            if values.get('code'):
                values = values.copy()
                values['code'] = values['code'].upper()
            args.extend((subdivisions, values))
        super(Subdivision, cls).write(*args)


class PostalCode(ModelSQL, ModelView):
    "Postal Code"
    __name__ = 'country.postal_code'
    country = fields.Many2One(
        'country.country', "Country", required=True, ondelete='CASCADE',
        help="The country that contains the postal code.")
    subdivision = fields.Many2One(
        'country.subdivision', "Subdivision", ondelete='CASCADE',
        domain=[('country', '=', Eval('country', -1))],
        help="The subdivision where the postal code is.")
    postal_code = fields.Char('Postal Code')
    city = fields.Char(
        "City", help="The city associated with the postal code.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('country', 'ASC'))
        cls._order.insert(0, ('postal_code', 'ASC'))

    @classmethod
    def __register__(cls, module):
        # Migration from 5.8: rename zip to postal_code
        backend.TableHandler.table_rename('country_zip', cls._table)
        table_h = cls.__table_handler__(module)
        table_h.column_rename('zip', 'postal_code')

        super().__register__(module)

    def get_rec_name(self, name):
        if self.city and self.postal_code:
            return '%s (%s)' % (self.city, self.postal_code)
        else:
            return (self.postal_code or self.city or str(self.id))

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
            ('postal_code', operator, code_value, *extra),
            ('city', operator, operand, *extra),
            ]
