#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
'Address'
from trytond.osv import fields, OSV

STATES = {
    'readonly': "active == False",
}


class Address(OSV):
    "Address"
    _name = 'relationship.address'
    _description = __doc__
    party = fields.Many2One('relationship.party', 'Party', required=True,
           ondelete='cascade', select=1,  states=STATES)
    name = fields.Char('Contact Name', size=64, states=STATES)
    street = fields.Char('Street', size=128, states=STATES)
    streetbis = fields.Char('Street (bis)', size=128, states=STATES)
    zip = fields.Char('Zip', change_default=True, size=24,
           states=STATES)
    city = fields.Char('City', size=128, states=STATES)
    country = fields.Many2One('relationship.country', 'Country',
           states=STATES)
    subdivision = fields.Many2One("relationship.country.subdivision",
            'Subdivision', domain="[('country', '=', country)]", states=STATES)
    email = fields.Char('E-Mail', size=64, states=STATES)
    phone = fields.Char('Phone', size=64, states=STATES)
    fax = fields.Char('Fax', size=64, states=STATES)
    mobile = fields.Char('Mobile', size=64, states=STATES)
    active = fields.Boolean('Active')
    sequence = fields.Integer("Sequence")

    def __init__(self):
        super(Address, self).__init__()
        self._order.insert(0, ('party', 'ASC'))
        self._order.insert(1, ('sequence', 'ASC'))
        self._order.insert(2, ('id', 'ASC'))
        self._error_messages.update({
            'write_party': 'You can not modify the party of an address!',
            })

    def default_active(self, cursor, user, context=None):
        return 1

    def name_get(self, cursor, user, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []
        for address in self.browse(cursor, user, ids, context):
            res.append((address.id, ", ".join(x for x in [address.name,
                address.party.name, address.zip, address.city] if x)))
        return res

    def name_search(self, cursor, user, name, args=None, operator='ilike',
                    context=None, limit=None):
        if not args:
            args=[]

        ids = self.search(cursor, user, [('zip', '=', name)] + args,
                          limit=limit, context=context)
        if not ids:
            ids = self.search(cursor, user, [('city', operator, name)] + args,
                              limit=limit, context=context)
        if name:
            ids += self.search(cursor, user, [('name', operator, name)] + args,
                               limit=limit, context=context)
            ids += self.search(cursor, user, [('party', operator, name)] + args,
                               limit=limit, context=context)
        return self.name_get(cursor, user, ids, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if 'party' in vals:
            if isinstance(ids, (int, long)):
                ids = [ids]
            for address in self.browse(cursor, user, ids, context=context):
                if address.party.id != vals['party']:
                    self.raise_user_error(cursor, 'write_party',
                            context=context)
        return super(Address, self).write(cursor, user, ids, vals,
                context=context)

Address()
