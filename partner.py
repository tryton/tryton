from trytond.osv import fields, OSV
STATES = {'readonly': "active == False",}

class Partner(OSV):
    "Partner"

    _description = __doc__
    _name = "partner.partner"
    _order = "name"

    _columns = {
        'name': fields.Char('Name', size=128, required=True, select=True,
                states= STATES,),
        'corp_type': fields.Many2One("partner.corporation_type", "Corp. Type",
                states= STATES,),
        'lang': fields.Many2One("ir.lang", 'Language',
                states= STATES,),
        'vat': fields.Char('VAT',size=32 ,help="Value Added Tax number",
                states= STATES,),
        'website': fields.Char('Website',size=64,
                states= STATES,),
        'addresses': fields.One2Many('partner.address', 'partner',
                'Addresses',states= STATES,),
        'categories': fields.Many2Many(
                'partner.category', 'partner_category_rel',
                'partner', 'category', 'Categories',
                states= STATES,),
        'active': fields.Boolean('Active'),
    }
    _defaults = {
        'active': lambda *a: True,
    }

    _sql_constraints = [
        ('name_uniq', 'unique (name)',
         'The name of the partner must be unique !')
    ]
Partner()
