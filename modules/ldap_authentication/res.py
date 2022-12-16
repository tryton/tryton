# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import urlparse

import ldap
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.config import config, parse_uri

__all__ = ['User']
__metaclass__ = PoolMeta

logger = logging.getLogger(__name__)
section = 'ldap_authentication'

# Old version of urlparse doesn't parse query for ldap
# see http://bugs.python.org/issue9374
if hasattr(urlparse, 'uses_query') and 'ldap' not in urlparse.uses_query:
    urlparse.uses_query.append('ldap')


def parse_ldap_url(uri):
    unquote = urlparse.unquote
    uri = parse_uri(uri)
    dn = unquote(uri.path)[1:]
    attributes, scope, filter_, extensions = (
        uri.query.split('?') + [''] * 4)[:4]
    if not scope:
        scope = 'base'
    extensions = urlparse.parse_qs(extensions)
    return (uri, dn, unquote(attributes), unquote(scope), unquote(filter_),
        extensions)


def ldap_connection():
    uri = config.get(section, 'uri')
    if not uri:
        return
    uri, _, _, _, _, extensions = parse_ldap_url(uri)
    if uri.scheme.startswith('ldaps'):
        scheme, port = 'ldaps', 636
    else:
        scheme, port = 'ldap', 389
    conn = ldap.initialize('%s://%s:%s/' % (
            scheme, uri.hostname, uri.port or port))
    if config.getboolean(section, 'active_directory', default=False):
        conn.set_option(ldap.OPT_REFERRALS, 0)
    if 'tls' in uri.scheme:
        conn.start_tls_s()

    bindname, = extensions.get('bindname', [None])
    if not bindname:
        bindname, = extensions.get('!bindname', [None])
    if bindname:
        # XXX find better way to get the password
        conn.simple_bind_s(bindname, config.get(section, 'bind_pass'))
    return conn


# python-ldap works only with str
def unicode2str(param):
    if isinstance(param, unicode):
        param = param.encode('utf-8')
    return param


class User:
    __name__ = 'res.user'

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._error_messages.update({
                'set_passwd_ldap_user': (
                    'You can not set the password of ldap user "%s".'),
                })

    @staticmethod
    def ldap_search_user(login, con, attrs=None):
        '''
        Return the result of a ldap search for the login using the ldap
        connection con based on connection.
        The attributes values defined in attrs will be return.
        '''
        _, dn, _, scope, filter_, _ = parse_ldap_url(
            config.get(section, 'uri'))
        scope = {
            'base': ldap.SCOPE_BASE,
            'onelevel': ldap.SCOPE_ONELEVEL,
            'subtree': ldap.SCOPE_SUBTREE,
            }.get(scope)
        uid = config.get(section, 'uid', default='uid')
        if filter_:
            filter_ = '(&(%s=%s)%s)' % (uid, unicode2str(login), filter_)
        else:
            filter_ = '(%s=%s)' % (uid, unicode2str(login))

        result = con.search_s(dn, scope, filter_, attrs)
        if config.get(section, 'active_directory'):
            result = [x for x in result if x[0]]
        if result and len(result) > 1:
            logger.info('ldap_search_user found more than 1 user')
        return result

    @classmethod
    def _check_passwd_ldap_user(cls, logins):
        find = False
        try:
            con = ldap_connection()
            if not con:
                return
            for login in logins:
                if cls.ldap_search_user(login, con, attrs=[]):
                    find = True
                    break
        except ldap.LDAPError:
            logger.error('LDAPError when checking password', exc_info=True)
        if find:
            cls.raise_user_error('set_passwd_ldap_user', (login,))

    @classmethod
    def create(cls, vlist):
        tocheck = []
        for values in vlist:
            if values.get('password') and 'login' in values:
                tocheck.append(values['login'])
        if tocheck:
            with Transaction().set_context(_check_access=False):
                cls._check_passwd_ldap_user(tocheck)
        return super(User, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        for users, values in zip(actions, actions):
            if values.get('password'):
                logins = [x.login for x in users]
                cls._check_passwd_ldap_user(logins)
        super(User, cls).write(*args)

    @classmethod
    def set_preferences(cls, values, old_password=False):
        if 'password' in values:
            try:
                con = ldap_connection()
                if con:
                    user = cls(Transaction().user)
                    uid = config.get(section, 'uid', default='uid')
                    users = cls.ldap_search_user(user.login, con, attrs=[uid])
                    if users and len(users) == 1:
                        [(dn, attrs)] = users
                        if con.simple_bind_s(dn, unicode2str(old_password)):
                            con.passwd_s(
                                dn, unicode2str(old_password),
                                unicode2str(values['password']))
                            values = values.copy()
                            del values['password']
                        else:
                            cls.raise_user_error('wrong_password')
            except ldap.LDAPError:
                logger.error('LDAPError when setting preferences',
                    exc_info=True)
        super(User, cls).set_preferences(values, old_password=old_password)

    @classmethod
    def get_login(cls, login, password):
        pool = Pool()
        LoginAttempt = pool.get('res.user.login.attempt')
        try:
            con = ldap_connection()
            if con:
                uid = config.get(section, 'uid', default='uid')
                users = cls.ldap_search_user(login, con, attrs=[uid])
                if users and len(users) == 1:
                    [(dn, attrs)] = users
                    if (password
                            and con.simple_bind_s(dn, unicode2str(password))):
                        # Use ldap uid so we always get the right case
                        login = attrs.get(uid, [login])[0]
                        user_id, _ = cls._get_login(login)
                        if user_id:
                            LoginAttempt.remove(login)
                            return user_id
                        elif config.getboolean(section, 'create_user'):
                            user, = cls.create([{
                                        'name': login,
                                        'login': login,
                                        }])
                            return user.id
        except ldap.LDAPError:
            logger.error('LDAPError when login', exc_info=True)
        return super(User, cls).get_login(login, password)
