#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields


class Country(ModelSQL, ModelView):
    'Country'
    _name = 'country.country'
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True,
           help='The full name of the country.', select=True)
    code = fields.Char('Code', size=2, select=True,
           help='The ISO country code in two chars.\n'
           'You can use this field for quick search.', required=True)
    subdivisions = fields.One2Many('country.subdivision',
            'country', 'Subdivisions')

    def __init__(self):
        super(Country, self).__init__()
        self._sql_constraints += [
            ('name_uniq', 'UNIQUE(name)',
             'The name of the country must be unique!'),
            ('code_uniq', 'UNIQUE(code)',
             'The code of the country must be unique!'),
        ]
        self._order.insert(0, ('name', 'ASC'))

    def search_rec_name(self, name, clause):
        ids = self.search([('code',) + clause[1:]], limit=1)
        if ids:
            return [('code',) + clause[1:]]
        return [(self._rec_name,) + clause[1:]]

    def create(self, vals):
        if 'code' in vals and vals['code']:
            vals = vals.copy()
            vals['code'] = vals['code'].upper()
        return super(Country, self).create(vals)

    def write(self, ids, vals):
        if 'code' in vals and vals['code']:
            vals = vals.copy()
            vals['code'] = vals['code'].upper()
        return super(Country, self).write(ids, vals)

Country()


class Subdivision(ModelSQL, ModelView):
    "Subdivision"
    _name = 'country.subdivision'
    _description = __doc__
    country = fields.Many2One('country.country', 'Country',
            required=True, select=True)
    name = fields.Char('Name', required=True, select=True, translate=True)
    code = fields.Char('Code', required=True, select=True)
    type = fields.Selection([
        ('administration', 'Administration'),
        ('administrative area', 'Administrative area'),
        ('administrative region', 'Administrative Region'),
        ('administrative territory', 'Administrative Territory'),
        ('area', 'Area'),
        ('atoll', 'Atoll'),
        ('autonomous city', 'Autonomous City'),
        ('autonomous commune', 'Autonomous Commune'),
        ('autonomous communities', 'Autonomous communities'),
        ('autonomous district', 'Autonomous District'),
        ('autonomous island', 'Autonomous island'),
        ('autonomous monastic state', 'Autonomous monastic state'),
        ('autonomous municipality', 'Autonomous municipality'),
        ('autonomous province', 'Autonomous Province'),
        ('autonomous region', 'Autonomous Region'),
        ('autonomous republic', 'Autonomous republic'),
        ('autonomous sector', 'Autonomous sector'),
        ('autonomous territory', 'Autonomous territory'),
        ('borough', 'Borough'),
        ('canton', 'Canton'),
        ('capital city', 'Capital city'),
        ('capital district', 'Capital District'),
        ('capital metropolitan city', 'Capital Metropolitan City'),
        ('capital territory', 'Capital Territory'),
        ('city', 'City'),
        ('city corporation', 'City corporation'),
        ('city with county rights', 'City with county rights'),
        ('commune', 'Commune'),
        ('country', 'Country'),
        ('county', 'County'),
        ('department', 'Department'),
        ('dependency', 'Dependency'),
        ('district', 'District'),
        ('division', 'Division'),
        ('economic prefecture', 'Economic Prefecture'),
        ('economic region', 'Economic region'),
        ('emirate', 'Emirate'),
        ('entity', 'Entity'),
        ('federal dependency', 'Federal Dependency'),
        ('federal district', 'Federal District'),
        ('federal territories', 'Federal Territories'),
        ('geographical region', 'Geographical region'),
        ('geographical unit', 'Geographical unit'),
        ('governorate', 'Governorate'),
        ('included for completeness', 'Included for completeness'),
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
        ('oblast', 'Oblast'),
        ('outlying area', 'Outlying area'),
        ('overseas region/department', 'Overseas region/department'),
        ('overseas territorial collectivity',
            'Overseas territorial collectivity'),
        ('parish', 'Parish'),
        ('prefecture', 'Prefecture'),
        ('principality', 'Principality'),
        ('province', 'Province'),
        ('rayon', 'Rayon'),
        ('region', 'Region'),
        ('regional council', 'Regional council'),
        ('republic', 'Republic'),
        ('special administrative region', 'Special administrative region'),
        ('special city', 'Special city'),
        ('special district', 'Special District'),
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
        ], 'Type', required=True)
    parent = fields.Many2One('country.subdivision', 'Parent')

    def __init__(self):
        super(Subdivision, self).__init__()
        self._order.insert(0, ('code', 'ASC'))

    def search_rec_name(self, name, clause):
        ids = self.search([('code',) + clause[1:]], limit=1)
        if ids:
            return [('code',) + clause[1:]]
        return [(self._rec_name,) + clause[1:]]

    def create(self, vals):
        if 'code' in vals and vals['code']:
            vals['code'] = vals['code'].upper()
        return super(Subdivision, self).create(vals)

    def write(self, ids, vals):
        if 'code' in vals and vals['code']:
            vals['code'] = vals['code'].upper()
        return super(Subdivision, self).write(ids, vals)

Subdivision()
