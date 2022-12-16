#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields

TRIGGER_LOGS = []

class Triggered(ModelSQL):
    'Triggered'
    _name = 'test.triggered'
    _description = __doc__

    name = fields.Char('Name')

    def trigger(self, ids, trigger_id):
        '''
        Trigger function for test
        '''
        TRIGGER_LOGS.append((ids, trigger_id))

Triggered()
