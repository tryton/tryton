#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval

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
    _name = "party.contact_mechanism"
    _description = __doc__
    _rec_name = 'value'

    type = fields.Selection(_TYPES, 'Type', required=True, states=STATES,
        sort=False, depends=DEPENDS)
    value = fields.Char('Value', select=True, states=STATES,
        on_change=['value'], depends=DEPENDS)
    comment = fields.Text('Comment', states=STATES, depends=DEPENDS)
    party = fields.Many2One('party.party', 'Party', required=True,
        ondelete='CASCADE', states=STATES, select=True, depends=DEPENDS)
    active = fields.Boolean('Active', select=True)
    sequence = fields.Integer('Sequence', required=True)
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

    def __init__(self):
        super(ContactMechanism, self).__init__()
        self._order.insert(0, ('party', 'ASC'))
        self._order.insert(1, ('sequence', 'ASC'))
        self._error_messages.update({
            'write_party': 'You can not modify the party of ' \
                    'a contact mechanism!',
            })

    def default_type(self):
        return 'phone'

    def default_active(self):
        return True

    def get_value(self, ids, names):
        res = {}
        for name in names:
            res[name] = {}
        for mechanism in self.browse(ids):
            for name in names:
                res[name][mechanism.id] = mechanism.value
        return res

    def set_value(self, ids, name, value):
        self.write(ids, {
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

    def on_change_value(self, vals):
        return self._change_value(vals.get('value'))

    def on_change_website(self, vals):
        return self._change_value(vals.get('website'))

    def on_change_email(self, vals):
        return self._change_value(vals.get('email'))

    def on_change_skype(self, vals):
        return self._change_value(vals.get('skype'))

    def on_change_sip(self, vals):
        return self._change_value(vals.get('sip'))

    def on_change_other_value(self, vals):
        return self._change_value(vals.get('other_value'))

    def write(self, ids, vals):
        if 'party' in vals:
            if isinstance(ids, (int, long)):
                ids = [ids]
            for mechanism in self.browse(ids):
                if mechanism.party.id != vals['party']:
                    self.raise_user_error('write_party')
        return super(ContactMechanism, self).write(ids, vals)

ContactMechanism()
