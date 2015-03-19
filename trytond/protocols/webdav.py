# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import SocketServer
import socket
import BaseHTTPServer
import urlparse
import time
import urllib
import logging
from threading import local
import xml.dom.minidom
import base64
from pywebdav.lib import WebDAVServer, iface
from pywebdav.lib.errors import DAV_Error, DAV_NotFound, DAV_Secret, \
    DAV_Forbidden, DAV_Requested_Range_Not_Satisfiable
from pywebdav.lib.constants import COLLECTION, DAV_VERSION_1, DAV_VERSION_2
from pywebdav.lib.utils import get_urifilename, quote_uri
from pywebdav.lib.davcmd import copyone, copytree, moveone, movetree, \
    delone, deltree
from trytond.protocols.sslsocket import SSLSocket
from trytond.protocols.common import daemon
from trytond.security import login
from trytond import __version__
from trytond.tools.misc import LocalDict
from trytond import backend
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.exceptions import UserError, UserWarning, NotLogged, \
    ConcurrencyException
domimpl = xml.dom.minidom.getDOMImplementation()

DAV_VERSION_1['version'] += ',access-control'
DAV_VERSION_2['version'] += ',access-control'

logger = logging.getLogger(__name__)


# Local int for multi-thread
class LocalInt(local):

    def __init__(self, value=0):
        super(LocalInt, self).__init__()
        self.value = value

    def __int__(self):
        return int(self.value)

CACHE = LocalDict()


def setupConfig():

    class ConfigDAV:
        lockemulation = False
        verbose = False
        baseurl = ''

        def getboolean(self, name):
            return bool(self.get(name))

        def get(self, name, default=None):
            return getattr(self, name, default)

    class Config:
        DAV = ConfigDAV()

    return Config()


class BaseThreadedHTTPServer(SocketServer.ThreadingMixIn,
        BaseHTTPServer.HTTPServer):
    timeout = 1

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET,
                socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET,
            socket.SO_KEEPALIVE, 1)
        BaseHTTPServer.HTTPServer.server_bind(self)


class SecureThreadedHTTPServer(BaseThreadedHTTPServer):

    def __init__(self, server_address, HandlerClass):
        BaseThreadedHTTPServer.__init__(self, server_address, HandlerClass)
        self.socket = socket.socket(self.address_family, self.socket_type)
        self.server_bind()
        self.server_activate()


class WebDAVServerThread(daemon):

    def __init__(self, interface, port, secure=False):
        daemon.__init__(self, interface, port, secure,
                name='WebDAVServerThread')
        if self.secure:
            handler_class = SecureWebDAVAuthRequestHandler
            server_class = SecureThreadedHTTPServer
            if self.ipv6:
                server_class = SecureThreadedHTTPServer6
        else:
            handler_class = WebDAVAuthRequestHandler
            server_class = BaseThreadedHTTPServer
            if self.ipv6:
                server_class = BaseThreadedHTTPServer6
        handler_class._config = setupConfig()
        handler_class.IFACE_CLASS = TrytonDAVInterface(interface, port, secure)
        handler_class.IFACE_CLASS.baseurl = handler_class._config.DAV.baseurl
        self.server = server_class((interface, port), handler_class)


class BaseThreadedHTTPServer6(BaseThreadedHTTPServer):
    address_family = socket.AF_INET6


class SecureThreadedHTTPServer6(SecureThreadedHTTPServer):
    address_family = socket.AF_INET6


class TrytonDAVInterface(iface.dav_interface):

    def __init__(self, interface, port, secure=False):
        if secure:
            protocol = 'https'
        else:
            protocol = 'http'
        self.baseuri = '%s://%s:%s/' % (protocol, interface or
                socket.gethostname(), port)
        self.verbose = False

    def _log_exception(self, exception):
        if isinstance(exception, (NotLogged, ConcurrencyException, UserError,
                    UserWarning, DAV_Error, DAV_NotFound, DAV_Secret,
                    DAV_Forbidden)):
            logger.debug('Exception %s', exception, exc_info=True)
        else:
            logger.error('Exception %s', exception, exc_info=True)

    @staticmethod
    def get_dburi(uri):
        uri = urlparse.urlsplit(uri)[2]
        if uri and uri[0] == '/':
            uri = uri[1:]
        dbname, uri = (uri.split('/', 1) + [None])[0:2]
        if dbname:
            dbname = urllib.unquote_plus(dbname)
        if uri:
            uri = urllib.unquote_plus(uri)
        return dbname, uri

    def _get_dburi(self, uri):
        return TrytonDAVInterface.get_dburi(uri)

    def get_childs(self, uri, filter=None):
        res = []
        dbname, dburi = self._get_dburi(uri)
        if not dbname:
            database = backend.get('Database')().connect()
            cursor = database.cursor()
            try:
                lists = database.list(cursor)
            except Exception:
                lists = []
            finally:
                cursor.close()
            for dbname in lists:
                res.append(urlparse.urljoin(uri, dbname))
            return res
        pool = Pool(Transaction().cursor.database_name)
        try:
            Collection = pool.get('webdav.collection')
            scheme, netloc, path, params, query, fragment = \
                urlparse.urlparse(uri)
            if path[-1:] != '/':
                path += '/'
            for child in Collection.get_childs(dburi, filter=filter,
                    cache=CACHE):
                res.append(urlparse.urlunparse((scheme, netloc,
                            path + child.encode('utf-8'), params, query,
                            fragment)))
        except KeyError:
            return res
        except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden), exception:
            self._log_exception(exception)
            raise
        except Exception, exception:
            self._log_exception(exception)
            raise DAV_Error(500)
        return res

    def get_data(self, uri, range=None):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or (self.exists(uri) and self.is_collection(uri)):
            res = ('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 '
                'Transitional//EN">')
            res += '<html>'
            res += '<head>'
            res += ('<meta http-equiv="Content-Type" content="text/html; '
                'charset=utf-8">')
            res += '<title>Tryton - WebDAV - %s</title>' % dbname or 'root'
            res += '</head>'
            res += '<body>'
            res += '<h2>Collection: %s</h2>' % (get_urifilename(uri) or '/')
            res += '<ul>'
            if dbname:
                scheme, netloc, path, params, query, fragment = \
                    urlparse.urlparse(uri)
                if path[-1:] != '/':
                    path += '/'
                res += ('<li><a href="%s">..</a></li>'
                    % urlparse.urlunparse((scheme, netloc, path + '..',
                            params, query, fragment)))
            childs = self.get_childs(uri)
            childs.sort()
            for child in childs:
                res += ('<li><a href="%s">%s</a></li>'
                    % (quote_uri(child), get_urifilename(child)))
            res += '</ul>'
            res += '<hr noshade>'
            res += ('<em>Powered by <a href="http://www.tryton.org/">'
                'Tryton</a> version %s</em>' % __version__)
            res += '</body>'
            res += '</html>'
            return res
        pool = Pool(Transaction().cursor.database_name)
        Collection = pool.get('webdav.collection')
        try:
            res = Collection.get_data(dburi, cache=CACHE)
        except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden), exception:
            self._log_exception(exception)
            raise
        except Exception, exception:
            self._log_exception(exception)
            raise DAV_Error(500)
        if range is None:
            return res
        size = len(res)
        if range[1] == '':
            range[1] = size
        else:
            range[1] = int(range[1])
        if range[1] > size:
            range[1] = size
        if range[0] == '':
            range[0] = size - range[1]
        else:
            range[0] = int(range[0])
        if range[0] > size:
            raise DAV_Requested_Range_Not_Satisfiable
        return res[range[0]:range[1]]

    def put(self, uri, data, content_type=''):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            raise DAV_Forbidden
        pool = Pool(Transaction().cursor.database_name)
        Collection = pool.get('webdav.collection')
        try:
            res = Collection.put(dburi, data, content_type, cache=CACHE)
            Transaction().cursor.commit()
        except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden), exception:
            self._log_exception(exception)
            Transaction().cursor.rollback()
            raise
        except Exception, exception:
            self._log_exception(exception)
            Transaction().cursor.rollback()
            raise DAV_Error(500)
        if res:
            uparts = list(urlparse.urlsplit(uri))
            uparts[2] = res
            res = urlparse.urlunsplit(uparts)
        return res

    def mkcol(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            raise DAV_Forbidden
        pool = Pool(Transaction().cursor.database_name)
        Collection = pool.get('webdav.collection')
        try:
            res = Collection.mkcol(dburi, cache=CACHE)
            Transaction().cursor.commit()
        except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden), exception:
            self._log_exception(exception)
            Transaction().cursor.rollback()
            raise
        except Exception, exception:
            self._log_exception(exception)
            Transaction().cursor.rollback()
            raise DAV_Error(500)
        return res

    def _get_dav_resourcetype(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return COLLECTION
        pool = Pool(Transaction().cursor.database_name)
        Collection = pool.get('webdav.collection')
        try:
            res = Collection.get_resourcetype(dburi, cache=CACHE)
        except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden), exception:
            self._log_exception(exception)
            raise
        except Exception, exception:
            self._log_exception(exception)
            raise DAV_Error(500)
        return res

    def _get_dav_displayname(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return uri.split('/')[-1]
        pool = Pool(Transaction().cursor.database_name)
        try:
            Collection = pool.get('webdav.collection')
            res = Collection.get_displayname(dburi, cache=CACHE)
        except KeyError:
            raise DAV_NotFound
        except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden), exception:
            self._log_exception(exception)
            raise
        except Exception, exception:
            self._log_exception(exception)
            raise DAV_Error(500)
        return res

    def _get_dav_getcontentlength(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return '0'
        pool = Pool(Transaction().cursor.database_name)
        Collection = pool.get('webdav.collection')
        try:
            res = Collection.get_contentlength(dburi, cache=CACHE)
        except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden), exception:
            self._log_exception(exception)
            raise
        except Exception, exception:
            self._log_exception(exception)
            raise DAV_Error(500)
        return res

    def _get_dav_getcontenttype(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or self.is_collection(uri):
            return "text/html"
        pool = Pool(Transaction().cursor.database_name)
        Collection = pool.get('webdav.collection')
        try:
            res = Collection.get_contenttype(dburi, cache=CACHE)
        except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden), exception:
            self._log_exception(exception)
            raise
        except Exception, exception:
            self._log_exception(exception)
            raise DAV_Error(500)
        return res

    def _get_dav_getetag(self, uri):
        return '"' + str(self.get_lastmodified(uri)) + '"'

    def get_creationdate(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return time.time()
        pool = Pool(Transaction().cursor.database_name)
        Collection = pool.get('webdav.collection')
        try:
            res = Collection.get_creationdate(dburi, cache=CACHE)
        except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden), exception:
            self._log_exception(exception)
            raise
        except Exception, exception:
            self._log_exception(exception)
            raise DAV_Error(500)
        return res

    def get_lastmodified(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return time.time()
        pool = Pool(Transaction().cursor.database_name)
        Collection = pool.get('webdav.collection')
        try:
            res = Collection.get_lastmodified(dburi, cache=CACHE)
        except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden), exception:
            self._log_exception(exception)
            raise
        except Exception, exception:
            self._log_exception(exception)
            raise DAV_Error(500)
        return res

    def rmcol(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return 403
        pool = Pool(Transaction().cursor.database_name)
        Collection = pool.get('webdav.collection')
        try:
            res = Collection.rmcol(dburi, cache=CACHE)
            Transaction().cursor.commit()
        except Exception, exception:
            self._log_exception(exception)
            Transaction().cursor.rollback()
            return 500
        return res

    def rm(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return 403
        pool = Pool(Transaction().cursor.database_name)
        Collection = pool.get('webdav.collection')
        try:
            res = Collection.rm(dburi, cache=CACHE)
            Transaction().cursor.commit()
        except Exception, exception:
            self._log_exception(exception)
            Transaction().cursor.rollback()
            return 500
        return res

    def exists(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return 1
        pool = Pool(Transaction().cursor.database_name)
        Collection = pool.get('webdav.collection')
        try:
            res = Collection.exists(dburi, cache=CACHE)
        except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden), exception:
            self._log_exception(exception)
            raise
        except Exception, exception:
            self._log_exception(exception)
            raise DAV_Error(500)
        return res

    def is_collection(self, uri):
        if self._get_dav_resourcetype(uri) == COLLECTION:
            return 1
        return 0

    def copyone(self, src, dst, overwrite):
        return copyone(self, src, dst, overwrite)

    def copytree(self, src, dst, overwrite):
        return copytree(self, src, dst, overwrite)

    def moveone(self, src, dst, overwrite):
        return moveone(self, src, dst, overwrite)

    def movetree(self, src, dst, overwrite):
        return movetree(self, src, dst, overwrite)

    def delone(self, uri):
        return delone(self, uri)

    def deltree(self, uri):
        return deltree(self, uri)

    def copy(self, src, dst):
        content = self._get_dav_getcontenttype(src)
        data = self.get_data(src)
        self.put(dst, data, content)
        return 201

    def copycol(self, src, dst):
        return self.mkcol(dst)

    def _get_dav_current_user_privilege_set(self, uri):
        dbname, dburi = self._get_dburi(uri)
        privileges = []
        if not dbname or not dburi:
            privileges = ['create', 'read', 'write', 'delete']
        else:
            pool = Pool(Transaction().cursor.database_name)
            try:
                Collection = pool.get('webdav.collection')
                privileges = Collection.current_user_privilege_set(dburi,
                        cache=CACHE)
            except KeyError:
                pass
            except Exception, exception:
                self._log_exception(exception)
                pass
        doc = domimpl.createDocument(None, 'privilege', None)
        privilege = doc.documentElement
        privilege.tagName = 'D:privilege'
        if 'create' in privileges:
            bind = doc.createElement('D:bind')
            privilege.appendChild(bind)
        if 'read' in privileges:
            read = doc.createElement('D:read')
            privilege.appendChild(read)
            read_acl = doc.createElement('D:read-acl')
            privilege.appendChild(read_acl)
        if 'write' in privileges:
            write = doc.createElement('D:write')
            privilege.appendChild(write)
            write_content = doc.createElement('D:write-content')
            privilege.appendChild(write_content)
            write_properties = doc.createElement('D:write-properties')
            privilege.appendChild(write_properties)
        if 'delete' in privileges:
            unbind = doc.createElement('D:unbind')
            privilege.appendChild(unbind)
        return privilege

TrytonDAVInterface.PROPS['DAV:'] = tuple(list(TrytonDAVInterface.PROPS['DAV:']
    ) + ['current-user-privilege-set'])


class WebDAVAuthRequestHandler(WebDAVServer.DAVRequestHandler):

    def finish(self):
        WebDAVServer.DAVRequestHandler.finish(self)

        global CACHE
        CACHE = LocalDict()
        if not Transaction().cursor:
            return
        dbname = Transaction().cursor.database_name
        Transaction().stop()
        if dbname:
            with Transaction().start(dbname, 0):
                Cache.resets(dbname)

    def parse_request(self):
        if not BaseHTTPServer.BaseHTTPRequestHandler.parse_request(self):
            return False

        authorization = self.headers.get('Authorization', '')
        if authorization:
            scheme, credentials = authorization.split()
            if scheme != 'Basic':
                self.send_error(501)
                return False
            credentials = base64.decodestring(credentials)
            user, password = credentials.split(':', 2)
            if not self.get_userinfo(user, password, self.command):
                self.send_autherror(401, "Authorization Required")
                return False
        else:
            if not self.get_userinfo(None, None, self.command):
                self.send_autherror(401, "Authorization Required")
                return False
        return True

    def get_userinfo(self, user, password, command=''):
        path = urlparse.urlparse(self.path).path
        dbname = urllib.unquote_plus(path.split('/', 2)[1])
        database = backend.get('Database')().connect()
        cursor = database.cursor()
        databases = database.list(cursor)
        cursor.close()
        if not dbname or dbname not in databases:
            return True
        if user:
            user = int(login(dbname, user, password, cache=False))
            if not user:
                return None
        else:
            url = urlparse.urlparse(self.path)
            query = urlparse.parse_qs(url.query)
            path = url.path[len(dbname) + 2:]
            if 'key' in query:
                key, = query['key']
                with Transaction().start(dbname, 0) as transaction:
                    database_list = Pool.database_list()
                    pool = Pool(dbname)
                    if dbname not in database_list:
                        pool.init()
                    Share = pool.get('webdav.share')
                    user = Share.get_login(key, command, path)
                    transaction.cursor.commit()
            if not user:
                return None

        Transaction().start(dbname, user, context={
                '_check_access': True,
                })
        Cache.clean(dbname)
        return user


class SecureWebDAVAuthRequestHandler(WebDAVAuthRequestHandler):

    def setup(self):
        self.request = SSLSocket(self.request)
        WebDAVAuthRequestHandler.setup(self)
