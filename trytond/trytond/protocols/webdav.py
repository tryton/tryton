#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import SocketServer
import socket
import os
import BaseHTTPServer
import urlparse
import time
import urllib
import sys
import traceback
import logging
from threading import local
import xml.dom.minidom
from DAV import AuthServer, WebDAVServer, iface
from DAV.errors import *
from DAV.constants import COLLECTION, DAV_VERSION_1, DAV_VERSION_2
from DAV.utils import get_uriparentpath, get_urifilename, quote_uri
from DAV.davcmd import copyone, copytree, moveone, movetree, delone, deltree
from trytond.protocols.sslsocket import SSLSocket
from trytond.protocols.common import daemon
from trytond.config import CONFIG
from trytond.security import login
from trytond.version import PACKAGE, VERSION, WEBSITE
from trytond.tools.misc import LocalDict
from trytond.backend import Database
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.cache import Cache
from trytond.exceptions import UserError, UserWarning, NotLogged, \
    ConcurrencyException
_TRYTON_RELOAD = False
domimpl = xml.dom.minidom.getDOMImplementation()

DAV_VERSION_1['version'] += ',access-control'
DAV_VERSION_2['version'] += ',access-control'

# Local int for multi-thread
class LocalInt(local):

    def __init__(self, value=0):
        super(LocalInt, self).__init__()
        self.value = value

    def __int__(self):
        return int(self.value)

CACHE = LocalDict()

# Fix for bad use of Document in DAV.utils make_xmlresponse
from DAV.utils import VERSION as DAV_VERSION
if DAV_VERSION == '0.6':
    from xml.dom.Document import Document
    Document.Document = Document

# Fix for unset _config in DAVRequestHandler
if not hasattr(WebDAVServer.DAVRequestHandler, '_config'):


    class DAV:
        lockemulation = False
        verbose = False

        def getboolean(self, name):
            return bool(self.get(name))

        def get(self, name, default=None):
            try:
                return self[name]
            except Exception:
                return default


    class _Config:
        DAV = DAV()

    WebDAVServer.DAVRequestHandler._config = _Config()


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
        self.socket = SSLSocket(socket.socket(self.address_family,
                                              self.socket_type))
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
        handler_class.IFACE_CLASS = TrytonDAVInterface(interface, port, secure)
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
        if CONFIG['verbose'] and not isinstance(exception, (
                    NotLogged, ConcurrencyException, UserError, UserWarning,
                    DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden)):
            tb_s = reduce(lambda x, y: x + y,
                traceback.format_exception(*sys.exc_info()))
            logger = logging.getLogger('webdav')
            logger.error('Exception:\n' + tb_s.decode('utf-8', 'ignore'))

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
            database = Database().connect()
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
            collection_obj = pool.get('webdav.collection')
            if uri[-1:] != '/':
                uri += '/'
            for child in collection_obj.get_childs(dburi, filter=filter,
                    cache=CACHE):
                res.append(uri + child.encode('utf-8'))
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
            res = '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 '\
                    'Transitional//EN">'
            res += '<html>'
            res += '<head>'
            res += '<meta http-equiv="Content-Type" content="text/html; '\
                    'charset=utf-8">'
            res += '<title>%s - WebDAV - %s</title>' \
                    % (PACKAGE, dbname or 'root')
            res += '</head>'
            res += '<body>'
            res += '<h2>Collection: %s</h2>' % (get_urifilename(uri) or '/')
            res += '<ul>'
            if dbname:
                res += '<li><a href="%s">..</a></li>' \
                        % (quote_uri(get_uriparentpath(uri) or '/'))
            childs = self.get_childs(uri)
            childs.sort()
            for child in childs:
                res += '<li><a href="%s">%s</a></li>' \
                        % (quote_uri(child), get_urifilename(child))
            res += '</ul>'
            res += '<hr noshade>'
            res += '<em>Powered by <a href="%s">%s</a> version %s</em>' \
                    % (quote_uri(WEBSITE), PACKAGE, VERSION)
            res += '</body>'
            res += '</html>'
            return res
        pool = Pool(Transaction().cursor.database_name)
        collection_obj = pool.get('webdav.collection')
        try:
            res = collection_obj.get_data(dburi, cache=CACHE)
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
        collection_obj = pool.get('webdav.collection')
        try:
            res = collection_obj.put(dburi, data, content_type, cache=CACHE)
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
        collection_obj = pool.get('webdav.collection')
        try:
            res = collection_obj.mkcol(dburi, cache=CACHE)
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
        collection_obj = pool.get('webdav.collection')
        try:
            res = collection_obj.get_resourcetype(dburi, cache=CACHE)
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
            collection_obj = pool.get('webdav.collection')
            res = collection_obj.get_displayname(dburi, cache=CACHE)
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
        collection_obj = pool.get('webdav.collection')
        try:
            res = collection_obj.get_contentlength(dburi, cache=CACHE)
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
        collection_obj = pool.get('webdav.collection')
        try:
            res = collection_obj.get_contenttype(dburi, cache=CACHE)
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
        collection_obj = pool.get('webdav.collection')
        try:
            res = collection_obj.get_creationdate(dburi, cache=CACHE)
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
        collection_obj = pool.get('webdav.collection')
        try:
            res = collection_obj.get_lastmodified(dburi, cache=CACHE)
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
        collection_obj = pool.get('webdav.collection')
        try:
            res = collection_obj.rmcol(dburi, cache=CACHE)
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
        collection_obj = pool.get('webdav.collection')
        try:
            res = collection_obj.rm(dburi, cache=CACHE)
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
        collection_obj = pool.get('webdav.collection')
        try:
            res = collection_obj.exists(dburi, cache=CACHE)
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
                collection_obj = pool.get('webdav.collection')
                privileges = collection_obj.current_user_privilege_set(dburi,
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


class WebDAVAuthRequestHandler(AuthServer.BufferedAuthRequestHandler,
        WebDAVServer.DAVRequestHandler):

    def finish(self):
        global CACHE
        CACHE = LocalDict()
        if not Transaction().cursor:
            return
        dbname = Transaction().cursor.database_name
        Transaction().stop()
        if dbname:
            Cache.resets(dbname)

    def get_userinfo(self, user, password, command=''):
        dbname = urllib.unquote_plus(self.path.split('/', 2)[1])
        database = Database().connect()
        cursor = database.cursor()
        databases = database.list(cursor)
        cursor.close()
        if not dbname or dbname not in databases:
            return 1
        user = int(login(dbname, user, password, cache=False))

        Transaction().start(dbname, user)
        Cache.clean(dbname)
        database_list = Pool.database_list()
        pool = Pool(dbname)
        if not dbname in database_list:
            pool.init()
        if user:
            return 1
        return 0

class SecureWebDAVAuthRequestHandler(WebDAVAuthRequestHandler):

    def setup(self):
        self.connection = SSLSocket(self.request)
        self.rfile = socket._fileobject(self.request, "rb", self.rbufsize)
        self.wfile = socket._fileobject(self.request, "wb", self.wbufsize)
