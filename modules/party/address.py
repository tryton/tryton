#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
'Address'
from trytond.model import ModelView, ModelSQL, fields

STATES = {
    'readonly': "active == False",
}


class Address(ModelSQL, ModelView):
    "Address"
    _name = 'party.address'
    _description = __doc__
    party = fields.Many2One('party.party', 'Party', required=True,
            ondelete='CASCADE', select=1,  states={
                'readonly': "(active == False) or (active_id > 0)",
            })
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
            return {}
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
                if address.zip:
                    res[address.id] += address.zip
                if address.city:
                    if res[address.id][-1:] != '\n':
                        res[address.id] += ' '
                    res[address.id] += address.city
            if address.country or address.subdivision:
                if res[address.id]:
                    res[address.id] += '\n'
                if address.subdivision:
                    res[address.id] += address.subdivision.name
                if address.country:
                    if res[address.id][-1:] != '\n':
                        res[address.id] += ' '
                    res[address.id] += address.country.name
        return res

    def get_rec_name(self, cursor, user, ids, name, arg, context=None):
        if not ids:
            return {}
        res = {}
        for address in self.browse(cursor, user, ids, context=context):
            res[address.id] = ", ".join(x for x in [address.name,
                address.party.rec_name, address.zip, address.city] if x)
        return res

    def search_rec_name(self, cursor, user, name, args, context=None):
        args2 = []
        i = 0
        while i < len(args):
            ids = self.search(cursor, user, ['OR',
                ('zip', '=', args[i][2]),
                ('city', '=', args[i][2]),
                ('name', args[i][1], args[i][2]),
                ], context=context)
            if ids:
                args2.append(('id', 'in', ids))
            else:
                args2.append(('party', args[i][1], args[i][2]))
            i += 1
        return args2

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
