# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
'Address'
from string import Template

from sql import Literal
from sql.functions import Substring
from sql.operators import Equal

from trytond.cache import Cache
from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, Exclude, MatchMixin, ModelSQL, ModelView, fields,
    sequence_ordered)
from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.pyson import Eval, If
from trytond.rpc import RPC
from trytond.transaction import Transaction

from .contact_mechanism import _ContactMechanismMixin
from .exceptions import InvalidFormat


class Address(
        DeactivableMixin, sequence_ordered(), _ContactMechanismMixin,
        ModelSQL, ModelView):
    "Address"
    __name__ = 'party.address'
    party = fields.Many2One(
        'party.party', "Party", required=True, ondelete='CASCADE',
        states={
            'readonly': Eval('id', 0) > 0,
            })
    party_name = fields.Char(
        "Party Name",
        help="If filled, replace the name of the party for address formatting")
    name = fields.Char("Building Name")
    street = fields.Text("Street")
    street_single_line = fields.Function(
        fields.Char("Street"),
        'on_change_with_street_single_line',
        searcher='search_street_single_line')
    postal_code = fields.Char("Postal Code")
    city = fields.Char("City")
    country = fields.Many2One('country.country', "Country")
    subdivision_types = fields.Function(
        fields.MultiSelection(
            'get_subdivision_types', "Subdivision Types"),
        'on_change_with_subdivision_types')
    subdivision = fields.Many2One("country.subdivision",
        'Subdivision',
        domain=[
            ('country', '=', Eval('country', -1)),
            If(Eval('subdivision_types', []),
                ('type', 'in', Eval('subdivision_types', [])),
                ()
                ),
            ])
    full_address = fields.Function(fields.Text('Full Address'),
            'get_full_address')
    identifiers = fields.One2Many(
        'party.identifier', 'address', "Identifiers",
        domain=[
            ('party', '=', Eval('party')),
            ('type', 'in', ['fr_siret']),
            ])
    contact_mechanisms = fields.One2Many(
        'party.contact_mechanism', 'address', "Contact Mechanisms",
        domain=[
            ('party', '=', Eval('party', -1)),
            ])

    @classmethod
    def __setup__(cls):
        super(Address, cls).__setup__()
        cls._order.insert(0, ('party', 'ASC'))
        cls.__rpc__.update(
            autocomplete_postal_code=RPC(instantiate=0, cache=dict(days=1)),
            autocomplete_city=RPC(instantiate=0, cache=dict(days=1)),
            )

    @classmethod
    def __register__(cls, module_name):
        table = cls.__table_handler__(module_name)

        # Migration from 5.8: rename zip to postal code
        table.column_rename('zip', 'postal_code')

        super(Address, cls).__register__(module_name)

    @fields.depends('street')
    def on_change_with_street_single_line(self, name=None):
        if self.street:
            return " ".join(self.street.splitlines())

    @classmethod
    def search_street_single_line(cls, name, domain):
        return [('street',) + tuple(domain[1:])]

    _autocomplete_limit = 100

    @fields.depends('country', 'subdivision')
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
        PostalCode = pool.get('country.postal_code')
        if domain:
            records = PostalCode.search(domain, limit=self._autocomplete_limit)
            if len(records) < self._autocomplete_limit:
                return sorted({getattr(z, name) for z in records})
        return []

    @fields.depends('city', methods=['_autocomplete_domain'])
    def autocomplete_postal_code(self):
        domain = self._autocomplete_domain()
        if self.city:
            domain.append(('city', 'ilike', '%%%s%%' % self.city))
        return self._autocomplete_search(domain, 'postal_code')

    @fields.depends('postal_code', methods=['_autocomplete_domain'])
    def autocomplete_city(self):
        domain = self._autocomplete_domain()
        if self.postal_code:
            domain.append(('postal_code', 'ilike', '%s%%' % self.postal_code))
        return self._autocomplete_search(domain, 'city')

    def get_full_address(self, name):
        pool = Pool()
        AddressFormat = pool.get('party.address.format')
        full_address = Template(AddressFormat.get_format(self)).substitute(
            **self._get_address_substitutions())
        return '\n'.join(
            filter(None, (x.strip() for x in full_address.splitlines())))

    def _get_address_substitutions(self):
        pool = Pool()
        Country = pool.get('country.country')

        context = Transaction().context
        subdivision_code = ''
        if getattr(self, 'subdivision', None):
            subdivision_code = self.subdivision.code or ''
            if '-' in subdivision_code:
                subdivision_code = subdivision_code.split('-', 1)[1]
        country_name = ''
        if getattr(self, 'country', None):
            with Transaction().set_context(language='en'):
                country_name = Country(self.country.id).name
        substitutions = {
            'party_name': '',
            'attn': '',
            'name': getattr(self, 'name', None) or '',
            'street': getattr(self, 'street', None) or '',
            'postal_code': getattr(self, 'postal_code', None) or '',
            'city': getattr(self, 'city', None) or '',
            'subdivision': (self.subdivision.name
                if getattr(self, 'subdivision', None) else ''),
            'subdivision_code': subdivision_code,
            'country': country_name,
            'country_code': (self.country.code or ''
                if getattr(self, 'country', None) else ''),
            }
        # Keep zip for backward compatibility
        substitutions['zip'] = substitutions['postal_code']
        if context.get('address_from_country') == getattr(self, 'country', ''):
            substitutions['country'] = ''
        if context.get('address_with_party', False):
            substitutions['party_name'] = self.party_full_name
        if context.get('address_attention_party', False):
            substitutions['attn'] = (
                context['address_attention_party'].full_name)
        for key, value in list(substitutions.items()):
            substitutions[key.upper()] = value.upper()
        return substitutions

    @property
    def party_full_name(self):
        name = ''
        if self.party_name:
            name = self.party_name
        elif self.party:
            name = self.party.full_name
        return name

    def get_rec_name(self, name):
        party = self.party_full_name
        if self.street_single_line:
            street = self.street_single_line
        else:
            street = None
        if self.country:
            country = self.country.code
        else:
            country = None
        return ', '.join(
            filter(None, [
                    party,
                    self.name,
                    street,
                    self.postal_code,
                    self.city,
                    country]))

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('party',) + tuple(clause[1:]),
            ('name',) + tuple(clause[1:]),
            ('street',) + tuple(clause[1:]),
            ('postal_code',) + tuple(clause[1:]),
            ('city',) + tuple(clause[1:]),
            ('country',) + tuple(clause[1:]),
            ]

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        for addresses, values in zip(actions, actions):
            if 'party' in values:
                for address in addresses:
                    if address.party.id != values['party']:
                        raise AccessError(
                            gettext('party.msg_address_change_party',
                                address=address.rec_name))
        super(Address, cls).write(*args)

    @fields.depends('subdivision', 'country')
    def on_change_country(self):
        if (self.subdivision
                and self.subdivision.country != self.country):
            self.subdivision = None

    @classmethod
    def get_subdivision_types(cls):
        pool = Pool()
        Subdivision = pool.get('country.subdivision')
        selection = Subdivision.fields_get(['type'])['type']['selection']
        return [(k, v) for k, v in selection if k is not None]

    @fields.depends('country')
    def on_change_with_subdivision_types(self, name=None):
        pool = Pool()
        Types = pool.get('party.address.subdivision_type')
        return Types.get_types(self.country)

    def contact_mechanism_get(self, types=None, usage=None):
        mechanism = super().contact_mechanism_get(types=types, usage=usage)
        if mechanism is None:
            mechanism = self.party.contact_mechanism_get(
                types=types, usage=usage)
        return mechanism


class AddressFormat(DeactivableMixin, MatchMixin, ModelSQL, ModelView):
    "Address Format"
    __name__ = 'party.address.format'
    country_code = fields.Char("Country Code", size=2)
    language_code = fields.Char("Language Code", size=2)
    format_ = fields.Text("Format", required=True,
        help="Available variables (also in upper case):\n"
        "- ${party_name}\n"
        "- ${name}\n"
        "- ${attn}\n"
        "- ${street}\n"
        "- ${postal_code}\n"
        "- ${city}\n"
        "- ${subdivision}\n"
        "- ${subdivision_code}\n"
        "- ${country}\n"
        "- ${country_code}")

    _get_format_cache = Cache('party.address.format.get_format')

    @classmethod
    def __setup__(cls):
        super(AddressFormat, cls).__setup__()
        cls._order.insert(0, ('country_code', 'ASC NULLS LAST'))
        cls._order.insert(1, ('language_code', 'ASC NULLS LAST'))

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Country = pool.get('country.country')
        Language = pool.get('ir.lang')
        country = Country.__table__()
        language = Language.__table__()
        table = cls.__table__()
        cursor = Transaction().connection.cursor()

        super().__register__(module_name)

        table_h = cls.__table_handler__()

        # Migration from 5.2: replace country by country_code
        if table_h.column_exist('country'):
            query = table.update(
                [table.country_code],
                country.select(
                    country.code,
                    where=country.id == table.country))
            cursor.execute(*query)
            table_h.drop_column('country')

        # Migration from 5.2: replace language by language_code
        if table_h.column_exist('language'):
            query = table.update(
                [table.language_code],
                language.select(
                    Substring(language.code, 0, 2),
                    where=language.id == table.language))
            cursor.execute(*query)
            table_h.drop_column('language')

    @classmethod
    def default_format_(cls):
        return """${attn}
${party_name}
${name}
${street}
${postal_code} ${city}
${subdivision}
${COUNTRY}"""

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
    def validate_fields(cls, formats, field_names):
        super().validate_fields(formats, field_names)
        cls.check_format(formats, field_names)

    @classmethod
    def check_format(cls, formats, field_names=None):
        pool = Pool()
        Address = pool.get('party.address')
        if field_names and 'format_' not in field_names:
            return
        address = Address()
        substitutions = address._get_address_substitutions()
        for format_ in formats:
            try:
                Template(format_.format_).substitute(**substitutions)
            except Exception as exception:
                raise InvalidFormat(gettext('party.invalid_format',
                        format=format_.format_,
                        exception=exception)) from exception

    @classmethod
    def get_format(cls, address, pattern=None):
        if pattern is None:
            pattern = {}
        else:
            pattern = pattern.copy()
        pattern.setdefault(
            'country_code', address.country.code if address.country else None)
        pattern.setdefault('language_code', Transaction().language[:2])

        key = tuple(sorted(pattern.items()))
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


class SubdivisionType(DeactivableMixin, ModelSQL, ModelView):
    "Address Subdivision Type"
    __name__ = 'party.address.subdivision_type'
    country_code = fields.Char("Country Code", size=2, required=True)
    types = fields.MultiSelection('get_subdivision_types', "Subdivision Types")
    _get_types_cache = Cache('party.address.subdivision_type.get_types')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('country_code_unique',
                Exclude(t, (t.country_code, Equal),
                    where=t.active == Literal(True)),
                'party.msg_address_subdivision_country_code_unique')
            ]
        cls._order.insert(0, ('country_code', 'ASC NULLS LAST'))

    @classmethod
    def get_subdivision_types(cls):
        pool = Pool()
        Subdivision = pool.get('country.subdivision')
        selection = Subdivision.fields_get(['type'])['type']['selection']
        return [(k, v) for k, v in selection if k is not None]

    @classmethod
    def create(cls, *args, **kwargs):
        records = super().create(*args, **kwargs)
        cls._get_types_cache.clear()
        return records

    @classmethod
    def write(cls, *args, **kwargs):
        super().write(*args, **kwargs)
        cls._get_types_cache.clear()

    @classmethod
    def delete(cls, *args, **kwargs):
        super().delete(*args, **kwargs)
        cls._get_types_cache.clear()

    @classmethod
    def get_types(cls, country):
        key = country.code if country else None
        types = cls._get_types_cache.get(key)
        if types is not None:
            return list(types)

        records = cls.search([
                ('country_code', '=', country.code if country else None),
                ])
        if records:
            record, = records
            types = record.types
        else:
            types = []

        cls._get_types_cache.set(key, types)
        return types
