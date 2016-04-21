# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
'Address'
from sql import Null
from sql.conditionals import Case

from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval, If
from trytond import backend
from trytond.pool import Pool

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
        states=STATES, depends=DEPENDS)
    subdivision = fields.Many2One("country.subdivision",
            'Subdivision', domain=[('country', '=', Eval('country'))],
            states=STATES, depends=['active', 'country'])
    active = fields.Boolean('Active')
    sequence = fields.Integer("Sequence")
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
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        super(Address, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [Case((table.sequence == Null, 0), else_=1), table.sequence]

    @staticmethod
    def default_active():
        return True

    _autocomplete_limit = 100

    def _autocomplete_domain(self):
        domain = []
        if self.country:
            domain.append(('country', '=', self.country.id))
        if self.subdivision:
            domain.append(['OR',
                    ('subdivision', '=', self.subdivision.id),
                    ('subdivision', '=', None),
                    ])
        return domain

    def _autocomplete_search(self, domain, name):
        pool = Pool()
        Zip = pool.get('country.zip')
        if domain:
            records = Zip.search(domain, limit=self._autocomplete_limit)
            if len(records) < self._autocomplete_limit:
                return sorted({getattr(z, name) for z in records})
        return []

    @fields.depends('city', 'country', 'subdivision')
    def autocomplete_zip(self):
        domain = self._autocomplete_domain()
        if self.city:
            domain.append(('city', 'ilike', '%%%s%%' % self.city))
        return self._autocomplete_search(domain, 'zip')

    @fields.depends('zip', 'country', 'subdivision')
    def autocomplete_city(self):
        domain = self._autocomplete_domain()
        if self.zip:
            domain.append(('zip', 'ilike', '%s%%' % self.zip))
        return self._autocomplete_search(domain, 'city')

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
        if self.subdivision:
            if full_address:
                full_address += '\n'
            full_address += self.subdivision.name
        if self.country:
            if full_address:
                full_address += '\n'
            full_address += self.country.name.upper()
        return full_address

    def get_rec_name(self, name):
        return ", ".join(x for x in [self.name,
                self.party.rec_name, self.zip, self.city] if x)

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('zip',) + tuple(clause[1:]),
            ('city',) + tuple(clause[1:]),
            ('name',) + tuple(clause[1:]),
            ('party',) + tuple(clause[1:]),
            ]

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        for addresses, values in zip(actions, actions):
            if 'party' in values:
                for address in addresses:
                    if address.party.id != values['party']:
                        cls.raise_user_error(
                            'write_party', (address.rec_name,))
        super(Address, cls).write(*args)

    @fields.depends('subdivision', 'country')
    def on_change_country(self):
        if (self.subdivision
                and self.subdivision.country != self.country):
            self.subdivision = None
