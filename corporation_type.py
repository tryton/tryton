from trytond.osv import fields, OSV
STATES = {'readonly': "active == False",}

class CorporationType(OSV):
    "Corporation Type"

    _name = 'partner.corporation_type'
    _description = __doc__
    _order= 'name'
    _columns = {
        'name': fields.Char('Name', required=True, size=64),
    }

CorporationType()
