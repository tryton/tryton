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
    def _get_auth(self):
        pool = Pool()
        User = pool.get('res.user')
        Session = pool.get('ir.session')

        user, = User.search([('login', '=', 'user')])
        with Transaction().set_user(user.id):
            key = Session.new()

        Transaction().commit()
        return user.id, key

    def test_security_check(self):
        "Test security.check"
        user_id, key = self._get_auth()
        authenticated_user_id = security.check(self.db_name, user_id, key)
        self.assertEqual(authenticated_user_id, user_id)

    def test_security_check_invalid(self):
        "Test security.check with an invalid session"
        user_id, _ = self._get_auth()
        user_id = security.check(self.db_name, user_id, "invalid key")
        self.assertIsNone(user_id)

    def test_security_check_no_pool(self):
        "Test security.check without the pool"
        user_id, key = self._get_auth()
        Pool.stop(self.db_name)

        authenticated_user_id = security.check(self.db_name, user_id, key)
        self.assertNotIn(self.db_name, Pool._pools)
        self.assertEqual(authenticated_user_id, user_id)

    def test_security_check_no_pool_invalid(self):
        "Test security.check without the pool on an invalid session"
        user_id, _ = self._get_auth()
        Pool.stop(self.db_name)

        user_id = security.check(self.db_name, user_id, "invalid key")
        self.assertNotIn(self.db_name, Pool._pools)
        self.assertIsNone(user_id)
