#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
'Address'
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.backend import TableHandler

__all__ = ['Address']

STATES = {
    'readonly': ~Eval('active'),
    }
DEPENDS = ['active']


class Address(ModelSQL, ModelView):
    "Address"
    __name__ = 'party.address'
    party = fields.Many2One('party.party', 'Party', required=True,
        ondelete='CASCADE', select=True, states={
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
    sequence = fields.Integer("Sequence",
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s')
    full_address = fields.Function(fields.Text('Full Address'),
            'get_full_address')

    @classmethod
    def __setup__(cls):
        super(Address, cls).__setup__()
        cls._order.insert(0, ('party', 'ASC'))
        cls._order.insert(1, ('sequence', 'ASC'))
        cls._error_messages.update({
                'write_party': 'You can not modify the party of address "%s".',
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        super(Address, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @staticmethod
    def default_active():
        return True

    def get_full_address(self, name):
        full_address = ''
        if self.name:
            full_address = self.name
        if self.street:
            if full_address:
                full_address += '\n'
            full_address += self.street
        if self.streetbis:
            if full_address:
                full_address += '\n'
            full_address += self.streetbis
        if self.zip or self.city:
            if full_address:
                full_address += '\n'
            if self.zip:
                full_address += self.zip
            if self.city:
                if full_address[-1:] != '\n':
                    full_address += ' '
                full_address += self.city
        if self.country or self.subdivision:
            if full_address:
                full_address += '\n'
            if self.subdivision:
                full_address += self.subdivision.name
            if self.country:
                if full_address[-1:] != '\n':
                    full_address += ' '
                full_address += self.country.name
        return full_address

    def get_rec_name(self, name):
        return ", ".join(x for x in [self.name,
                self.party.rec_name, self.zip, self.city] if x)

    @classmethod
    def search_rec_name(cls, name, clause):
        addresses = cls.search(['OR',
                ('zip',) + clause[1:],
                ('city',) + clause[1:],
                ('name',) + clause[1:],
                ], order=[])
        if addresses:
            return [('id', 'in', [address.id for address in addresses])]
        return [('party',) + clause[1:]]

    @classmethod
    def write(cls, addresses, vals):
        if 'party' in vals:
            for address in addresses:
                if address.party.id != vals['party']:
                    cls.raise_user_error('write_party', (address.rec_name,))
        super(Address, cls).write(addresses, vals)

    def on_change_country(self):
        if (self.subdivision
                and self.subdivision.country != self.country):
            return {'subdivision': None}
        return {}
