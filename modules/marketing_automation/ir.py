# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.method.selection.extend([
                ('marketing.automation.scenario|trigger',
                    "Trigger Marketing Scenarios"),
                ('marketing.automation.record.activity|process',
                    "Process Marketing Activity"),
                ])


class Email(metaclass=PoolMeta):
    __name__ = 'ir.email'

    marketing_automation_activity = fields.Many2One(
        'marketing.automation.activity', "Activity", readonly=True,
        states={
            'invisible': ~Eval('marketing_automation_activity'),
            })
    marketing_automation_record = fields.Many2One(
        'marketing.automation.record', "Record",
        readonly=True,
        states={
            'invisible': ~Eval('marketing_automation_record'),
            })

    def get_user(self, name):
        user = super().get_user(name)
        if (self.marketing_automation_activity
                or self.marketing_automation_record):
            user = None
        return user
