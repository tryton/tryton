from trytond.osv import fields, OSV
STATES = {
    'readonly': "active == False",
}

class Address(OSV):
    "Partner Address"
    _name = 'partner.address'
    _description = __doc__
    _order = 'partner, sequence, id'
    partner = fields.Many2One('partner.partner', 'Partner', required=True,
           ondelete='cascade', select=True,  states=STATES)
    type_invoice = fields.Boolean("Invoice", states=STATES,
        help="Make this address of type invoicing")
    type_delivery = fields.Boolean("Delivery", states=STATES,
        help="Make this address of type delivery")
    type_contact = fields.Boolean("Contact", states=STATES,
        help="Make this address of type contact")
    name = fields.Char('Contact Name', size=64, states=STATES)
    street = fields.Char('Street', size=128, states=STATES)
    streetbis = fields.Char('Street (bis)', size=128, states=STATES)
    zip = fields.Char('Zip', change_default=True, size=24,
           states=STATES)
    city = fields.Char('City', size=128, states=STATES)
    country = fields.Many2One('partner.country', 'Country',
           states=STATES)
    state = fields.Many2One("partner.country.state", 'State',
           domain="[('country', '=', country)]", states=STATES)
    email = fields.Char('E-Mail', size=64, states=STATES)
    phone = fields.Char('Phone', size=64, states=STATES)
    fax = fields.Char('Fax', size=64, states=STATES)
    mobile = fields.Char('Mobile', size=64, states=STATES)
    active = fields.Boolean('Active')
    sequence = fields.Integer("Sequence")


    def default_active(self, cursor, user, context=None):
        return 1

    def default_sequence(self, cursor, user, context=None):
        return 10

    def name_get(self, cursor, user, ids, context=None):
        if not len(ids):
            return []
        res = []
        for address in self.browse(cursor, user, ids, context):
            res.append((address.id, ", ".join(x for x in [address.name, address.partner.name, address.zip, address.city] if x)))
        return res


    def name_search(self, cursor, user, name, args=None, operator='ilike', context=None, limit=80):
        if not args:
            args=[]
        if not context:
            context={}

        ids = self.search(cursor, user, [('zip','=',name)] + args, limit=limit, context=context)
        if not ids:
            ids = self.search(cursor, user, [('city',operator,name)] + args, limit=limit, context=context)
        if name:
            ids += self.search(cursor, user, [('name',operator,name)] + args, limit=limit, context=context)
            ids += self.search(cursor, user, [('partner',operator,name)] + args, limit=limit, context=context)
        return self.name_get(cursor, user, ids, context=context)

Address()
