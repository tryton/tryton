# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import chain
try:
    import phonenumbers
    from phonenumbers import PhoneNumberFormat, NumberParseException
except ImportError:
    phonenumbers = None

from trytond.i18n import gettext
from trytond.model import (
    ModelView, ModelSQL, DeactivableMixin, fields, sequence_ordered)
from trytond.model.exceptions import AccessError
from trytond.pyson import Eval
from trytond.transaction import Transaction

from .exceptions import InvalidPhoneNumber

_TYPES = [
    ('phone', 'Phone'),
    ('mobile', 'Mobile'),
    ('fax', 'Fax'),
    ('email', 'E-Mail'),
    ('website', 'Website'),
    ('skype', 'Skype'),
    ('sip', 'SIP'),
    ('irc', 'IRC'),
    ('jabber', 'Jabber'),
    ('other', 'Other'),
]

_PHONE_TYPES = {
    'phone',
    'mobile',
    'fax',
    }


class ContactMechanism(
        DeactivableMixin, sequence_ordered(), ModelSQL, ModelView):
    "Contact Mechanism"
    __name__ = 'party.contact_mechanism'
    _rec_name = 'value'

    type = fields.Selection(_TYPES, "Type", required=True, sort=False)
    value = fields.Char("Value", select=True,
        # Add all function fields to ensure to always fill them via on_change
        depends=[
            'email', 'website', 'skype', 'sip', 'other_value',
            'value_compact'])
    value_compact = fields.Char('Value Compact', readonly=True)
    name = fields.Char("Name")
    comment = fields.Text("Comment")
    party = fields.Many2One(
        'party.party', "Party", required=True, ondelete='CASCADE', select=True)
    email = fields.Function(fields.Char('E-Mail', states={
        'invisible': Eval('type') != 'email',
        'required': Eval('type') == 'email',
        }, depends=['value', 'type']),
        'get_value', setter='set_value')
    website = fields.Function(fields.Char('Website', states={
        'invisible': Eval('type') != 'website',
        'required': Eval('type') == 'website',
        }, depends=['value', 'type']),
        'get_value', setter='set_value')
    skype = fields.Function(fields.Char('Skype', states={
        'invisible': Eval('type') != 'skype',
        'required': Eval('type') == 'skype',
        }, depends=['value', 'type']),
        'get_value', setter='set_value')
    sip = fields.Function(fields.Char('SIP', states={
        'invisible': Eval('type') != 'sip',
        'required': Eval('type') == 'sip',
        }, depends=['value', 'type']),
        'get_value', setter='set_value')
    other_value = fields.Function(fields.Char('Value', states={
        'invisible': Eval('type').in_(['email', 'website', 'skype', 'sip']),
        'required': ~Eval('type').in_(['email', 'website']),
        }, depends=['value', 'type']),
        'get_value', setter='set_value')
    url = fields.Function(fields.Char('URL', states={
                'invisible': ~Eval('url'),
                }),
        'on_change_with_url')

    @classmethod
    def __setup__(cls):
        super(ContactMechanism, cls).__setup__()
        cls._order.insert(0, ('party', 'ASC'))

    @staticmethod
    def default_type():
        return 'phone'

    @classmethod
    def default_party(cls):
        return Transaction().context.get('related_party')

    @classmethod
    def get_value(cls, mechanisms, names):
        return dict((name, dict((m.id, m.value) for m in mechanisms))
            for name in names)

    @fields.depends('type', 'value')
    def on_change_with_url(self, name=None, value=None):
        if value is None:
            value = self.value
        if self.type == 'email':
            return 'mailto:%s' % value
        elif self.type == 'website':
            return value
        elif self.type == 'skype':
            return 'callto:%s' % value
        elif self.type == 'sip':
            return 'sip:%s' % value
        elif self.type in {'phone', 'mobile'}:
            return 'tel:%s' % value
        elif self.type == 'fax':
            return 'fax:%s' % value
        return None

    @fields.depends('party', '_parent_party.addresses')
    def _phone_country_codes(self):
        if self.party:
            for address in self.party.addresses:
                if address.country:
                    yield address.country.code

    @fields.depends(methods=['_phone_country_codes'])
    def _parse_phonenumber(self, value):
        for country_code in chain(self._phone_country_codes(), [None]):
            try:
                # Country code is ignored if value has an international prefix
                return phonenumbers.parse(value, country_code)
            except NumberParseException:
                pass
        return None

    @fields.depends(methods=['_parse_phonenumber'])
    def format_value(self, value=None, type_=None):
        if phonenumbers and type_ in _PHONE_TYPES:
            phonenumber = self._parse_phonenumber(value)
            if phonenumber:
                value = phonenumbers.format_number(
                    phonenumber, PhoneNumberFormat.INTERNATIONAL)
        return value

    @fields.depends(methods=['_parse_phonenumber'])
    def format_value_compact(self, value=None, type_=None):
        if phonenumbers and type_ in _PHONE_TYPES:
            phonenumber = self._parse_phonenumber(value)
            if phonenumber:
                value = phonenumbers.format_number(
                    phonenumber, PhoneNumberFormat.E164)
        return value

    @classmethod
    def set_value(cls, mechanisms, name, value):
        #  Setting value is done by on_changes
        pass

    @fields.depends(
        methods=['on_change_with_url', 'format_value', 'format_value_compact'])
    def _change_value(self, value, type_):
        self.value = self.format_value(value=value, type_=type_)
        self.value_compact = self.format_value_compact(
            value=value, type_=type_)
        self.website = value
        self.email = value
        self.skype = value
        self.sip = value
        self.other_value = value
        self.url = self.on_change_with_url(value=value)

    @fields.depends('value', 'type', methods=['_change_value'])
    def on_change_value(self):
        return self._change_value(self.value, self.type)

    @fields.depends('website', 'type', methods=['_change_value'])
    def on_change_website(self):
        return self._change_value(self.website, self.type)

    @fields.depends('email', 'type', methods=['_change_value'])
    def on_change_email(self):
        return self._change_value(self.email, self.type)

    @fields.depends('skype', 'type', methods=['_change_value'])
    def on_change_skype(self):
        return self._change_value(self.skype, self.type)

    @fields.depends('sip', 'type', methods=['_change_value'])
    def on_change_sip(self):
        return self._change_value(self.sip, self.type)

    @fields.depends('other_value', 'type', methods=['_change_value'])
    def on_change_other_value(self):
        return self._change_value(self.other_value, self.type)

    def get_rec_name(self, name):
        name = self.name or self.party.rec_name
        return '%s <%s>' % (name, self.value_compact or self.value)

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('value',) + tuple(clause[1:]),
            ('value_compact',) + tuple(clause[1:]),
            ]

    @classmethod
    def _format_values(cls, mechanisms):
        for mechanism in mechanisms:
            value = mechanism.format_value(
                value=mechanism.value, type_=mechanism.type)
            if value != mechanism.value:
                mechanism.value = value
            value_compact = mechanism.format_value_compact(
                value=mechanism.value, type_=mechanism.type)
            if value_compact != mechanism.value_compact:
                mechanism.value_compact = value_compact
        cls.save(mechanisms)

    @classmethod
    def create(cls, vlist):
        mechanisms = super(ContactMechanism, cls).create(vlist)
        cls._format_values(mechanisms)
        return mechanisms

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        all_mechanisms = []
        for mechanisms, values in zip(actions, actions):
            all_mechanisms.extend(mechanisms)
            if 'party' in values:
                for mechanism in mechanisms:
                    if mechanism.party.id != values['party']:
                        raise AccessError(
                            gettext('party'
                            '.msg_contact_mechanism_change_party') % {
                                'contact': mechanism.rec_name,
                                })
        super(ContactMechanism, cls).write(*args)
        cls._format_values(all_mechanisms)

    @classmethod
    def validate(cls, mechanisms):
        super(ContactMechanism, cls).validate(mechanisms)
        for mechanism in mechanisms:
            mechanism.check_valid_phonenumber()

    def check_valid_phonenumber(self):
        if not phonenumbers or self.type not in _PHONE_TYPES:
            return
        phonenumber = self._parse_phonenumber(self.value)
        if not (phonenumber and phonenumbers.is_valid_number(phonenumber)):
            raise InvalidPhoneNumber(
                gettext('party.msg_invalid_phone_number',
                    phone=self.value, party=self.party.rec_name))

    @classmethod
    def usages(cls, _fields=None):
        "Returns the selection list of usage"
        usages = [(None, "")]
        if _fields:
            for name, desc in cls.fields_get(_fields).items():
                usages.append((name, desc['string']))
        return usages
