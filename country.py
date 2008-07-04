#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV
STATES = {
    'readonly': "active == False",
}


class Country(OSV):
    'Country'
    _name = 'relationship.country'
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True,
           help='The full name of the country.', select=1)
    code = fields.Char('Code', size=2, select=1,
           help='The ISO country code in two chars.\n'
           'You can use this field for quick search.', required=True)
    state = fields.One2Many('relationship.country.state', 'country', 'State')

    def __init__(self):
        super(Country, self).__init__()
        self._sql_constraints += [
            ('name_uniq', 'UNIQUE(name)',
             'The name of the country must be unique!'),
            ('code_uniq', 'UNIQUE(code)',
             'The code of the country must be unique!'),
        ]
        self._order.insert(0, ('code', 'ASC'))

    def name_search(self, cr, user, name='', args=None, operator='ilike',
                    context=None, limit=None):
        if not args:
            args=[]
        if not context:
            context={}
        ids = False
        if len(name) <= 2:
            ids = self.search(cr, user, [('code', '=', name)] + args,
                    limit=limit, context=context)
        if not ids:
            ids = self.search(cr, user, [('name', operator, name)] + args,
                    limit=limit, context=context)
        return self.name_get(cr, user, ids, context)

    def create(self, cursor, user, vals, context=None):
        if 'code' in vals:
            vals['code'] = vals['code'].upper()
        return super(Country, self).create(cursor, user, vals, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if 'code' in vals:
            vals['code'] = vals['code'].upper()
        return super(Country, self).write(cursor, user, ids, vals,
                context=context)

Country()


class State(OSV):
    "State"
    _name = 'relationship.country.state'
    _description = __doc__
    country = fields.Many2One('relationship.country', 'Country',
            required=True)
    name = fields.Char('Name', required=True, select=1)
    code = fields.Char('Code', size=3, required=True, select=1)

    def __init__(self):
        super(State, self).__init__()
        self._order.insert(0, ('code', 'ASC'))

    def create(self, cursor, user, vals, context=None):
        if 'code' in vals:
            vals['code'] = vals['code'].upper()
        return super(State, self).create(cursor, user, vals,
                context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if 'code' in vals:
            vals['code'] = vals['code'].upper()
        return super(State, self).write(cursor, user, ids, vals,
                context=context)

State()
