# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import sys
import unittest
from unittest.mock import ANY, MagicMock, Mock, patch

import ldap3

from trytond.config import config
from trytond.modules.ldap_authentication.res import ldap_server, parse_ldap_url
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction

section = 'ldap_authentication'


class LDAPAuthenticationTestCase(ModuleTestCase):
    'Test LDAPAuthentication module'
    module = 'ldap_authentication'

    def setUp(self):
        super(LDAPAuthenticationTestCase, self).setUp()
        methods = config.get('session', 'authentications', default='')
        config.set('session', 'authentications', 'ldap')
        self.addCleanup(config.set, 'session', 'authentications', methods)
        config.add_section(section)
        self.addCleanup(config.remove_section, section)

    def _get_login(
            self, uri='ldap://localhost/dc=tryton,dc=org', start_tls=False):
        pool = Pool()
        User = pool.get('res.user')
        config.set(section, 'uri', uri)

        @patch.object(ldap3, 'Connection')
        @patch.object(User, 'ldap_search_user')
        def get_login(login, password, find, ldap_search_user, Connection):
            con = Connection.return_value = MagicMock()
            con.__enter__.return_value = con
            con.bind.return_value = bool(find)
            if find:
                ldap_search_user.return_value = [('dn', {'uid': [find]})]
            else:
                ldap_search_user.return_value = None
            user_id = User.get_login(login, {
                    'password': password,
                    })
            if find:
                Connection.assert_called_with(
                    ANY, ANY, password, auto_bind=ldap3.AUTO_BIND_NONE)
                if start_tls:
                    con.start_tls.assert_called()
                else:
                    con.start_tls.assert_not_called()
                con.bind.assert_called()
            return user_id
        return get_login

    @with_transaction()
    def test_user_get_login_existing_user(self):
        "Test User.get_login with existing user"
        pool = Pool()
        User = pool.get('res.user')
        user, = User.search([('login', '=', 'admin')])

        get_login = self._get_login()

        self.assertEqual(get_login('admin', 'admin', 'admin'), user.id)
        self.assertEqual(get_login('AdMiN', 'admin', 'admin'), user.id)

    @with_transaction()
    def test_user_get_login_unknown_user(self):
        "test User.get_login with unknown user"
        get_login = self._get_login()

        self.assertFalse(get_login('foo', 'bar', None))
        self.assertFalse(get_login('foo', 'bar', 'foo'))

    @with_transaction()
    def test_user_get_login_create_user(self):
        "Test User.get_login with user to create"
        pool = Pool()
        User = pool.get('res.user')
        config.set(section, 'create_user', 'True')
        get_login = self._get_login()

        user_id = get_login('foo', 'bar', 'foo')
        foo, = User.search([('login', '=', 'foo')])

        self.assertEqual(user_id, foo.id)
        self.assertEqual(foo.name, 'foo')

    @with_transaction()
    def test_user_get_login_create_user_case(self):
        "Test User.get_login with user to create with different case"
        pool = Pool()
        User = pool.get('res.user')
        config.set(section, 'create_user', 'True')
        get_login = self._get_login()

        user_id = get_login('BaR', 'foo', 'bar')
        bar, = User.search([('login', '=', 'bar')])

        self.assertEqual(user_id, bar.id)
        self.assertEqual(bar.name, 'bar')

    @with_transaction()
    def test_user_get_login_with_tls(self):
        "Test User.get_login with TLS"
        pool = Pool()
        User = pool.get('res.user')
        user, = User.search([('login', '=', 'admin')])

        get_login = self._get_login(
            'ldap+tls://localhost/dc=tryton,dc=org', start_tls=True)

        self.assertEqual(get_login('admin', 'admin', 'admin'), user.id)

    @with_transaction()
    def test_user_get_login_with_ssl(self):
        "Test User.get_login with SSL"
        pool = Pool()
        User = pool.get('res.user')
        user, = User.search([('login', '=', 'admin')])

        get_login = self._get_login('ldaps://localhost/dc=tryton,dc=org')

        self.assertEqual(get_login('admin', 'admin', 'admin'), user.id)

    def test_parse_ldap_url(self):
        'Test parse_ldap_url'
        self.assertEqual(
            parse_ldap_url('ldap:///o=University%20of%20Michigan,c=US')[1],
            'o=University of Michigan,c=US')
        self.assertEqual(
            parse_ldap_url(
                'ldap://ldap.itd.umich.edu/o=University%20of%20Michigan,c=US'
                )[1],
            'o=University of Michigan,c=US')
        self.assertEqual(
            parse_ldap_url(
                'ldap://ldap.itd.umich.edu/o=University%20of%20Michigan,'
                'c=US?postalAddress')[2],
            'postalAddress')
        self.assertEqual(
            parse_ldap_url(
                'ldap://host.com:6666/o=University%20of%20Michigan,'
                'c=US??sub?(cn=Babs%20Jensen)')[3:5],
            ('sub', '(cn=Babs Jensen)'))
        self.assertEqual(
            parse_ldap_url(
                'ldap:///??sub??bindname=cn=Manager%2co=Foo')[5],
            {'bindname': ['cn=Manager,o=Foo']})
        self.assertEqual(
            parse_ldap_url(
                'ldap:///??sub??!bindname=cn=Manager%2co=Foo')[5],
            {'!bindname': ['cn=Manager,o=Foo']})

    @unittest.skipIf(
        sys.version_info < (3, 8), "call_args does not have args nor kwargs")
    def test_ldap_server(self):
        "Test ldap_server"
        for uri, (host, tls) in [
                ('ldap://localhost/dc=tryton,dc=org',
                    ('ldap://localhost:389', None)),
                ('ldaps://localhost/dc=tryton,dc=org',
                    ('ldaps://localhost:636', True)),
                ('ldap+tls://localhost/dc=tryton,dc=org',
                    ('ldap://localhost:389', True)),
                ]:
            config.set(section, 'uri', uri)

            with patch('ldap3.Server') as Server:
                ldap_server()

                self.assertEqual(Server.call_args.args, (host,))
                if tls:
                    self.assertTrue(Server.call_args.kwargs.get('tls'))
                else:
                    self.assertFalse(Server.call_args.kwargs.get('tls'))

    def _ldap_search_user(
            self, uri='ldap://localhost/dc=tryton,dc=org',
            auto_bind=ldap3.AUTO_BIND_DEFAULT):
        pool = Pool()
        User = pool.get('res.user')
        config.set(section, 'uri', uri)

        @patch.object(ldap3, 'Connection')
        def ldap_search_user(login, attrs, Connection):
            con = Connection.return_value = MagicMock()
            con.__enter__.return_value = con
            con.entries = [Mock()]
            server = ldap_server()
            User.ldap_search_user(login, server, attrs=attrs)
            Connection.assert_called_with(
                ANY, ANY, ANY, auto_bind=auto_bind)
            con.search.assert_called()
        return ldap_search_user

    @with_transaction()
    def test_ldap_search_user(self):
        "Test User.ldap_search_user"
        ldap_search_user = self._ldap_search_user()

        ldap_search_user('admin', None)

    @with_transaction()
    def test_ldap_search_user_with_tls(self):
        "Test User.ldap_search_user with TSL"
        ldap_search_user = self._ldap_search_user(
            'ldap+tls://localhost/dc=tryton,dc=org',
            ldap3.AUTO_BIND_TLS_BEFORE_BIND)

        ldap_search_user('admin', None)

    @with_transaction()
    def test_ldap_search_user_with_ssl(self):
        "Test User.ldap_search_user with SSL"
        ldap_search_user = self._ldap_search_user(
            'ldaps://localhost/dc=tryton,dc=org')

        ldap_search_user('admin', None)


del ModuleTestCase
