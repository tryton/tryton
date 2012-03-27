#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
'Address'
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval, If
from trytond.pool import Pool

STATES = {
    'readonly': ~Eval('active'),
    }
DEPENDS = ['active']


class Address(ModelSQL, ModelView):
    "Address"
    _name = 'party.address'
    _description = __doc__
    party = fields.Many2One('party.party', 'Party', required=True,
        ondelete='CASCADE', select=True,  states={
            'readonly': If(~Eval('active'), True, Eval('id', 0) > 0),
            },
        depends=['active', 'id'])
    name = fields.Char('Name', states=STATES, depends=DEPENDS)
    street = fields.Char('Street', states=STATES, depends=DEPENDS)
    streetbis = fields.Char('Street (bis)', states=STATES, depends=DEPENDS)
    zip = fields.Char('Zip', states=STATES, depends=DEPENDS)
    city = fields.Char('City', states=STATES, depends=DEPENDS)
    country = fields.Many2One('country.country', 'Country',
        on_change=['country', 'subdivision'], states=STATES, depends=DEPENDS)
    subdivision = fields.Many2One("country.subdivision",
            'Subdivision', domain=[('country', '=', Eval('country'))],
            states=STATES, depends=['active', 'country'])
    active = fields.Boolean('Active')
    sequence = fields.Integer("Sequence", required=True)
    full_address = fields.Function(fields.Text('Full Address'),
            'get_full_address')

    def __init__(self):
        super(Address, self).__init__()
        self._order.insert(0, ('party', 'ASC'))
        self._order.insert(1, ('sequence', 'ASC'))
        self._error_messages.update({
            'write_party': 'You can not modify the party of an address!',
            })

    def default_active(self):
        return True

    def get_full_address(self, ids, name):
        if not ids:
            return {}
        res = {}
        for address in self.browse(ids):
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

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        for address in self.browse(ids):
            res[address.id] = ", ".join(x for x in [address.name,
                address.party.rec_name, address.zip, address.city] if x)
        return res

    def search_rec_name(self, name, clause):
        ids = self.search(['OR',
            ('zip',) + clause[1:],
            ('city',) + clause[1:],
            ('name',) + clause[1:],
            ], order=[])
        if ids:
            return [('id', 'in', ids)]
        return [('party',) + clause[1:]]

    def write(self, ids, vals):
        if 'party' in vals:
            if isinstance(ids, (int, long)):
                ids = [ids]
            for address in self.browse(ids):
                if address.party.id != vals['party']:
                    self.raise_user_error('write_party')
        return super(Address, self).write(ids, vals)

    def on_change_country(self, vals):
        subdivision_obj = Pool().get('country.subdivision')
        result = dict((k, vals.get(k))
            for k in ('country', 'subdivision'))
        if vals['subdivision']:
            subdivision = subdivision_obj.browse(vals['subdivision'])
            if subdivision.country.id != vals['country']:
                result['subdivision'] = None
        return result

Address()
