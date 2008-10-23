#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
'Address'
from trytond.osv import fields, OSV

STATES = {
    'readonly': "active == False",
}


class Address(OSV):
    "Address"
    _name = 'party.address'
    _description = __doc__
    party = fields.Many2One('party.party', 'Party', required=True,
           ondelete='cascade', select=1,  states=STATES)
    name = fields.Char('Name', states=STATES)
    street = fields.Char('Street', states=STATES)
    streetbis = fields.Char('Street (bis)', states=STATES)
    zip = fields.Char('Zip', change_default=True,
           states=STATES)
    city = fields.Char('City', states=STATES)
    country = fields.Many2One('country.country', 'Country',
           states=STATES)
    subdivision = fields.Many2One("country.subdivision",
            'Subdivision', domain="[('country', '=', country)]", states=STATES)
    active = fields.Boolean('Active')
    sequence = fields.Integer("Sequence")
    full_address = fields.Function('get_full_address', type='text')

    def __init__(self):
        super(Address, self).__init__()
        self._order.insert(0, ('party', 'ASC'))
        self._order.insert(1, ('sequence', 'ASC'))
        self._error_messages.update({
            'write_party': 'You can not modify the party of an address!',
            })

    def default_active(self, cursor, user, context=None):
        return True

    def get_full_address(self, cursor, user, ids, name, arg, context=None):
        if not ids:
            return []
        res = {}
        for address in self.browse(cursor, user, ids, context=context):
            res[address.id] = ''
            if address.name:
                res[address.id] += address.name
            if address.street:
                if res[address.id]:
                    res[address.id] += '\n'
                res[address.id] += address.street
            if address.streetbis:
                if res[address.id]:
                    res[address.id] += '\n'
                res[address.id] += address.streetbis
            if address.zip or address.city:
                if res[address.id]:
                    res[address.id] += '\n'
                res[address.id] += address.zip or '' +  ' ' + address.city or ''
            if address.country or address.subdivision:
                if res[address.id]:
                    res[address.id] += '\n'
                if address.subdivision:
                    res[address.id] += ' ' + address.subdivision.name
                if address.country:
                    res[address.id] += address.country.name
        return res

    def name_get(self, cursor, user, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []
        for address in self.browse(cursor, user, ids, context=context):
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
