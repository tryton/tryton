# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

__all__ = ['Trigger']


class Trigger:
    __name__ = 'ir.trigger'
    __metaclass__ = PoolMeta

    _required = ((Eval('action_function') == 'trigger')
        & (Eval('action_model_name' == 'notification.email')))

    notification_email = fields.Many2One(
        'notification.email', "Email Notification", readonly=True,
        states={
            'required': _required,
            'invisible': ~_required,
            },
        depends=['action_function', 'action_model_name'])
    action_model_name = fields.Function(
        fields.Char("Action Model Name"), 'on_change_with_action_model_name')

    del _required

    @fields.depends('action_model')
    def on_change_with_action_model_name(self, name=None):
        if self.action_model:
            return self.action_model.model

    @fields.depends('notification_email', '_parent_notification_email.model')
    def on_change_notification_email(self):
        pool = Pool()
        Model = pool.get('ir.model')
        if self.notification_email:
            try:
                trigger_model, = Model.search([
                        ('model', '=', self.notification_email.model),
                        ])
            except ValueError:
                pass
            else:
                self.model = trigger_model
            notification_model, = Model.search([
                    ('model', '=', 'notification.email'),
                    ])
            self.action_model = notification_model
            self.action_function = 'trigger'
