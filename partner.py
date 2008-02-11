from trytond.osv import fields, OSV


class CorporationType(OSV):
    "Corporation Type"

    _name = 'partner.corporation_type'
    _description = __doc__
    _order= 'name'
    _columns = {
        'name': fields.char('Name', required=True, size=64),
    }

CorporationType()

class Category(OSV):
    "Partner Category"

    _name = "partner.category"
    _description = __doc__
    _order = 'parent,name'
    _parent_name = 'parent'

    def name_get(self, cursor, user, ids, context=None):

        if not len(ids):
            return []
        categories = self.browse(cursor, user, ids, context=context)
        res = []
        for category in categories:
            if category.parent:
                name = category.parent.name+' / '+ category.name
            else:
                name = category.name
            res.append((category.id, name))
        return res

    def _name_get_fnc(self, cursor, user, obj_id, name, value, arg,
            context=None):
        res = self.name_get(cursor, user, ids, context)
        return dict(res)

    def check_recursion(self, cursor, user, ids, parent=None):
        return super(Category, self).check_recursion(cursor, user,
            ids,parent="parent")

    _columns = {
        'name': fields.char('Category Name', required=True, size=64),
        'parent': fields.many2one('partner.category', 'Parent Category',
                select=True),
        'complete_name': fields.function(_name_get_fnc, method=True,
                type="char", string='Name'),
        'childs': fields.one2many('partner.category', 'parent',
            'Childs Category'),
        'active' : fields.boolean('Active'),
    }

    _defaults = {
        'active' : lambda *a: 1,
    }

    _constraints = [
        (check_recursion,
         'Error ! You can not create recursive categories.', ['parent'])
	]

Category()

class Partner(OSV):
    "Partner"

    _description = __doc__
    _name = "partner.partner"
    _order = "name"

    _columns = {
        'name': fields.char('Name', size=128, required=True, select=True),
        'corp_type': fields.many2one("partner.corporation_type", "Corp. Type"),
        'lang': fields.many2one("ir.lang", 'Language'),
        'vat': fields.char('VAT',size=32 ,help="Value Added Tax number"),
        'website': fields.char('Website',size=64),
        'addresses': fields.one2many('partner.address', 'partner',
                                     'Addresses'),
        'categories': fields.many2many(
                'partner.category', 'partner_category_rel',
                'partner', 'category', 'Categories'),
        'active': fields.boolean('Active'),
    }
    _defaults = {
        'active': lambda *a: True,
    }

    _sql_constraints = [
        ('name_uniq', 'unique (name)',
         'The name of the partner must be unique !')
    ]
Partner()


class Country(OSV):
    'Partner Country'

    _name = 'partner.country'
    _description = __doc__
    _order='code'

    _columns = {
        'name': fields.char('Country Name', size=64,
                help='The full name of the country.', required=True),
        'code': fields.char('Country Code', size=2,
                help='The ISO country code in two chars.\n'
                'You can use this field for quick search.', required=True),
    }
    _sql_constraints = [
        ('name_uniq', 'unique (name)',
         'The name of the country must be unique !'),
        ('code_uniq', 'unique (code)',
         'The code of the country must be unique !')
    ]

    def name_search(self, cr, user, name='', args=None, operator='ilike',
                    context=None, limit=80):
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
    "Country state"

    _name = 'partner.state'
    _description = __doc__
    _order = 'code'

    _columns = {
        'country': fields.many2one('partner.country', 'Country',
                                   required=True),
        'name': fields.char('State Name', size=64, required=True),
        'code': fields.char('State Code', size=3, required=True),
	}

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



class Address(OSV):
    "Partner Address"

    _name = 'partner.address'
    _description = __doc__
    _order = 'partner'



    _columns = {
        'partner': fields.many2one('partner.partner', 'Partner', required=True,
                                   ondelete='cascade', select=True),
        'type': fields.selection( [ ('default','Default'),('invoice','Invoice'),
            ('delivery','Delivery'), ('contact','Contact'), ('other','Other') ],
            'Address Type'),
        'name': fields.char('Contact Name', size=64),
        'street': fields.char('Street', size=128),
        'streetbis': fields.char('Street (bis)', size=128),
        'zip': fields.char('Zip', change_default=True, size=24),
        'city': fields.char('City', size=128),
        'state': fields.many2one("partner.state", 'State',
                                 domain="[('country_id','=',country_id)]"),
        'country': fields.many2one('partner.country', 'Country'),
        'email': fields.char('E-Mail', size=64),
        'phone': fields.char('Phone', size=64),
        'fax': fields.char('Fax', size=64),
        'mobile': fields.char('Mobile', size=64),
        'active': fields.boolean('Active'),
    }
    _defaults = {
        'active': lambda *a: 1,
    }
Address()
