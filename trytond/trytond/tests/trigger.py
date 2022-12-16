# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields

__all__ = [
    'Triggered', 'TriggerAction',
    ]

TRIGGER_LOGS = []


class Triggered(ModelSQL):
    'Triggered'
    __name__ = 'test.triggered'
    name = fields.Char('Name')


class TriggerAction(ModelSQL):
    'Trigger Action Model'
    __name__ = 'test.trigger_action'

    @staticmethod
    def trigger(records, trigger):
        '''
        Trigger function for test
        '''
        TRIGGER_LOGS.append((records, trigger))
