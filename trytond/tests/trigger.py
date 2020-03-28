# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.pool import Pool, PoolMeta

TRIGGER_LOGS = []


class Trigger(metaclass=PoolMeta):
    __name__ = 'ir.trigger'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.action.selection.append(
            ('test.trigger_action|trigger', "Test Trigger"))


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


def register(module):
    Pool.register(
        Trigger,
        Triggered,
        TriggerAction,
        module=module, type_='model')
