# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
'Address'
from string import Template

from sql import Null
from sql.conditionals import Case, Coalesce
from sql.operators import Concat

from trytond.model import ModelView, ModelSQL, MatchMixin, fields, \
    sequence_ordered
from trytond.pyson import Eval, If
from trytond import backend
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.cache import Cache

__all__ = ['Address', 'AddressFormat']

STATES = {
    'readonly': ~Eval('active'),
    }
DEPENDS = ['active']


class Address(sequence_ordered(), ModelSQL, ModelView):
    "Address"
    __name__ = 'party.address'
    party = fields.Many2One('party.party', 'Party', required=True,
        ondelete='CASCADE', select=True, states={
            'readonly': If(~Eval('active'), True, Eval('id', 0) > 0),
            },
        depends=['active', 'id'])
    name = fields.Char("Building Name", states=STATES, depends=DEPENDS)
    street = fields.Text("Street", states=STATES, depends=DEPENDS)
    zip = fields.Char('Zip', states=STATES, depends=DEPENDS)
    city = fields.Char('City', states=STATES, depends=DEPENDS)
    country = fields.Many2One('country.country', 'Country',
        states=STATES, depends=DEPENDS)
    subdivision = fields.Many2One("country.subdivision",
        'Subdivision', domain=[
            ('country', '=', Eval('country', -1)),
            ('parent', '=', None),
            ],
        states=STATES, depends=['active', 'country'])
    active = fields.Boolean('Active')
    full_address = fields.Function(fields.Text('Full Address'),
            'get_full_address')

    @classmethod
    def __setup__(cls):
        super(Address, cls).__setup__()
        cls._order.insert(0, ('party', 'ASC'))
        cls._error_messages.update({
                'write_party': 'You can not modify the party of address "%s".',
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        table = TableHandler(cls, module_name)
        sql_table = cls.__table__()

        super(Address, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

        # Migration from 4.0: remove streetbis
        if table.column_exist('streetbis'):
            value = Concat(
                Coalesce(sql_table.street, ''),
                Concat('\n', Coalesce(sql_table.streetbis, '')))
            cursor.execute(*sql_table.update(
                    [sql_table.street],
                    [value]))
            table.drop_column('streetbis')

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
                    ('subdivision', 'child_of',
                        [self.subdivision.id], 'parent'),
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
        pool = Pool()
        AddressFormat = pool.get('party.address.format')
        full_address = Template(AddressFormat.get_format(self)).substitute(
            **self._get_address_substitutions())
        return '\n'.join(
            filter(None, (x.strip() for x in full_address.splitlines())))

    def _get_address_substitutions(self):
        context = Transaction().context
        substitutions = {
            'party_name': '',
            'name': self.name or '',
            'street': self.street or '',
            'zip': self.zip or '',
            'city': self.city or '',
            'subdivision': self.subdivision.name if self.subdivision else '',
            'subdivision_code': (self.subdivision.code.split('-', 1)[1]
                if self.subdivision else ''),
            'country': self.country.name if self.country else '',
            'country_code': self.country.code if self.country else '',
            }

        # Map invalid substitutions district* to subdivision* on 4.2.
        substitutions['district'] = substitutions['subdivision']
        substitutions['district_code'] = substitutions['subdivision_code']

        if context.get('address_from_country') == self.country:
            substitutions['country'] = ''
        if context.get('address_with_party', False):
            substitutions['party_name'] = self.party.full_name
        for key, value in substitutions.items():
            substitutions[key.upper()] = value.upper()
        return substitutions

    def get_rec_name(self, name):
        return ', '.join(
            filter(None, [self.party.rec_name, self.zip, self.city]))

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('zip',) + tuple(clause[1:]),
            ('city',) + tuple(clause[1:]),
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


class AddressFormat(MatchMixin, ModelSQL, ModelView):
    "Address Format"
    __name__ = 'party.address.format'
    country = fields.Many2One('country.country', "Country")
    language = fields.Many2One('ir.lang', "Language")
    active = fields.Boolean("Active")
    format_ = fields.Text("Format", required=True,
        help="Available variables (also in upper case):\n"
        "- ${party_name}\n"
        "- ${name}\n"
        "- ${street}\n"
        "- ${zip}\n"
        "- ${city}\n"
        "- ${subdivision}\n"
        "- ${subdivision_code}\n"
        "- ${country}\n"
        "- ${country_code}")

    _get_format_cache = Cache('party.address.format.get_format')

    @classmethod
    def __setup__(cls):
        super(AddressFormat, cls).__setup__()
        cls._order.insert(0, ('country', 'ASC'))
        cls._order.insert(1, ('language', 'ASC'))

    @classmethod
    def default_active(cls):
        return True

    @classmethod
    def default_format_(cls):
        return """${party_name}
${name}
${street}
${zip} ${city}
${subdivision}
${COUNTRY}"""

    @staticmethod
    def order_language(tables):
        table, _ = tables[None]
        return [Case((table.language == Null, 1), else_=0), table.language]

    @classmethod
    def create(cls, *args, **kwargs):
        records = super(AddressFormat, cls).create(*args, **kwargs)
        cls._get_format_cache.clear()
        return records

    @classmethod
    def write(cls, *args, **kwargs):
        super(AddressFormat, cls).write(*args, **kwargs)
        cls._get_format_cache.clear()

    @classmethod
    def delete(cls, *args, **kwargs):
        super(AddressFormat, cls).delete(*args, **kwargs)
        cls._get_format_cache.clear()

    @classmethod
    def get_format(cls, address, pattern=None):
        pool = Pool()
        Language = pool.get('ir.lang')

        if pattern is None:
            pattern = {}
        else:
            pattern = pattern.copy()
        pattern.setdefault(
            'country', address.country.id if address.country else None)

        languages = Language.search([
                ('code', '=', Transaction().language),
                ], limit=1)
        if languages:
            language, = languages
        else:
            language = None
        pattern.setdefault('language', language.id if language else None)

        key = tuple(sorted(pattern.iteritems()))
        format_ = cls._get_format_cache.get(key)
        if format_ is not None:
            return format_

        for record in cls.search([]):
            if record.match(pattern):
                format_ = record.format_
                break
        else:
            format_ = cls.default_format_()

        cls._get_format_cache.set(key, format_)
        return format_
