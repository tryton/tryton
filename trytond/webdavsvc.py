#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import urlparse
import socket
import base64
import time
from DAV import AuthServer, WebDAVServer, iface
from DAV.errors import *
from DAV.constants import COLLECTION, OBJECT
from DAV.utils import get_uriparentpath, get_urifilename, quote_uri
from DAV.davcmd import copyone, copytree, moveone, movetree, delone, deltree
from netsvc import LocalService, SSLSocket
import security
import pooler
from version import PACKAGE, VERSION, WEBSITE
from tools.misc import Cache

# Local int for multi-thread
import sys
if sys.version_info[:2] < (2, 4):
    from threadinglocal import local
else:
    from threading import local


class LocalInt(local):

    def __init__(self, value=0):
        self.value = value

    def __int__(self):
        return int(self.value)

USER_ID = LocalInt(0)

# Fix for bad use of Document in DAV.utils make_xmlresponse
from DAV.utils import VERSION as DAV_VERSION
if DAV_VERSION == '0.6':
    from xml.dom.Document import Document
    Document.Document = Document

# Fix for unset _config in DAVRequestHandler
if DAV_VERSION == '0.8':


    class DAV:
        lockemulation = False
        verbose = False


    class _Config:
        DAV = DAV()

    WebDAVServer.DAVRequestHandler._config = _Config()


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
        if uri[0] == '/':
            uri = uri[1:]
        dbname, uri = (uri.split('/', 1) + [None])[0:2]
        return dbname, uri

    def get_childs(self, uri):
        res = []
        dbname, dburi = self._get_dburi(uri)
        if not dbname:
            db = LocalService('db')
            for dbname in db.list():
                res.append(urlparse.urljoin(self.baseuri, dbname))
            return res
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        collection_obj = pool.get('webdav.collection')
        if uri[-1:] != '/':
            uri += '/'
        for child in collection_obj.get_childs(cursor, int(USER_ID), dburi):
            res.append(urlparse.urljoin(self.baseuri, uri + child))
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
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        collection_obj = pool.get('webdav.collection')
        try:
            res = collection_obj.get_data(cursor, int(USER_ID), dburi)
        finally:
            cursor.close()
        return res

    def put(self, uri, data, content_type=''):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            raise DAV_Forbidden
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        collection_obj = pool.get('webdav.collection')
        try:
            try:
                res = collection_obj.put(cursor, int(USER_ID), dburi, data,
                        content_type)
                cursor.commit()
            except:
                cursor.rollback()
                raise
        finally:
            cursor.close()
        return res

    def mkcol(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            raise DAV_Forbidden
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        collection_obj = pool.get('webdav.collection')
        try:
            try:
                res = collection_obj.mkcol(cursor, int(USER_ID), dburi)
                cursor.commit()
            except:
                cursor.rollback()
                raise
        finally:
            cursor.close()
        return res

    def _get_dav_resourcetype(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return COLLECTION
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        collection_obj = pool.get('webdav.collection')
        res = collection_obj.get_resourcetype(cursor, int(USER_ID), dburi)
        cursor.close()
        return res

    def _get_dav_displayname(self, uri):
        raise DAV_Secret

    def _get_dav_getcontentlength(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return '0'
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        collection_obj = pool.get('webdav.collection')
        res = collection_obj.get_contentlength(cursor, int(USER_ID), dburi)
        cursor.close()
        return res

    def _get_dav_getcontenttype(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or self.is_collection(uri):
            return "text/html"
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        collection_obj = pool.get('webdav.collection')
        res = collection_obj.get_contenttype(cursor, int(USER_ID), dburi)
        cursor.close()
        return res

    def get_creationdate(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return time.time()
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        collection_obj = pool.get('webdav.collection')
        res = collection_obj.get_creationdate(cursor, int(USER_ID), dburi)
        cursor.close()
        return res

    def get_lastmodified(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return time.time()
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        collection_obj = pool.get('webdav.collection')
        res = collection_obj.get_lastmodified(cursor, int(USER_ID), dburi)
        cursor.close()
        return res

    def rmcol(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            raise DAV_Forbidden
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        collection_obj = pool.get('webdav.collection')
        try:
            try:
                res = collection_obj.rmcol(cursor, int(USER_ID), dburi)
                cursor.commit()
            except:
                cursor.rollback()
                raise
        finally:
            cursor.close()
        return res

    def rm(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            raise DAV_Forbidden
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        collection_obj = pool.get('webdav.collection')
        try:
            try:
                res = collection_obj.rm(cursor, int(USER_ID), dburi)
                cursor.commit()
            except:
                cursor.rollback()
                raise
        finally:
            cursor.close()
        return res

    def exists(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return 1
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        collection_obj = pool.get('webdav.collection')
        res = collection_obj.exists(cursor, int(USER_ID), dburi)
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
        dbname = self.path.split('/', 2)[1]
        if not dbname:
            return 1
        USER_ID = security.login(dbname, user, password, cache=False)
        Cache.clean(dbname)
        if int(USER_ID):
            return 1
        return 0

class SecureWebDAVAuthRequestHandler(WebDAVAuthRequestHandler):

    def setup(self):
        self.connection = SSLSocket(self.request)
        self.rfile = socket._fileobject(self.request, "rb", self.rbufsize)
        self.wfile = socket._fileobject(self.request, "wb", self.wbufsize)
