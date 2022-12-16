#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.protocols.sslsocket import SSLSocket
from trytond.config import CONFIG
from trytond.security import login
from trytond.version import PACKAGE, VERSION, WEBSITE
from trytond.tools.misc import Cache, LocalDict
from trytond.backend import Database
from trytond.pool import Pool
import threading
import SocketServer
import socket
import os
import BaseHTTPServer
import urlparse
import base64
import time
from DAV import AuthServer, WebDAVServer, iface
from DAV.errors import *
from DAV.constants import COLLECTION, OBJECT
from DAV.utils import get_uriparentpath, get_urifilename, quote_uri
from DAV.davcmd import copyone, copytree, moveone, movetree, delone, deltree
import urllib

# Local int for multi-thread
import sys
from threading import local


class LocalInt(local):

    def __init__(self, value=0):
        self.value = value

    def __int__(self):
        return int(self.value)

USER_ID = LocalInt(0)
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
            except:
                return default


    class _Config:
        DAV = DAV()

    WebDAVServer.DAVRequestHandler._config = _Config()


class BaseThreadedHTTPServer(SocketServer.ThreadingMixIn,
        BaseHTTPServer.HTTPServer):
    timeout = 1
    max_children = CONFIG['max_thread']

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET,
                socket.SO_REUSEADDR, 1)
        BaseHTTPServer.HTTPServer.server_bind(self)


class SecureThreadedHTTPServer(BaseThreadedHTTPServer):

    def __init__(self, server_address, HandlerClass):
        BaseThreadedHTTPServer.__init__(self, server_address, HandlerClass)
        self.socket = SSLSocket(socket.socket(self.address_family,
                                              self.socket_type))
        self.server_bind()
        self.server_activate()


class WebDAVServerThread(threading.Thread):

    def __init__(self, interface, port, secure=False):
        threading.Thread.__init__(self)
        self.secure = secure
        self.running = False
        ipv6 = False
        if socket.has_ipv6:
            try:
                socket.getaddrinfo(interface or None, port, socket.AF_INET6)
                ipv6 = True
            except:
                pass
        if secure:
            handler_class = SecureWebDAVAuthRequestHandler
            server_class = SecureThreadedHTTPServer
            if ipv6:
                server_class = SecureThreadedHTTPServer6
        else:
            handler_class = WebDAVAuthRequestHandler
            server_class = BaseThreadedHTTPServer
            if ipv6:
                server_class = BaseThreadedHTTPServer6
        handler_class.IFACE_CLASS = TrytonDAVInterface(interface, port, secure)
        self.server = server_class((interface, port), handler_class)

    def stop(self):
        self.running = False
        if os.name != 'nt':
            if hasattr(socket, 'SHUT_RDWR'):
                self.server.socket.shutdown(socket.SHUT_RDWR)
            else:
                self.server.socket.shutdown(2)
        self.server.socket.close()

    def run(self):
        self.running = True
        while self.running:
            self.server.handle_request()
        return True


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
        self.baseuri = '%s://%s:%s/' % (protocol, interface or socket.gethostname(), port)
        self.verbose = False

    def _get_dburi(self, uri):
        uri = urlparse.urlsplit(uri)[2]
        if uri and uri[0] == '/':
            uri = uri[1:]
        dbname, uri = (uri.split('/', 1) + [None])[0:2]
        if dbname:
            dbname = urllib.unquote_plus(dbname)
        if uri:
            uri = urllib.unquote_plus(uri)
        return dbname, uri

    def get_childs(self, uri):
        res = []
        dbname, dburi = self._get_dburi(uri)
        if not dbname:
            database = Database().connect()
            try:
                try:
                    cursor = database.cursor()
                    lists = database.list(cursor)
                except:
                    lists = []
            finally:
                cursor.close()
            for dbname in lists:
                res.append(urlparse.urljoin(self.baseuri, dbname))
            return res
        database = Database(dbname).connect()
        cursor = database.cursor()
        database_list = Pool.database_list()
        pool = Pool(dbname)
        if not dbname in database_list:
            pool.init()
        try:
            try:
                collection_obj = pool.get('webdav.collection')
                if uri[-1:] != '/':
                    uri += '/'
                for child in collection_obj.get_childs(cursor, int(USER_ID), dburi,
                        cache=CACHE):
                    res.append(urlparse.urljoin(self.baseuri,
                        uri + child.encode('utf-8')))
            except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden):
                raise
            except:
                raise DAV_Error(500)
        finally:
            cursor.close()
        return res

    def get_data(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or (self.exists(uri) and self.is_collection(uri)):
            res = '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">'
            res += '<html>'
            res += '<head>'
            res += '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
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
        database = Database(dbname).connect()
        cursor = database.cursor()
        database_list = Pool.database_list()
        pool = Pool(dbname)
        if not dbname in database_list:
            pool.init()
        collection_obj = pool.get('webdav.collection')
        try:
            try:
                res = collection_obj.get_data(cursor, int(USER_ID), dburi,
                        cache=CACHE)
            except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden):
                raise
            except:
                raise DAV_Error(500)
        finally:
            cursor.close()
        return res

    def put(self, uri, data, content_type=''):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            raise DAV_Forbidden
        database = Database(dbname).connect()
        cursor = database.cursor()
        database_list = Pool.database_list()
        pool = Pool(dbname)
        if not dbname in database_list:
            pool.init()
        collection_obj = pool.get('webdav.collection')
        try:
            try:
                res = collection_obj.put(cursor, int(USER_ID), dburi, data,
                        content_type, cache=CACHE)
                cursor.commit()
            except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden):
                cursor.rollback()
                raise
            except:
                cursor.rollback()
                raise DAV_Error(500)
        finally:
            cursor.close()
        return res

    def mkcol(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            raise DAV_Forbidden
        database = Database(dbname).connect()
        cursor = database.cursor()
        database_list = Pool.database_list()
        pool = Pool(dbname)
        if not dbname in database_list:
            pool.init()
        collection_obj = pool.get('webdav.collection')
        try:
            try:
                res = collection_obj.mkcol(cursor, int(USER_ID), dburi,
                        cache=CACHE)
                cursor.commit()
            except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden):
                cursor.rollback()
                raise
            except:
                cursor.rollback()
                raise DAV_Error(500)
        finally:
            cursor.close()
        return res

    def _get_dav_resourcetype(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return COLLECTION
        database = Database(dbname).connect()
        cursor = database.cursor()
        database_list = Pool.database_list()
        pool = Pool(dbname)
        if not dbname in database_list:
            pool.init()
        collection_obj = pool.get('webdav.collection')
        try:
            try:
                res = collection_obj.get_resourcetype(cursor, int(USER_ID), dburi,
                    cache=CACHE)
            except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden):
                raise
            except:
                raise DAV_Error(500)
        finally:
            cursor.close()
        return res

    def _get_dav_displayname(self, uri):
        raise DAV_Secret

    def _get_dav_getcontentlength(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return '0'
        database = Database(dbname).connect()
        cursor = database.cursor()
        database_list = Pool.database_list()
        pool = Pool(dbname)
        if not dbname in database_list:
            pool.init()
        collection_obj = pool.get('webdav.collection')
        try:
            try:
                res = collection_obj.get_contentlength(cursor, int(USER_ID), dburi,
                        cache=CACHE)
            except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden):
                raise
            except:
                raise DAV_Error(500)
        finally:
            cursor.close()
        return res

    def _get_dav_getcontenttype(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or self.is_collection(uri):
            return "text/html"
        database = Database(dbname).connect()
        cursor = database.cursor()
        database_list = Pool.database_list()
        pool = Pool(dbname)
        if not dbname in database_list:
            pool.init()
        collection_obj = pool.get('webdav.collection')
        try:
            try:
                res = collection_obj.get_contenttype(cursor, int(USER_ID), dburi,
                        cache=CACHE)
            except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden):
                raise
            except:
                raise DAV_Error(500)
        finally:
            cursor.close()
        return res

    def get_creationdate(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return time.time()
        database = Database(dbname).connect()
        cursor = database.cursor()
        database_list = Pool.database_list()
        pool = Pool(dbname)
        if not dbname in database_list:
            pool.init()
        collection_obj = pool.get('webdav.collection')
        try:
            try:
                res = collection_obj.get_creationdate(cursor, int(USER_ID), dburi,
                        cache=CACHE)
            except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden):
                raise
            except:
                raise DAV_Error(500)
        finally:
            cursor.close()
        return res

    def get_lastmodified(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return time.time()
        database = Database(dbname).connect()
        cursor = database.cursor()
        database_list = Pool.database_list()
        pool = Pool(dbname)
        if not dbname in database_list:
            pool.init()
        collection_obj = pool.get('webdav.collection')
        try:
            try:
                res = collection_obj.get_lastmodified(cursor, int(USER_ID), dburi,
                        cache=CACHE)
            except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden):
                raise
            except:
                raise DAV_Error(500)
        finally:
            cursor.close()
        return res

    def rmcol(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            raise DAV_Forbidden
        database = Database(dbname).connect()
        cursor = database.cursor()
        database_list = Pool.database_list()
        pool = Pool(dbname)
        if not dbname in database_list:
            pool.init()
        collection_obj = pool.get('webdav.collection')
        try:
            try:
                res = collection_obj.rmcol(cursor, int(USER_ID), dburi,
                        cache=CACHE)
                cursor.commit()
            except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden):
                cursor.rollback()
                raise
            except:
                cursor.rollback()
                raise DAV_Error(500)
        finally:
            cursor.close()
        return res

    def rm(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            raise DAV_Forbidden
        database = Database(dbname).connect()
        cursor = database.cursor()
        database_list = Pool.database_list()
        pool = Pool(dbname)
        if not dbname in database_list:
            pool.init()
        collection_obj = pool.get('webdav.collection')
        try:
            try:
                res = collection_obj.rm(cursor, int(USER_ID), dburi,
                        cache=CACHE)
                cursor.commit()
            except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden):
                cursor.rollback()
                raise
            except:
                cursor.rollback()
                raise DAV_Error(500)
        finally:
            cursor.close()
        return res

    def exists(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return 1
        database = Database(dbname)
        cursor = database.cursor()
        database_list = Pool.database_list()
        pool = Pool(dbname)
        if not dbname in database_list:
            pool.init()
        collection_obj = pool.get('webdav.collection')
        try:
            try:
                res = collection_obj.exists(cursor, int(USER_ID), dburi, cache=CACHE)
            except (DAV_Error, DAV_NotFound, DAV_Secret, DAV_Forbidden):
                raise
            except:
                raise DAV_Error(500)
        finally:
            cursor.close()
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


class WebDAVAuthRequestHandler(AuthServer.BufferedAuthRequestHandler,
        WebDAVServer.DAVRequestHandler):

    def get_userinfo(self, user, password, command=''):
        global USER_ID
        dbname = urllib.unquote_plus(self.path.split('/', 2)[1])
        if not dbname:
            return 1
        USER_ID = login(dbname, user, password, cache=False)
        Cache.clean(dbname)
        Cache.resets(dbname)
        if int(USER_ID):
            return 1
        return 0

class SecureWebDAVAuthRequestHandler(WebDAVAuthRequestHandler):

    def setup(self):
        self.connection = SSLSocket(self.request)
        self.rfile = socket._fileobject(self.request, "rb", self.rbufsize)
        self.wfile = socket._fileobject(self.request, "wb", self.wbufsize)
