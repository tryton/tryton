# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Table

from trytond import backend
from trytond.config import config
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction


class Trigger(metaclass=PoolMeta):
    __name__ = 'ir.trigger'

    notification_email = fields.Many2One(
        'notification.email', "Email Notification", readonly=True,
        states={
            'required': Eval('notification_email_required', False),
            'invisible': ~Eval('notification_email_required', False),
            })
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
                        ('name', '=', self.notification_email.model),
                        ])
            except ValueError:
                pass
            else:
                self.model = trigger_model
            self.action = 'notification.email|trigger'


class Email(metaclass=PoolMeta):
    __name__ = 'ir.email'

    notification_email = fields.Many2One(
        'notification.email', "Notification Email", readonly=True,
        states={
            'invisible': ~Eval('notification_email'),
            })
    notification_trigger = fields.Many2One(
        'ir.trigger', "Notification Trigger", readonly=True,
        states={
            'invisible': ~Eval('notification_trigger'),
            })

    @classmethod
    def __register__(cls, module):
        table = cls.__table__()
        log_name = 'notification.email.log'
        log_table_name = config.get(
            'table', log_name, default=log_name.replace('.', '_'))
        log = Table(log_table_name)

        cursor = Transaction().connection.cursor()

        super().__register__(module)

        # Migration from 6.6: merge notification email log with email
        if backend.TableHandler.table_exist(log_table_name):
            query = table.insert(
                [table.create_uid, table.create_date,
                    table.write_uid, table.write_date,
                    table.recipients, table.recipients_secondary,
                    table.recipients_hidden,
                    table.resource,
                    table.notification_email, table.notification_trigger],
                log.select(
                    log.create_uid, log.create_date,
                    log.write_uid, log.write_date,
                    log.recipients, log.recipients_secondary,
                    log.recipients_hidden,
                    log.resource,
                    log.notification, log.trigger))
            cursor.execute(*query)
            backend.TableHandler.drop_table(log_name, log_table_name)

    def get_user(self, name):
        user = super().get_user(name)
        if self.notification_email or self.notification_trigger:
            user = None
        return user
