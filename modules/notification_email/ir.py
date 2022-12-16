# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Trigger(metaclass=PoolMeta):
    __name__ = 'ir.trigger'

    notification_email = fields.Many2One(
        'notification.email', "Email Notification", readonly=True,
        states={
            'required': Eval('notification_email_required', False),
            'invisible': ~Eval('notification_email_required', False),
            },
        depends=['notification_email_required'])
    notification_email_required = fields.Function(
        fields.Boolean("Notification Email Required"),
        'on_change_with_notification_email_required')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.action.selection.append(
            ('notification.email|trigger', "Email Notification"),
            )

    @fields.depends('action')
    def on_change_with_notification_email_required(self, name=None):
        return self.action == 'notification.email|trigger'

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
            self.action = 'notification.email|trigger'
