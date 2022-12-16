#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.backend import TableHandler

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


class ContactMechanism(ModelSQL, ModelView):
    "Contact Mechanism"
    __name__ = 'party.contact_mechanism'
    _rec_name = 'value'

    type = fields.Selection(_TYPES, 'Type', required=True, states=STATES,
        sort=False, depends=DEPENDS)
    value = fields.Char('Value', select=True, states=STATES,
        on_change=['value'], depends=DEPENDS)
    comment = fields.Text('Comment', states=STATES, depends=DEPENDS)
    party = fields.Many2One('party.party', 'Party', required=True,
        ondelete='CASCADE', states=STATES, select=True, depends=DEPENDS)
    active = fields.Boolean('Active', select=True)
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s')
    email = fields.Function(fields.Char('E-Mail', states={
        'invisible': Eval('type') != 'email',
        'required': Eval('type') == 'email',
        'readonly': ~Eval('active', True),
        }, on_change=['email'], depends=['value', 'type', 'active']),
        'get_value', setter='set_value')
    website = fields.Function(fields.Char('Website', states={
        'invisible': Eval('type') != 'website',
        'required': Eval('type') == 'website',
        'readonly': ~Eval('active', True),
        }, on_change=['website'], depends=['value', 'type', 'active']),
        'get_value', setter='set_value')
    skype = fields.Function(fields.Char('Skype', states={
        'invisible': Eval('type') != 'skype',
        'required': Eval('type') == 'skype',
        'readonly': ~Eval('active', True),
        }, on_change=['skype'], depends=['value', 'type', 'active']),
        'get_value', setter='set_value')
    sip = fields.Function(fields.Char('SIP', states={
        'invisible': Eval('type') != 'sip',
        'required': Eval('type') == 'sip',
        'readonly': ~Eval('active', True),
        }, on_change=['sip'], depends=['value', 'type', 'active']),
        'get_value', setter='set_value')
    other_value = fields.Function(fields.Char('Value', states={
        'invisible': Eval('type').in_(['email', 'website', 'skype', 'sip']),
        'required': ~Eval('type').in_(['email', 'website']),
        'readonly': ~Eval('active', True),
        }, on_change=['other_value'], depends=['value', 'type', 'active']),
        'get_value', setter='set_value')

    @classmethod
    def __setup__(cls):
        super(ContactMechanism, cls).__setup__()
        cls._order.insert(0, ('party', 'ASC'))
        cls._order.insert(1, ('sequence', 'ASC'))
        cls._error_messages.update({
            'write_party': 'You can not modify the party of ' \
                    'a contact mechanism!',
            })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

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

    @classmethod
    def set_value(cls, mechanisms, name, value):
        cls.write(mechanisms, {
            'value': value,
            })

    def _change_value(self, value):
        return {
            'value': value,
            'website': value,
            'email': value,
            'skype': value,
            'sip': value,
            'other_value': value,
            }

    def on_change_value(self):
        return self._change_value(self.value)

    def on_change_website(self):
        return self._change_value(self.website)

    def on_change_email(self):
        return self._change_value(self.email)

    def on_change_skype(self):
        return self._change_value(self.skype)

    def on_change_sip(self):
        return self._change_value(self.sip)

    def on_change_other_value(self):
        return self._change_value(self.other_value)

    @classmethod
    def write(cls, mechanisms, vals):
        if 'party' in vals:
            for mechanism in mechanisms:
                if mechanism.party.id != vals['party']:
                    cls.raise_user_error('write_party')
        super(ContactMechanism, cls).write(mechanisms, vals)
