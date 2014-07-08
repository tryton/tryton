#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import unittest

from mock import patch
import ldap

import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction


class LDAPAuthenticationTestCase(unittest.TestCase):
    'Test LDAPAuthentication module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('ldap_authentication')

    def test0005views(self):
        'Test views'
        test_view('ldap_authentication')

    def test0006depends(self):
        'Test depends'
        test_depends()

    def test_user_get_login(self):
        'Test User.get_login'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            User = POOL.get('res.user')
            Connection = POOL.get('ldap.connection')

            connection = Connection(server='localhost',
                auth_base_dn='dc=tryton,dc=org')
            connection.save()

            @patch.object(ldap, 'initialize')
            @patch.object(User, 'ldap_search_user')
            def get_login(login, password, find, ldap_search_user, initialize):
                con = initialize.return_value
                con.simple_bind_s.return_value = True
                if find:
                    ldap_search_user.return_value = [('dn', {})]
                else:
                    ldap_search_user.return_value = None
                return User.get_login(login, password)

            # Test existing user
            self.assertEqual(get_login('admin', 'admin', False), USER)
            self.assertEqual(get_login('admin', 'admin', True), USER)

            # Test new user
            self.assertFalse(get_login('foo', 'bar', False))
            self.assertFalse(get_login('foo', 'bar', True))

            # Test create new user
            connection.auth_create_user = True
            connection.save()
            user_id = get_login('foo', 'bar', True)
            foo, = User.search([('login', '=', 'foo')])
            self.assertEqual(user_id, foo.id)
            self.assertEqual(foo.name, 'foo')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        LDAPAuthenticationTestCase))
    return suite
