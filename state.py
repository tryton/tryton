from trytond.osv import fields, OSV
STATES = {
    'readonly': "active == False"
}


class State(OSV):
    "Country state"
    _name = 'partner.state'
    _description = __doc__
    _order = 'code'
    country = fields.Many2One('partner.country', 'Country',
            required=True)
    name = fields.Char('State Name', size=64, required=True)
    code = fields.Char('State Code', size=3, required=True)

    def create(self, cursor, user, vals, context=None):
        if 'code' in vals:
            vals['code'] = vals['code'].upper()
        return super(CountryState, self).create(cursor, user, vals,
                context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if 'code' in vals:
            vals['code'] = vals['code'].upper()
        return super(CountryState, self).write(cursor, user, ids, vals,
                context=context)

State()

