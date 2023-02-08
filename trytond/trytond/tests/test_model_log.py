# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest

from trytond.pool import Pool
from trytond.transaction import Transaction

from .test_tryton import activate_module, with_transaction


class ModelLogTestCase(unittest.TestCase):
    "Test Model Log"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_log(self):
        "Test model log"
        pool = Pool()
        Model = pool.get('test.model_log.model')
        Log = pool.get('ir.model.log')
        transaction = Transaction()

        record, = Model.create([{}])
        Model.log([record], 'delete', user=0)
        transaction._store_log_records()

        log, = Log.search([('resource', '=', str(record))])
        self.assertEqual(log.user.id, 0)
        self.assertEqual(log.event, 'delete')

    @with_transaction()
    def test_log_no_log(self):
        "Test no model log without _log"
        pool = Pool()
        Model = pool.get('test.model_log.model')
        Log = pool.get('ir.model.log')
        transaction = Transaction()

        self.addCleanup(setattr, Model, '_log', Model._log)
        Model._log = False

        record, = Model.create([{}])
        Model.log([record], 'delete')
        transaction._store_log_records()

        logs = Log.search([('resource', '=', str(record))])
        self.assertEqual(logs, [])

    @with_transaction(context={'_check_access': True})
    def test_create(self):
        "Test no model log on create"
        pool = Pool()
        Model = pool.get('test.model_log.model')
        Log = pool.get('ir.model.log')
        transaction = Transaction()

        record, = Model.create([{}])
        transaction._store_log_records()

        logs = Log.search([('resource', '=', str(record))])
        self.assertEqual(logs, [])

    @with_transaction(context={'_check_access': True})
    def test_write(self):
        "Test model log on write"
        pool = Pool()
        Model = pool.get('test.model_log.model')
        Log = pool.get('ir.model.log')
        transaction = Transaction()

        record, = Model.create([{}])
        Model.write([record], {'name': "Foo", 'state': 'end'})
        transaction._store_log_records()

        log, = Log.search([('resource', '=', str(record))])
        self.assertEqual(log.user.id, 1)
        self.assertEqual(log.event, 'write')
        self.assertEqual(log.target, 'name,state')

    @with_transaction(context={'_check_access': True})
    def test_write_empty(self):
        "Test no model log on empty write"
        pool = Pool()
        Model = pool.get('test.model_log.model')
        Log = pool.get('ir.model.log')
        transaction = Transaction()

        record, = Model.create([{}])
        Model.write([record], {})
        transaction._store_log_records()

        logs = Log.search([('resource', '=', str(record))])
        self.assertEqual(logs, [])

    @with_transaction(context={'_check_access': False})
    def test_write_no_check_access(self):
        "Test no model log on write without check access"
        pool = Pool()
        Model = pool.get('test.model_log.model')
        Log = pool.get('ir.model.log')
        transaction = Transaction()

        record, = Model.create([{}])
        Model.write([record], {'name': "Foo", 'state': 'end'})
        transaction._store_log_records()

        logs = Log.search([('resource', '=', str(record))])
        self.assertEqual(logs, [])

    @with_transaction(context={'_check_access': True})
    def test_delete(self):
        "Test model log on delete"
        pool = Pool()
        Model = pool.get('test.model_log.model')
        Log = pool.get('ir.model.log')
        transaction = Transaction()

        record, = Model.create([{}])
        Model.delete([record])
        transaction._store_log_records()

        log, = Log.search([('resource', '=', str(record))])
        self.assertEqual(log.event, 'delete')

    @with_transaction(context={'_check_access': False})
    def test_delete_no_check_access(self):
        "Test no model log on delete without check access"
        pool = Pool()
        Model = pool.get('test.model_log.model')
        Log = pool.get('ir.model.log')
        transaction = Transaction()

        record, = Model.create([{}])
        Model.delete([record])
        transaction._store_log_records()

        logs = Log.search([('resource', '=', str(record))])
        self.assertEqual(logs, [])

    @with_transaction(context={'_check_access': True})
    def test_button(self):
        "Test model log on button"
        pool = Pool()
        Model = pool.get('test.model_log.model')
        Log = pool.get('ir.model.log')
        transaction = Transaction()

        record, = Model.create([{}])
        Model.click([record])
        transaction._store_log_records()

        log, = Log.search([('resource', '=', str(record))])
        self.assertEqual(log.user.id, 1)
        self.assertEqual(log.event, 'button')
        self.assertEqual(log.target, 'click')

    @with_transaction(context={'_check_access': False})
    def test_button_no_check_access(self):
        "Test model log on button"
        pool = Pool()
        Model = pool.get('test.model_log.model')
        Log = pool.get('ir.model.log')
        transaction = Transaction()

        record, = Model.create([{}])
        Model.click([record])
        transaction._store_log_records()

        logs = Log.search([('resource', '=', str(record))])
        self.assertEqual(logs, [])

    @with_transaction()
    def test_wizard(self):
        "Test model log on wizard"
        pool = Pool()
        Model = pool.get('test.model_log.model')
        Wizard = pool.get('test.model_log.wizard', type='wizard')
        Log = pool.get('ir.model.log')
        transaction = Transaction()

        record, = Model.create([{}])
        with transaction.set_context(
                active_model=Model.__name__,
                active_id=record.id,
                active_ids=[record.id]):
            session_id, _, _ = Wizard.create()
            Wizard.execute(session_id, {}, 'modification')
        transaction._store_log_records()

        log, = Log.search([('resource', '=', str(record))])
        self.assertEqual(log.user.id, 1)
        self.assertEqual(log.event, 'wizard')
        self.assertEqual(log.target, 'test.model_log.wizard:modification')

    @with_transaction()
    def test_wizard_no_modification(self):
        "Test no model log on wizard without modification"
        pool = Pool()
        Model = pool.get('test.model_log.model')
        Wizard = pool.get('test.model_log.wizard', type='wizard')
        Log = pool.get('ir.model.log')
        transaction = Transaction()

        record, = Model.create([{}])
        with transaction.set_context(
                active_model=Model.__name__,
                active_id=record.id,
                active_ids=[record.id]):
            session_id, _, _ = Wizard.create()
            Wizard.execute(session_id, {}, 'no_modification')
        transaction._store_log_records()

        logs = Log.search([('resource', '=', str(record))])
        self.assertEqual(logs, [])

    @with_transaction()
    def test_worflow(self):
        "Test model log on workflow transition"
        pool = Pool()
        Model = pool.get('test.model_log.model')
        Log = pool.get('ir.model.log')
        transaction = Transaction()

        record, = Model.create([{}])
        Model.end([record])
        transaction._store_log_records()

        log, = Log.search([('resource', '=', str(record))])
        self.assertEqual(log.user.id, 1)
        self.assertEqual(log.event, 'transition')
        self.assertEqual(log.target, 'state:end')

    @with_transaction()
    def test_worflow_no_transition(self):
        "Test no model log on workflow without transition"
        pool = Pool()
        Model = pool.get('test.model_log.model')
        Log = pool.get('ir.model.log')
        transaction = Transaction()

        record, = Model.create([{'state': 'end'}])
        Model.end([record])
        transaction._store_log_records()

        logs = Log.search([('resource', '=', str(record))])
        self.assertEqual(logs, [])
