# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

from trytond import security
from trytond.pool import Pool
from trytond.tests.test_tryton import RouteTestCase, with_transaction
from trytond.transaction import Transaction


class SecurityTestCase(RouteTestCase):
    "Test security"
    module = 'res'

    @classmethod
    def setUpDatabase(cls):
        pool = Pool()
        User = pool.get('res.user')
        User.create([{
                    'name': 'user',
                    'login': 'user',
                    'password': '12345678',
                    }])

    @with_transaction()
    def tearDown(self):
        pool = Pool()
        Session = pool.get('ir.session')
        Session.delete(Session.search([]))
        Transaction().commit()

    @with_transaction()
    def test_check_session(self):
        "Testing check_session"
        pool = Pool()
        User = pool.get('res.user')
        Session = pool.get('ir.session')

        db_name = Transaction().database.name
        user, = User.search([('login', '=', 'user')])
        with Transaction().set_user(user.id):
            key = Session.new()

        Transaction().commit()

        user_id = security.check_session(db_name, user.id, key)
        self.assertEqual(user_id, user.id)

    @with_transaction()
    def test_check_session_invalid(self):
        "Testing check_session with an invalid session"
        pool = Pool()
        User = pool.get('res.user')

        db_name = Transaction().database.name
        user, = User.search([('login', '=', 'user')])

        user_id = security.check_session(db_name, user.id, "invalid key")
        self.assertIsNone(user_id)
