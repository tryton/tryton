# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import ssl
import urllib.parse

import ldap3
from ldap3.core.exceptions import LDAPException

import trytond.config as config
from trytond.exceptions import LoginException
from trytond.i18n import gettext
from trytond.model.exceptions import AccessError
from trytond.pool import PoolMeta

logger = logging.getLogger(__name__)
section = 'ldap_authentication'

# Old version of urlparse doesn't parse query for ldap
# see http://bugs.python.org/issue9374
if 'ldap' not in urllib.parse.uses_query:
    urllib.parse.uses_query.append('ldap')


def parse_ldap_url(uri):
    unquote = urllib.parse.unquote
    uri = config.parse_uri(uri)
    dn = unquote(uri.path)[1:]
    attributes, scope, filter_, extensions = (
        uri.query.split('?') + [''] * 4)[:4]
    if not scope:
        scope = 'base'
    extensions = urllib.parse.parse_qs(extensions)
    return (uri, dn, unquote(attributes), unquote(scope), unquote(filter_),
        extensions)


def ldap_server():
    uri = config.get(section, 'uri')
    if not uri:
        return
    uri, _, _, _, _, extensions = parse_ldap_url(uri)
    if uri.scheme.startswith('ldaps'):
        scheme, port = 'ldaps', 636
        tls = ldap3.Tls(validate=ssl.CERT_REQUIRED)
    else:
        scheme, port = 'ldap', 389
        tls = None
        if 'tls' in uri.scheme:
            tls = ldap3.Tls(validate=ssl.CERT_REQUIRED)
    return ldap3.Server('%s://%s:%s' % (
            scheme, uri.hostname, uri.port or port), tls=tls)


class User(metaclass=PoolMeta):
    __name__ = 'res.user'

    @staticmethod
    def ldap_search_user(login, server, attrs=None):
        '''
        Return the result of a ldap search for the login using the ldap
        server.
        The attributes values defined in attrs will be return.
        '''
        _, dn, _, scope, filter_, extensions = parse_ldap_url(
            config.get(section, 'uri'))
        scope = {
            'base': ldap3.BASE,
            'onelevel': ldap3.LEVEL,
            'one': ldap3.LEVEL,
            'subtree': ldap3.SUBTREE,
            'sub': ldap3.SUBTREE,
            }[scope]
        uid = config.get(section, 'uid', default='uid')
        if filter_:
            filter_ = '(&(%s=%s)%s)' % (uid, login, filter_)
        else:
            filter_ = '(%s=%s)' % (uid, login)

        bindpass = None
        bindname, = extensions.get('bindname', [None])
        if not bindname:
            bindname, = extensions.get('!bindname', [None])
        if bindname:
            # XXX find better way to get the password
            bindpass = config.get(section, 'bind_pass')

        bind_method = ldap3.AUTO_BIND_DEFAULT
        if server.ssl is False and server.tls is not None:
            bind_method = ldap3.AUTO_BIND_TLS_BEFORE_BIND

        with ldap3.Connection(
                server, bindname, bindpass, auto_bind=bind_method) as con:
            con.search(dn, filter_, search_scope=scope, attributes=attrs)
            result = con.entries
            if result and len(result) > 1:
                logger.info('ldap_search_user found more than 1 user')
            return [(e.entry_dn, e.entry_attributes_as_dict)
                for e in result]

    @classmethod
    def _check_passwd_ldap_user(cls, logins):
        find = False
        try:
            server = ldap_server()
            if not server:
                return
            for login in logins:
                if cls.ldap_search_user(login, server, attrs=[]):
                    find = True
                    break
        except LDAPException:
            logger.error('LDAPError when checking password', exc_info=True)
        if find:
            raise AccessError(
                gettext('ldap_authentication.msg_ldap_user_change_password',
                    user=login))

    @classmethod
    def preprocess_values(cls, mode, values):
        values = super().preprocess_values(mode, values)
        if mode == 'create' and values.get('password') and 'login' in values:
            cls._check_passwd_ldap_user([values['login']])
        return values

    @classmethod
    def check_modification(cls, mode, users, values=None, external=False):
        super().check_modification(
            mode, users, values=values, external=external)
        if mode == 'write' and values.get('password'):
            cls._check_passwd_ldap_user([u.login for u in users])

    @classmethod
    def _login_ldap(cls, login, parameters):
        if 'password' not in parameters:
            msg = gettext('res.msg_user_password', login=login)
            raise LoginException('password', msg, type='password')
        password = parameters['password']
        try:
            server = ldap_server()
            if server:
                uid = config.get(section, 'uid', default='uid')
                users = cls.ldap_search_user(login, server, attrs=[uid])
                if users and len(users) == 1:
                    [(dn, attrs)] = users
                    with ldap3.Connection(
                            server, dn, password,
                            auto_bind=ldap3.AUTO_BIND_NONE) as con:
                        if server.ssl is False and server.tls is not None:
                            con.start_tls()
                        if (password and con.bind()):
                            # Use ldap uid so we always get the right case
                            login = attrs.get(uid, [login])[0]
                            user_id = cls._get_login(login)[0]
                            if user_id:
                                return user_id
                            elif config.getboolean(section, 'create_user'):
                                user, = cls.create([{
                                            'name': login,
                                            'login': login,
                                            }])
                                return user.id
        except LDAPException:
            logger.error('LDAPError when login', exc_info=True)
