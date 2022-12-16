# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, DeactivableMixin, fields
from trytond.pyson import Eval
from trytond.tools import lstrip_wildcard

__all__ = ['Country', 'Subdivision', 'Zip']


class Country(DeactivableMixin, ModelSQL, ModelView):
    'Country'
    __name__ = 'country.country'
    name = fields.Char('Name', required=True, translate=True,
           help="The main identifier of the country.", select=True)
    code = fields.Char('Code', size=2, select=True,
           help="The 2 chars ISO country code.")
    code3 = fields.Char('3-letters Code', size=3, select=True,
        help="The 3 chars ISO country code.")
    code_numeric = fields.Char('Numeric Code', select=True,
        help="The ISO numeric country code.")
    subdivisions = fields.One2Many('country.subdivision',
            'country', 'Subdivisions')

    @classmethod
    def __setup__(cls):
        super(Country, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        super(Country, cls).__register__(module_name)

        table = cls.__table_handler__(module_name)

        # Migration from 3.4: drop unique constraints from name and code
        table.drop_constraint('name_uniq')
        table.drop_constraint('code_uniq')

        # Migration from 3.8: remove required on code
        table.not_null_action('code', 'remove')

    @classmethod
    def search_rec_name(cls, name, clause):
        code_value = clause[2]
        if clause[1].endswith('like'):
            code_value = lstrip_wildcard(clause[2])
        return ['OR',
            ('name',) + tuple(clause[1:]),
            ('code', clause[1], code_value) + tuple(clause[3:]),
            ('code3', clause[1], code_value) + tuple(clause[3:]),
            ('code_numeric', clause[1], code_value) + tuple(clause[3:]),
            ]

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
    country = fields.Many2One('country.country', 'Country',
            required=True, select=True,
        help="The country where this subdivision is.")
    name = fields.Char('Name', required=True, select=True, translate=True,
        help="The main identifier of the subdivision.")
    code = fields.Char('Code', required=True, select=True,
        help="The ISO code of the subdivision.")
    type = fields.Selection([
        ('administration', 'Administration'),
        ('administrative area', 'Administrative area'),
        ('administrative atoll', 'Administrative atoll'),
        ('administrative region', 'Administrative Region'),
        ('administrative territory', 'Administrative Territory'),
        ('area', 'Area'),
        ('atoll', 'Atoll'),
        ('arctic region', 'Arctic Region'),
        ('autonomous city', 'Autonomous City'),
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
        ('capital city', 'Capital city'),
        ('capital district', 'Capital District'),
        ('capital metropolitan city', 'Capital Metropolitan City'),
        ('capital territory', 'Capital Territory'),
        ('chains (of islands)', 'Chains (of islands)'),
        ('city', 'City'),
        ('city corporation', 'City corporation'),
        ('city with county rights', 'City with county rights'),
        ('commune', 'Commune'),
        ('constitutional province', 'Constitutional province'),
        ('council area', 'Council area'),
        ('country', 'Country'),
        ('county', 'County'),
        ('department', 'Department'),
        ('dependency', 'Dependency'),
        ('development region', 'Development region'),
        ('district', 'District'),
        ('district council area', 'District council area'),
        ('division', 'Division'),
        ('economic prefecture', 'Economic Prefecture'),
        ('economic region', 'Economic region'),
        ('emirate', 'Emirate'),
        ('entity', 'Entity'),
        ('federal dependency', 'Federal Dependency'),
        ('federal district', 'Federal District'),
        ('federal territories', 'Federal Territories'),
        ('geographical entity', 'Geographical entity'),
        ('geographical region', 'Geographical region'),
        ('geographical unit', 'Geographical unit'),
        ('governorate', 'Governorate'),
        ('included for completeness', 'Included for completeness'),
        ('indigenous region', 'Indigenous region'),
        ('island', 'Island'),
        ('island council', 'Island council'),
        ('island group', 'Island group'),
        ('local council', 'Local council'),
        ('london borough', 'London borough'),
        ('metropolitan cities', 'Metropolitan cities'),
        ('metropolitan department', 'Metropolitan department'),
        ('metropolitan district', 'Metropolitan district'),
        ('metropolitan region', 'Metropolitan region'),
        ('municipalities', 'Municipalities'),
        ('municipality', 'Municipality'),
        ('nation', 'Nation'),
        ('oblast', 'Oblast'),
        ('outlying area', 'Outlying area'),
        ('overseas department', 'Overseas department'),
        ('overseas region', 'Overseas region'),
        ('overseas region/department', 'Overseas region/department'),
        ('overseas territorial collectivity',
            'Overseas territorial collectivity'),
        ('parish', 'Parish'),
        ('popularates', 'Popularates'),
        ('prefecture', 'Prefecture'),
        ('principality', 'Principality'),
        ('province', 'Province'),
        ('quarter', 'Quarter'),
        ('rayon', 'Rayon'),
        ('region', 'Region'),
        ('regional council', 'Regional council'),
        ('republic', 'Republic'),
        ('republican city', 'Republican City'),
        ('self-governed part', 'Self-governed part'),
        ('special administrative region', 'Special administrative region'),
        ('special city', 'Special city'),
        ('special district', 'Special District'),
        ('special island authority', 'Special island authority'),
        ('special municipality', 'Special Municipality'),
        ('special region', 'Special Region'),
        ('special zone', 'Special zone'),
        ('state', 'State'),
        ('territorial unit', 'Territorial unit'),
        ('territory', 'Territory'),
        ('town council', 'Town council'),
        ('two-tier county', 'Two-tier county'),
        ('union territory', 'Union territory'),
        ('unitary authority', 'Unitary authority'),
        ('unitary authority (england)', 'Unitary authority (england)'),
        ('unitary authority (wales)', 'Unitary authority (wales)'),
        ('zone', 'zone'),
        ], 'Type', required=True)
    parent = fields.Many2One('country.subdivision', 'Parent',
        domain=[
            ('country', '=', Eval('country', -1)),
            ],
        depends=['country'],
        help="Add subdivision below the parent.")

    @classmethod
    def __setup__(cls):
        super(Subdivision, cls).__setup__()
        cls._order.insert(0, ('code', 'ASC'))

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('name',) + tuple(clause[1:]),
            ('code',) + tuple(clause[1:]),
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


class Zip(ModelSQL, ModelView):
    "Zip"
    __name__ = 'country.zip'
    country = fields.Many2One('country.country', 'Country', required=True,
        select=True, ondelete='CASCADE',
        help="The country where the zip is.")
    subdivision = fields.Many2One('country.subdivision', 'Subdivision',
        select=True, ondelete='CASCADE',
        domain=[('country', '=', Eval('country', -1))],
        depends=['country'],
        help="The subdivision where the zip is.")
    zip = fields.Char('Zip')
    city = fields.Char('City', help="The name of the city for the zip.")

    @classmethod
    def __setup__(cls):
        super(Zip, cls).__setup__()
        cls._order.insert(0, ('country', 'ASC'))
        cls._order.insert(0, ('zip', 'ASC'))

    def get_rec_name(self, name):
        if self.city and self.zip:
            return '%s (%s)' % (self.city, self.zip)
        else:
            return (self.zip or self.city or str(self.id))

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('zip',) + tuple(clause[1:]),
            ('city',) + tuple(clause[1:]),
            ]
