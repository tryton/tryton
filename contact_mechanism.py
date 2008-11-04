#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.osv import OSV, fields

STATES = {
    'readonly': "active == False",
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


class ContactMechanism(OSV):
    "Contact Mechanism"
    _name = "party.contact_mechanism"
    _description = __doc__
    _rec_name = 'value'

    type = fields.Selection(_TYPES, 'Type', required=True, states=STATES,
            sort=False)
    value = fields.Char('Value', select=1,
            states={
                'invisible': "type in ('email', 'website')",
                'required': "type not in ('email', 'website')",
                'readonly': "active == False",
            }, on_change=['value'])
    comment = fields.Text('Comment', states=STATES)
    party = fields.Many2One('party.party', 'Party', required=True,
            ondelete='CASCADE', states=STATES, select=1)
    active = fields.Boolean('Active', select=1)
    sequence = fields.Integer('Sequence')
    email = fields.Function('get_value', fnct_inv='set_value', type='char',
            string="E-Mail", states={
                'invisible': "type != 'email'",
                'required': "type == 'email'",
                'readonly': "active == False",
            }, on_change=['email'])
    website = fields.Function('get_value', fnct_inv='set_value', type='char',
            string="Website", states={
                'invisible': "type != 'website'",
                'required': "type == 'website'",
                'readonly': "active == False",
            }, on_change=['website'])
    skype = fields.Function('get_value', fnct_inv='set_value', type='char',
            string="Skype", states={
                'invisible': "type != 'skype'",
                'required': "type == 'skype'",
                'readonly': "active == False",
            }, on_change=['skype'])
    sip = fields.Function('get_value', fnct_inv='set_value', type='char',
            string="SIP", states={
                'invisible': "type != 'sip'",
                'required': "type == 'sip'",
                'readonly': "active == False",
            }, on_change=['sip'])

    def __init__(self):
        super(ContactMechanism, self).__init__()
        self._order.insert(0, ('party', 'ASC'))
        self._order.insert(1, ('sequence', 'ASC'))
        self._error_messages.update({
            'write_party': 'You can not modify the party of ' \
                    'a contact mechanism!',
            })

    def default_type(self, cursor, user, context=None):
        return 'phone'

    def default_active(self, cursor, user, context=None):
        return True

    def get_value(self, cursor, user, ids, names, arg, context=None):
        res = {}
        for name in names:
            res[name] = {}
        for mechanism in self.browse(cursor, user, ids, context=context):
            for name in names:
                res[name][mechanism.id] = mechanism.value
        return res

    def set_value(self, cursor, user, obj_id, name, value, arg, context=None):
        self.write(cursor, user, obj_id, {
            'value': value,
            }, context=context)

    def _change_value(self, cursor, user, value, context=None):
        return {
            'value': value,
            'website': value,
            'email': value,
            'skype': value,
            'sip': value,
        }

    def on_change_value(self, cursor, user, ids, vals, context=None):
        return self._change_value(cursor, user, vals.get('value'),
                context=context)

    def on_change_website(self, cursor, user, ids, vals, context=None):
        return self._change_value(cursor, user, vals.get('website'),
                context=context)

    def on_change_email(self, cursor, user, ids, vals, context=None):
        return self._change_value(cursor, user, vals.get('email'),
                context=context)

    def on_change_skype(self, cursor, user, ids, vals, context=None):
        return self._change_value(cursor, user, vals.get('skype'),
                context=context)

    def on_change_sip(self, cursor, user, ids, vals, context=None):
        return self._change_value(cursor, user, vals.get('sip'),
                context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if 'party' in vals:
            if isinstance(ids, (int, long)):
                ids = [ids]
            for mechanism in self.browse(cursor, user, ids, context=context):
                if mechanism.party.id != vals['party']:
                    self.raise_user_error(cursor, 'write_party',
                            context=context)
        return super(ContactMechanism, self).write(cursor, user, ids, vals,
                context=context)

ContactMechanism()
