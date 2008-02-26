from trytond.osv import fields, OSV
STATES = {
    'readonly': "active == False",
}

class Address(OSV):
    "Partner Address"
    _name = 'partner.address'
    _description = __doc__
    _order = 'partner'
    partner = fields.Many2One('partner.partner', 'Partner', required=True,
           ondelete='cascade', select=True,  states=STATES)
    type = fields.Selection( [ ('default','Default'),('invoice','Invoice'),
           ('delivery','Delivery'), ('contact','Contact'),
           ('other','Other') ], 'Address Type',  states=STATES)
    name = fields.Char('Contact Name', size=64, states=STATES)
    street = fields.Char('Street', size=128, states=STATES)
    streetbis = fields.Char('Street (bis)', size=128, states=STATES)
    zip = fields.Char('Zip', change_default=True, size=24,
           states=STATES)
    city = fields.Char('City', size=128, states=STATES)
    state = fields.Many2One("partner.state", 'State',
           domain="[('country_id','=',country_id)]", states=STATES)
    country = fields.Many2One('partner.country', 'Country',
           states=STATES)
    email = fields.Char('E-Mail', size=64, states=STATES)
    phone = fields.Char('Phone', size=64, states=STATES)
    fax = fields.Char('Fax', size=64, states=STATES)
    mobile = fields.Char('Mobile', size=64, states=STATES)
    active = fields.Boolean('Active')
    _defaults = {
        'active': lambda *a: 1,
    }
Address()
