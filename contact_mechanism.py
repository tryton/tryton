# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
try:
    import phonenumbers
    from phonenumbers import PhoneNumberFormat, NumberParseException
except ImportError:
    phonenumbers = None

from trytond.model import ModelView, ModelSQL, fields, sequence_ordered
from trytond.pyson import Eval
from trytond import backend

__all__ = ['ContactMechanism']

STATES = {
    'readonly': ~Eval('active'),
    }
DEPENDS = ['active']

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


class ContactMechanism(sequence_ordered(), ModelSQL, ModelView):
    "Contact Mechanism"
    __name__ = 'party.contact_mechanism'
    _rec_name = 'value'

    type = fields.Selection(_TYPES, 'Type', required=True, states=STATES,
        sort=False, depends=DEPENDS)
    value = fields.Char('Value', select=True, states=STATES, depends=DEPENDS
        # Add all function fields to ensure to always fill them via on_change
        + ['email', 'website', 'skype', 'sip', 'other_value', 'value_compact'])
    value_compact = fields.Char('Value Compact', readonly=True)
    comment = fields.Text('Comment', states=STATES, depends=DEPENDS)
    party = fields.Many2One('party.party', 'Party', required=True,
        ondelete='CASCADE', states=STATES, select=True, depends=DEPENDS)
    active = fields.Boolean('Active', select=True)
    email = fields.Function(fields.Char('E-Mail', states={
        'invisible': Eval('type') != 'email',
        'required': Eval('type') == 'email',
        'readonly': ~Eval('active', True),
        }, depends=['value', 'type', 'active']),
        'get_value', setter='set_value')
    website = fields.Function(fields.Char('Website', states={
        'invisible': Eval('type') != 'website',
        'required': Eval('type') == 'website',
        'readonly': ~Eval('active', True),
        }, depends=['value', 'type', 'active']),
        'get_value', setter='set_value')
    skype = fields.Function(fields.Char('Skype', states={
        'invisible': Eval('type') != 'skype',
        'required': Eval('type') == 'skype',
        'readonly': ~Eval('active', True),
        }, depends=['value', 'type', 'active']),
        'get_value', setter='set_value')
    sip = fields.Function(fields.Char('SIP', states={
        'invisible': Eval('type') != 'sip',
        'required': Eval('type') == 'sip',
        'readonly': ~Eval('active', True),
        }, depends=['value', 'type', 'active']),
        'get_value', setter='set_value')
    other_value = fields.Function(fields.Char('Value', states={
        'invisible': Eval('type').in_(['email', 'website', 'skype', 'sip']),
        'required': ~Eval('type').in_(['email', 'website']),
        'readonly': ~Eval('active', True),
        }, depends=['value', 'type', 'active']),
        'get_value', setter='set_value')
    url = fields.Function(fields.Char('URL', states={
                'invisible': (~Eval('type').in_(['email', 'website', 'skype',
                            'sip', 'fax', 'phone'])
                    | ~Eval('url')),
                }, depends=['type']),
        'get_url')

    @classmethod
    def __setup__(cls):
        super(ContactMechanism, cls).__setup__()
        cls._order.insert(0, ('party', 'ASC'))
        cls._error_messages.update({
                'write_party': ('You can not modify the party of contact '
                    'mechanism "%s".'),
                'invalid_phonenumber': ('The phone number "%(phone)s" of '
                    'party "%(party)s" is not valid .'),
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        super(ContactMechanism, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @staticmethod
    def default_type():
        return 'phone'

    @staticmethod
    def default_active():
        return True

    @classmethod
    def get_value(cls, mechanisms, names):
        return dict((name, dict((m.id, m.value) for m in mechanisms))
            for name in names)

    def get_url(self, name=None, value=None):
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
        elif self.type == 'phone':
            return 'tel:%s' % value
        elif self.type == 'fax':
            return 'fax:%s' % value
        return None

    @classmethod
    def format_value(cls, value=None, type_=None):
        if phonenumbers and type_ in _PHONE_TYPES:
            try:
                phonenumber = phonenumbers.parse(value)
            except NumberParseException:
                pass
            else:
                value = phonenumbers.format_number(
                    phonenumber, PhoneNumberFormat.INTERNATIONAL)
        return value

    @classmethod
    def format_value_compact(cls, value=None, type_=None):
        if phonenumbers and type_ in _PHONE_TYPES:
            try:
                phonenumber = phonenumbers.parse(value)
            except NumberParseException:
                pass
            else:
                value = phonenumbers.format_number(
                    phonenumber, PhoneNumberFormat.E164)
        return value

    @classmethod
    def set_value(cls, mechanisms, name, value):
        #  Setting value is done by on_changes
        pass

    def _change_value(self, value, type_):
        self.value = self.format_value(value=value, type_=type_)
        self.value_compact = self.format_value_compact(
            value=value, type_=type_)
        self.website = value
        self.email = value
        self.skype = value
        self.sip = value
        self.other_value = value
        self.url = self.get_url(value=value)

    @fields.depends('value', 'type')
    def on_change_type(self):
        self.url = self.get_url(value=self.value)

    @fields.depends('value', 'type')
    def on_change_value(self):
        return self._change_value(self.value, self.type)

    @fields.depends('website', 'type')
    def on_change_website(self):
        return self._change_value(self.website, self.type)

    @fields.depends('email', 'type')
    def on_change_email(self):
        return self._change_value(self.email, self.type)

    @fields.depends('skype', 'type')
    def on_change_skype(self):
        return self._change_value(self.skype, self.type)

    @fields.depends('sip', 'type')
    def on_change_sip(self):
        return self._change_value(self.sip, self.type)

    @fields.depends('other_value', 'type')
    def on_change_other_value(self):
        return self._change_value(self.other_value, self.type)

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
        for mechanisms, values in zip(actions, actions):
            if 'party' in values:
                for mechanism in mechanisms:
                    if mechanism.party.id != values['party']:
                        cls.raise_user_error(
                            'write_party', (mechanism.rec_name,))
        super(ContactMechanism, cls).write(*args)
        cls._format_values(mechanisms)

    @classmethod
    def validate(cls, mechanisms):
        super(ContactMechanism, cls).validate(mechanisms)
        for mechanism in mechanisms:
            mechanism.check_valid_phonenumber()

    def check_valid_phonenumber(self):
        if not phonenumbers or self.type not in _PHONE_TYPES:
            return
        try:
            phonenumbers.parse(self.value)
        except NumberParseException:
            self.raise_user_error(
                'invalid_phonenumber', {
                    'phone': self.value,
                    'party': self.party.rec_name
                    })
