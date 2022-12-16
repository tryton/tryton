#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Not, Bool, Eval, Equal, In

STATES = {
    'readonly': Not(Bool(Eval('active'))),
}

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
            sort=False)
    value = fields.Char('Value', select=1, states=STATES, on_change=['value'])
    comment = fields.Text('Comment', states=STATES)
    party = fields.Many2One('party.party', 'Party', required=True,
            ondelete='CASCADE', states=STATES, select=1)
    active = fields.Boolean('Active', select=1)
    sequence = fields.Integer('Sequence')
    email = fields.Function(fields.Char('E-Mail', states={
        'invisible': Not(Equal(Eval('type'), 'email')),
        'required': Equal(Eval('type'), 'email'),
        'readonly': Not(Bool(Eval('active'))),
        }, on_change=['email'], depends=['value', 'type', 'active']),
        'get_value', setter='set_value')
    website = fields.Function(fields.Char('Website', states={
        'invisible': Not(Equal(Eval('type'), 'website')),
        'required': Equal(Eval('type'), 'website'),
        'readonly': Not(Bool(Eval('active'))),
        }, on_change=['website'], depends=['value', 'type', 'active']),
        'get_value', setter='set_value')
    skype = fields.Function(fields.Char('Skype',states={
        'invisible': Not(Equal(Eval('type'), 'skype')),
        'required': Equal(Eval('type'), 'skype'),
        'readonly': Not(Bool(Eval('active'))),
        }, on_change=['skype'], depends=['value', 'type', 'active']),
        'get_value', setter='set_value')
    sip = fields.Function(fields.Char('SIP', states={
        'invisible': Not(Equal(Eval('type'), 'sip')),
        'required': Equal(Eval('type'), 'sip'),
        'readonly': Not(Bool(Eval('active'))),
        }, on_change=['sip'], depends=['value', 'type', 'active']),
        'get_value', setter='set_value')
    other_value = fields.Function(fields.Char('Value', states={
        'invisible': In(Eval('type'), ['email', 'website', 'skype', 'sip']),
        'required': Not(In(Eval('type'), ['email', 'website'])),
        'readonly': Not(Bool(Eval('active'))),
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
