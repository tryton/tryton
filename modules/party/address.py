# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
'Address'
import re
from string import Template

from sql import Literal
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
    __name__ = 'party.address'
    party = fields.Many2One(
        'party.party', "Party", required=True, ondelete='CASCADE',
        states={
            'readonly': Eval('id', 0) > 0,
            })
    party_name = fields.Char(
        "Party Name",
        help="If filled, replace the name of the party for address formatting")

    street = fields.Function(fields.Text(
            "Street",
            states={
                'readonly': (
                    Eval('street_name')
                    | Eval('building_number')
                    | Eval('unit_number')
                    | Eval('floor_number')
                    | Eval('room_number')
                    | Eval('post_box')
                    | Eval('post_office')
                    | Eval('private_bag')),
                }),
        'on_change_with_street', setter='set_street', searcher='search_street')
    street_unstructured = fields.Text(
        "Street",
        states={
            'invisible': (
                (Eval('street_name')
                    | Eval('building_number')
                    | Eval('unit_number')
                    | Eval('floor_number')
                    | Eval('room_number')
                    | Eval('post_box')
                    | Eval('post_office')
                    | Eval('private_bag'))
                & ~Eval('street_unstructured')),
            })

    street_name = fields.Char(
        "Street Name",
        states={
            'invisible': Eval('street_unstructured') & ~Eval('street_name'),
            })
    building_name = fields.Char(
        "Building Name",
        states={
            'invisible': Eval('street_unstructured') & ~Eval('building_name'),
            })
    building_number = fields.Char(
        "Building Number",
        states={
            'invisible': (
                Eval('street_unstructured') & ~Eval('building_number')),
            })
    unit_number = fields.Char(
        "Unit Number",
        states={
            'invisible': Eval('street_unstructured') & ~Eval('unit_number'),
            })
    floor_number = fields.Char(
        "Floor Number",
        states={
            'invisible': Eval('street_unstructured') & ~Eval('floor_number'),
            })
    room_number = fields.Char(
        "Room Number",
        states={
            'invisible': Eval('street_unstructured') & ~Eval('room_number'),
            })

    post_box = fields.Char(
        "Post Box",
        states={
            'invisible': Eval('street_unstructured') & ~Eval('post_box'),
            })
    private_bag = fields.Char(
        "Private Bag",
        states={
            'invisible': Eval('street_unstructured') & ~Eval('private_bag'),
            })
    post_office = fields.Char(
        "Post Office",
        states={
            'invisible': Eval('street_unstructured') & ~Eval('post_office'),
            })

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
        'party.identifier', 'address', "Identifiers")
    contact_mechanisms = fields.One2Many(
        'party.contact_mechanism', 'address', "Contact Mechanisms",
        domain=[
            ('party', '=', Eval('party', -1)),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('party')
        cls._order.insert(0, ('party', 'ASC'))
        cls.__rpc__.update(
            autocomplete_postal_code=RPC(instantiate=0, cache=dict(days=1)),
            autocomplete_city=RPC(instantiate=0, cache=dict(days=1)),
            )
        cls.identifiers.domain = [
            ('party', '=', Eval('party', -1)),
            ('type', 'in', list(cls._type_identifiers())),
            ]

    @classmethod
    def __register__(cls, module_name):
        table = cls.__table_handler__(module_name)

        # Migration from 7.4: rename street to street_unstructured
        # and name to building_name
        table.column_rename('street', 'street_unstructured')
        table.column_rename('name', 'building_name')

        super().__register__(module_name)

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
        domain = [
            self._autocomplete_domain(),
            ('postal_code', 'not in', [None, '']),
            ]
        if self.city:
            domain.append(('city', 'ilike', '%%%s%%' % self.city))
        return self._autocomplete_search(domain, 'postal_code')

    @fields.depends('postal_code', methods=['_autocomplete_domain'])
    def autocomplete_city(self):
        domain = [
            self._autocomplete_domain(),
            ('city', 'not in', [None, '']),
            ]
        if self.postal_code:
            domain.append(('postal_code', 'ilike', '%s%%' % self.postal_code))
        return self._autocomplete_search(domain, 'city')

    def get_full_address(self, name):
        pool = Pool()
        AddressFormat = pool.get('party.address.format')
        full_address = Template(AddressFormat.get_format(self)).substitute(
            **self._get_address_substitutions())
        return self._strip(full_address)

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
        substitutions.update(self._get_street_substitutions())
        return substitutions

    @fields.depends('street', 'street_unstructured')
    def on_change_street(self):
        self.street_unstructured = self.street

    @fields.depends(
        'street_unstructured', 'country',
        methods=['_get_street_substitutions'])
    def on_change_with_street(self, name=None):
        pool = Pool()
        AddressFormat = pool.get('party.address.format')

        format_ = AddressFormat.get_street_format(self)
        street = Template(format_).substitute(
            **self._get_street_substitutions())
        if not (street := self._strip(street, doublespace=True)):
            street = self.street_unstructured
        return street

    @classmethod
    def set_street(cls, addresses, name, value):
        addresses = [a for a in addresses if a.street != value]
        cls.write(addresses, {
                'street_unstructured': value,
                'street_name': None,
                'building_name': None,
                'building_number': None,
                'unit_number': None,
                'floor_number': None,
                'room_number': None,
                })

    @classmethod
    def search_street(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('street_unstructured', *clause[1:]),
            ('street_name', *clause[1:]),
            ('building_name', *clause[1:]),
            ('building_number', *clause[1:]),
            ('unit_number', *clause[1:]),
            ('floor_number', *clause[1:]),
            ('room_number', *clause[1:]),
            ]

    @property
    def numbers(self):
        pool = Pool()
        AddressFormat = pool.get('party.address.format')

        format_ = AddressFormat.get_street_format(self)
        substitutions = {
            k: v if k.lower().endswith('_number') else ''
            for k, v in self._get_street_substitutions().items()}
        numbers = Template(format_).substitute(**substitutions)
        return self._strip(numbers, doublespace=True)

    @fields.depends(
        'country', 'street_name', 'building_number', 'unit_number',
        'floor_number', 'room_number', 'post_box', 'private_bag',
        'post_office')
    def _get_street_substitutions(self):
        pool = Pool()
        AddressFormat = pool.get('party.address.format')

        substitutions = {
            'street_name': getattr(self, 'street_name', None) or '',
            'building_name': getattr(self, 'building_name', None) or '',
            'building_number': getattr(self, 'building_number', None) or '',
            'unit_number': getattr(self, 'unit_number', None) or '',
            'floor_number': getattr(self, 'floor_number', None) or '',
            'room_number': getattr(self, 'room_number', None) or '',
            'post_box': getattr(self, 'post_box', None) or '',
            'private_bag': getattr(self, 'private_bag', None) or '',
            'post_office': getattr(self, 'post_office', None) or '',
            }
        for number in [
                'building_number',
                'unit_number',
                'floor_number',
                'room_number',
                'post_box',
                'private_bag',
                'post_office',
                ]:
            if (substitutions[number]
                    and (format_ := AddressFormat.get_number_format(
                            number, self))):
                substitutions[number] = format_.format(substitutions[number])
        for key, value in list(substitutions.items()):
            substitutions[key.upper()] = value.upper()
        return substitutions

    @classmethod
    def _type_identifiers(cls):
        return {'fr_siret'}

    @classmethod
    def _strip(cls, value, doublespace=False):
        value = re.sub(
            r'[\,\/,–][\s,\,\/]*([\,\/,–])', r'\1', value, flags=re.MULTILINE)
        if doublespace:
            value = re.sub(r' {1,}', r' ', value, flags=re.MULTILINE)
        value = value.splitlines()
        value = map(lambda x: x.strip(' ,/–'), value)
        return '\n'.join(filter(None, value))

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
            ('street',) + tuple(clause[1:]),
            ('postal_code',) + tuple(clause[1:]),
            ('city',) + tuple(clause[1:]),
            ('country',) + tuple(clause[1:]),
            ]

    @classmethod
    def check_modification(cls, mode, addresses, values=None, external=False):
        super().check_modification(
            mode, addresses, values=values, external=external)
        if mode == 'write' and 'party' in values:
            for address in addresses:
                if address.party.id != values['party']:
                    raise AccessError(gettext(
                            'party.msg_address_change_party',
                            address=address.rec_name))

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
    __name__ = 'party.address.format'
    country_code = fields.Char("Country Code", size=2)
    language_code = fields.Char("Language Code", size=2)
    format_ = fields.Text("Format", required=True,
        help="Available variables (also in upper case and street variables):\n"
        "- ${party_name}\n"
        "- ${attn}\n"
        "- ${street}\n"
        "- ${postal_code}\n"
        "- ${city}\n"
        "- ${subdivision}\n"
        "- ${subdivision_code}\n"
        "- ${country}\n"
        "- ${country_code}")
    street_format = fields.Text("Street Format", required=True,
        help="Available variables (also in upper case):\n"
        "- ${street_name}\n"
        "- ${building_name}\n"
        "- ${building_number}\n"
        "- ${unit_number}\n"
        "- ${floor_number}\n"
        "- ${room_number}\n"
        "- ${post_box}\n"
        "- ${private_bag}\n"
        "- ${post_office}\n")
    building_number_format = fields.Char(
        "Building Number Format",
        help="Use {} as placeholder for the building number.")
    unit_number_format = fields.Char(
        "Unit Number Format",
        help="Use {} as placeholder for the unit number.")
    floor_number_format = fields.Char(
        "Floor Number Format",
        help="Use {} as placeholder for the floor number.")
    room_number_format = fields.Char(
        "Room Number Format",
        help="Use {} as placeholder for the room number.")

    post_box_format = fields.Char(
        "Post Box Format",
        help="Use {} as placeholder for the post box.")
    private_bag_format = fields.Char(
        "Private Bag Format",
        help="Use {} as placeholder for the private bag.")
    post_office_format = fields.Char(
        "Post Office Format",
        help="Use {} as placeholder for the post office.")

    _get_format_cache = Cache('party.address.format.get_format')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('country_code', 'ASC NULLS LAST'))
        cls._order.insert(1, ('language_code', 'ASC NULLS LAST'))

    @classmethod
    def default_format_(cls):
        return """${attn}
${party_name}
${street}
${postal_code} ${city}
${subdivision}
${COUNTRY}"""

    @classmethod
    def on_modification(cls, mode, formats, field_names=None):
        super().on_modification(mode, formats, field_names=field_names)
        cls._get_format_cache.clear()

    @classmethod
    def default_street_format(cls):
        return (
            "${street_name} ${building_name} ${building_number}"
            "/${unit_number}/${floor_number}/${room_number}\n"
            "${post_box} ${private_bag} ${post_office}")

    @classmethod
    def validate_fields(cls, formats, field_names):
        super().validate_fields(formats, field_names)
        cls.check_format(formats, field_names)
        cls.check_street_format(formats, field_names)
        cls.check_number_format(formats, field_names)

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
                raise InvalidFormat(gettext('party.msg_invalid_format',
                        format=format_.format_,
                        exception=exception)) from exception

    @classmethod
    def check_street_format(cls, formats, field_names=None):
        pool = Pool()
        Address = pool.get('party.address')
        if field_names and 'street_format' not in field_names:
            return
        address = Address()
        substitutions = address._get_street_substitutions()
        for format_ in formats:
            try:
                Template(format_.street_format).substitute(**substitutions)
            except Exception as exception:
                raise InvalidFormat(gettext('party.msg_invalid_format',
                        format=format_.street_format,
                        exception=exception)) from exception

    @classmethod
    def check_number_format(cls, formats, field_names=None):
        fields = [
            'building_number_format', 'floor_number_format',
            'unit_number_format', 'room_number_format',
            'post_box_format', 'private_bag_format', 'post_office_format']
        if field_names and not (field_names & set(fields)):
            return
        for format_ in formats:
            for field in fields:
                if number_format := getattr(format_, field):
                    try:
                        number_format.format('')
                    except Exception as exception:
                        raise InvalidFormat(gettext('party.msg_invalid_format',
                                format=number_format,
                                exception=exception)) from exception

    @classmethod
    def get_format(cls, address, pattern=None):
        return cls._get_format('format_', address, pattern=pattern)

    @classmethod
    def get_street_format(cls, address, pattern=None):
        return cls._get_format('street_format', address, pattern=pattern)

    @classmethod
    def get_number_format(cls, number, address, pattern=None):
        return cls._get_format(f'{number}_format', address, pattern=pattern)

    @classmethod
    def _get_format(cls, field, address, pattern=None):
        if pattern is None:
            pattern = {}
        else:
            pattern = pattern.copy()
        pattern.setdefault(
            'country_code', address.country.code if address.country else None)
        pattern.setdefault('language_code', Transaction().language[:2])

        key = (field, *sorted(pattern.items()))
        format_ = cls._get_format_cache.get(key)
        if format_ is not None:
            return format_

        for record in cls.search([]):
            if record.match(pattern):
                format_ = getattr(record, field)
                break
        else:
            format_ = getattr(cls, f'default_{field}', lambda: '')()

        cls._get_format_cache.set(key, format_)
        return format_


class SubdivisionType(DeactivableMixin, ModelSQL, ModelView):
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

    @classmethod
    def on_modification(cls, mode, types, field_names=None):
        super().on_modification(mode, types, field_names=field_names)
        cls._get_types_cache.clear()
