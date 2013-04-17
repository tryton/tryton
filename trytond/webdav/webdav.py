#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os
import time
import urllib
import urlparse
import socket
import encodings
import uuid
import datetime
from dateutil.relativedelta import relativedelta
from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import reduce_ids, safe_eval
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.config import CONFIG
from trytond.pyson import Eval


def get_webdav_url():
    if CONFIG['ssl_webdav']:
        protocol = 'https'
    else:
        protocol = 'http'
    hostname = (CONFIG['hostname_webdav']
        or unicode(socket.getfqdn(), 'utf8'))
    hostname = '.'.join(encodings.idna.ToASCII(part) for part in
        hostname.split('.'))
    return urlparse.urlunsplit((protocol, hostname,
        urllib.quote(Transaction().cursor.database_name + '/'), None, None))


class Collection(ModelSQL, ModelView):
    "Collection"
    _name = "webdav.collection"
    _description = __doc__
    name = fields.Char('Name', required=True, select=True)
    parent = fields.Many2One('webdav.collection', 'Parent',
       ondelete='RESTRICT', domain=[('model', '=', None)])
    childs = fields.One2Many('webdav.collection', 'parent', 'Children')
    model = fields.Many2One('ir.model', 'Model')
    domain = fields.Char('Domain')
    complete_name = fields.Function(fields.Char('Complete Name',
            order_field='name'), 'get_rec_name')

    def __init__(self):
        super(Collection, self).__init__()
        self._sql_constraints += [
            ('name_parent_uniq', 'UNIQUE (name, parent)',
                'The collection name must be unique inside a collection!'),
        ]
        self._constraints += [
            ('check_recursion', 'recursive_collections'),
            ('check_attachment', 'collection_file_name'),
        ]
        self._error_messages.update({
            'recursive_collections': 'You can not create recursive ' \
                    'collections!',
            'collection_file_name': 'You can not create a collection\n' \
                    'in a collection with the name of an ' \
                    'existing file!',
        })
        self.ext2mime = {
            '.png': 'image/png',
            '.odt': 'application/vnd.oasis.opendocument.text',
            '.pdf': 'application/pdf',
        }

    def default_domain(self):
        return '[]'

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        names = {}

        def _name(collection):
            if collection.id in names:
                return names[collection.id]
            elif collection.parent:
                return _name(collection.parent) + '/' + collection.name
            else:
                return collection.name
        for collection in self.browse(ids):
            names[collection.id] = _name(collection)
        return names

    def check_attachment(self, ids):
        pool = Pool()
        attachment_obj = pool.get('ir.attachment')
        for collection in self.browse(ids):
            if collection.parent:
                attachment_ids = attachment_obj.search([
                    ('resource', '=', '%s,%s' %
                        (self._name, collection.parent.id)),
                    ])
                for attachment in attachment_obj.browse(attachment_ids):
                    if attachment.name == collection.name:
                        return False
        return True

    def _uri2object(self, uri, object_name=_name, object_id=None, cache=None):
        pool = Pool()
        attachment_obj = pool.get('ir.attachment')
        report_obj = pool.get('ir.action.report')
        cache_uri = uri

        if cache is not None:
            cache.setdefault('_uri2object', {})
            if cache_uri in cache['_uri2object']:
                return cache['_uri2object'][cache_uri]

        if not uri:
            if cache is not None:
                cache['_uri2object'][cache_uri] = (self._name, None)
            return self._name, None
        name, uri = (uri.split('/', 1) + [None])[0:2]
        if object_name == self._name:
            collection_ids = None
            if cache is not None:
                cache.setdefault('_parent2collection_ids', {})
                if object_id in cache['_parent2collection_ids']:
                    collection_ids = cache['_parent2collection_ids'][
                        object_id].get(name, [])
            if collection_ids is None:
                collection_ids = self.search([
                    ('parent', '=', object_id),
                    ])
                collections = self.browse(collection_ids)
                collection_ids = []
                if cache is not None:
                    cache['_parent2collection_ids'].setdefault(object_id, {})
                for collection in collections:
                    if cache is not None:
                        cache['_parent2collection_ids'][object_id]\
                                .setdefault(collection.name, [])
                        cache['_parent2collection_ids'][object_id][
                            collection.name].append(collection.id)
                        cache.setdefault('_collection_name', {})
                        if collection.model and uri:
                            cache['_collection_name'][collection.id] = \
                                collection.model.model
                        else:
                            cache['_collection_name'][collection.id] = \
                                self._name
                    if collection.name == name:
                        collection_ids.append(collection.id)
            if collection_ids:
                object_id = collection_ids[0]
                object_name2 = None
                if cache is not None:
                    cache.setdefault('_collection_name', {})
                    if object_id in cache['_collection_name']:
                        object_name2 = cache['_collection_name'][object_id]
                if object_name2 is None:
                    collection = self.browse(object_id)
                    if collection.model and uri:
                        object_name = collection.model.model
                        if cache is not None:
                            cache['_collection_name'][object_id] = object_name
                else:
                    object_name = object_name2
            else:
                if uri:
                    if cache is not None:
                        cache['_uri2object'][cache_uri] = (None, 0)
                    return None, 0

                attachment_ids = None
                if cache is not None:
                    cache.setdefault('_model&id2attachment_ids', {})
                    if (object_name, object_id) in \
                            cache['_model&id2attachment_ids']:
                        attachment_ids = cache['_model&id2attachment_ids'][
                            (object_name, object_id)].get(name, [])
                attachment_id = None
                if attachment_ids is None:
                    attachment_ids = attachment_obj.search([
                        ('resource', '=', '%s,%s' % (object_name, object_id)),
                        ])
                    attachments = attachment_obj.browse(attachment_ids)
                    key = (object_name, object_id)
                    attachment_ids = []
                    if cache is not None:
                        cache['_model&id2attachment_ids'].setdefault(key, {})
                    for attachment in attachments:
                        if cache is not None:
                            cache.setdefault('_model&id&name2attachment_ids',
                                    {})
                            cache['_model&id&name2attachment_ids'].setdefault(
                                    key, {})
                            cache['_model&id&name2attachment_ids'][key]\
                                    .setdefault(attachment.name, [])
                            cache['_model&id&name2attachment_ids'][key][
                                attachment.name].append(attachment.id)
                        if attachment.name == name:
                            attachment_id = attachment.id
                else:
                    key = (object_name, object_id)
                    cache.setdefault('_model&id&name2attachment_ids', {})
                    cache['_model&id&name2attachment_ids'].setdefault(key, {})
                    attachment_id = cache['_model&id&name2attachment_ids'][
                        key].get(name, [None])[0]
                if attachment_id:
                    object_name = 'ir.attachment'
                    object_id = attachment_id
                else:
                    object_name = None
                    object_id = None
        else:
            splitted_name = name.rsplit('-', 1)
            if len(splitted_name) != 2:
                if cache is not None:
                    cache['_uri2object'][cache_uri] = (object_name, 0)
                return object_name, 0
            object_id = int(splitted_name[1].strip())
            if uri:
                if '/' in uri:
                    if cache is not None:
                        cache['_uri2object'][cache_uri] = (None, 0)
                    return None, 0
                report_ids = report_obj.search([
                    ('model', '=', object_name),
                    ])
                reports = report_obj.browse(report_ids)
                for report in reports:
                    report_name = report.name + '-' + str(report.id) \
                            + '.' + report.extension
                    if uri == report_name:
                        if cache is not None:
                            cache['_uri2object'][cache_uri] = \
                                    ('ir.action.report', object_id)
                        return 'ir.action.report', object_id
                name = uri
                attachment_ids = None
                if cache is not None:
                    cache.setdefault('_model&id2attachment_ids', {})
                    if (object_name, object_id) in \
                            cache['_model&id2attachment_ids']:
                        attachment_ids = cache['_model&id2attachment_ids'][
                            (object_name, object_id)].get(name, [])
                if attachment_ids is None:
                    attachment_ids = attachment_obj.search([
                        ('resource', '=', '%s,%s' % (object_name, object_id)),
                        ])
                    attachments = attachment_obj.browse(attachment_ids)
                    key = (object_name, object_id)
                    attachment_ids = []
                    if cache is not None:
                        cache['_model&id2attachment_ids'].setdefault(key, {})
                    for attachment in attachments:
                        if cache is not None:
                            cache['_model&id2attachment_ids'][key]\
                                    .setdefault(attachment.name, [])
                            cache['_model&id2attachment_ids'][key][
                                attachment.name].append(attachment.id)
                        if attachment.name == name:
                            attachment_ids.append(attachment.id)
                if attachment_ids:
                    object_name = 'ir.attachment'
                    object_id = attachment_ids[0]
                else:
                    object_name = None
                    object_id = None
                if cache is not None:
                    cache['_uri2object'][cache_uri] = (object_name, object_id)
                return object_name, object_id
        if uri:
            res = self._uri2object(uri, object_name, object_id, cache=cache)
            if cache is not None:
                cache['_uri2object'][cache_uri] = res
            return res
        if cache is not None:
            cache['_uri2object'][cache_uri] = (object_name, object_id)
        return object_name, object_id

    def get_childs(self, uri, filter=None, cache=None):
        pool = Pool()
        report_obj = pool.get('ir.action.report')
        res = []
        if filter:
            return []
        if not uri:
            collection_ids = self.search([
                ('parent', '=', None),
                ])
            for collection in self.browse(collection_ids):
                if '/' in collection.name:
                    continue
                res.append(collection.name)
                if cache is not None:
                    cache.setdefault(self._name, {})
                    cache[self._name][collection.id] = {}
            return res
        object_name, object_id = self._uri2object(uri, cache=cache)
        if object_name == self._name and object_id:
            collection = self.browse(object_id)
            if collection.model:
                model_obj = pool.get(collection.model.model)
                if not model_obj:
                    return res
                model_ids = model_obj.search(
                        safe_eval(collection.domain or "[]"))
                for child in model_obj.browse(model_ids):
                    if '/' in child.rec_name:
                        continue
                    res.append(child.rec_name + '-' + str(child.id))
                    if cache is not None:
                        cache.setdefault(model_obj._name, {})
                        cache[model_obj._name][child.id] = {}
                return res
            else:
                for child in collection.childs:
                    if '/' in child.name:
                        continue
                    res.append(child.name)
                    if cache is not None:
                        cache.setdefault(self._name, {})
                        cache[self._name][child.id] = {}
        if object_name not in ('ir.attachment', 'ir.action.report'):
            report_ids = report_obj.search([
                ('model', '=', object_name),
                ])
            reports = report_obj.browse(report_ids)
            for report in reports:
                report_name = report.name + '-' + str(report.id) \
                        + '.' + report.extension
                if '/' in report_name:
                    continue
                res.append(report_name)
                if cache is not None:
                    cache.setdefault(report_obj._name, {})
                    cache[report_obj._name][report.id] = {}

            attachment_obj = pool.get('ir.attachment')
            attachment_ids = attachment_obj.search([
                ('resource', '=', '%s,%s' % (object_name, object_id)),
                ])
            for attachment in attachment_obj.browse(attachment_ids):
                if attachment.name and not attachment.link:
                    if '/' in attachment.name:
                        continue
                    res.append(attachment.name)
                    if cache is not None:
                        cache.setdefault(attachment_obj._name, {})
                        cache[attachment_obj._name][attachment.id] = {}
        return res

    def get_resourcetype(self, uri, cache=None):
        from pywebdav.lib.constants import COLLECTION, OBJECT
        object_name, object_id = self._uri2object(uri, cache=cache)
        if object_name in ('ir.attachment', 'ir.action.report'):
            return OBJECT
        return COLLECTION

    def get_displayname(self, uri, cache=None):
        object_name, object_id = self._uri2object(uri, cache=cache)
        model_obj = Pool().get(object_name)
        return model_obj.browse(object_id).rec_name

    def get_contentlength(self, uri, cache=None):
        pool = Pool()
        attachment_obj = pool.get('ir.attachment')

        object_name, object_id = self._uri2object(uri, cache=cache)
        if object_name == 'ir.attachment':

            if cache is not None:
                cache.setdefault('ir.attachment', {})
                ids = cache['ir.attachment'].keys()
                if object_id not in ids:
                    ids.append(object_id)
                elif 'contentlength' in cache['ir.attachment'][object_id]:
                    return cache['ir.attachment'][object_id]['contentlength']
            else:
                ids = [object_id]

            attachments = attachment_obj.browse(ids)

            res = '0'
            for attachment in attachments:
                size = '0'
                try:
                    if attachment.data_size:
                        size = str(attachment.data_size)
                except Exception:
                    pass
                if attachment.id == object_id:
                    res = size
                if cache is not None:
                    cache['ir.attachment'].setdefault(attachment.id, {})
                    cache['ir.attachment'][attachment.id]['contentlength'] = \
                            size
            return res
        return '0'

    def get_contenttype(self, uri, cache=None):
        object_name, object_id = self._uri2object(uri, cache=cache)
        if object_name in ('ir.attachment', 'ir.action.report'):
            ext = os.path.splitext(uri)[1]
            if not ext:
                return "application/octet-stream"
            return self.ext2mime.get(ext, 'application/octet-stream')
        return "application/octet-stream"

    def get_creationdate(self, uri, cache=None):
        pool = Pool()
        object_name, object_id = self._uri2object(uri, cache=cache)
        if object_name == 'ir.attachment':
            model_obj = pool.get(object_name)
            if object_id:
                if cache is not None:
                    cache.setdefault(model_obj._name, {})
                    ids = cache[model_obj._name].keys()
                    if object_id not in ids:
                        ids.append(object_id)
                    elif 'creationdate' in cache[model_obj._name][object_id]:
                        return cache[model_obj._name][object_id][
                            'creationdate']
                else:
                    ids = [object_id]
                res = None
                cursor = Transaction().cursor
                for i in range(0, len(ids), cursor.IN_MAX):
                    sub_ids = ids[i:i + cursor.IN_MAX]
                    red_sql, red_ids = reduce_ids('id', sub_ids)
                    cursor.execute('SELECT id, '
                        'EXTRACT(epoch FROM create_date) '
                        'FROM "' + model_obj._table + '" '
                        'WHERE ' + red_sql, red_ids)
                    for object_id2, date in cursor.fetchall():
                        if object_id2 == object_id:
                            res = date
                        if cache is not None:
                            cache[model_obj._name].setdefault(object_id2, {})
                            cache[model_obj._name][object_id2][
                                'creationdate'] = date
                if res is not None:
                    return res
        return time.time()

    def get_lastmodified(self, uri, cache=None):
        pool = Pool()
        object_name, object_id = self._uri2object(uri, cache=cache)
        if object_name == 'ir.attachment':
            model_obj = pool.get(object_name)
            if object_id:
                if cache is not None:
                    cache.setdefault(model_obj._name, {})
                    ids = cache[model_obj._name].keys()
                    if object_id not in ids:
                        ids.append(object_id)
                    elif 'lastmodified' in cache[model_obj._name][object_id]:
                        return cache[model_obj._name][object_id][
                            'lastmodified']
                else:
                    ids = [object_id]
                res = None
                cursor = Transaction().cursor
                for i in range(0, len(ids), cursor.IN_MAX):
                    sub_ids = ids[i:i + cursor.IN_MAX]
                    red_sql, red_ids = reduce_ids('id', sub_ids)
                    cursor.execute('SELECT id, '
                        'EXTRACT(epoch FROM '
                            'COALESCE(write_date, create_date)) '
                        'FROM "' + model_obj._table + '" '
                        'WHERE ' + red_sql, red_ids)
                    for object_id2, date in cursor.fetchall():
                        if object_id2 == object_id:
                            res = date
                        if cache is not None:
                            cache[model_obj._name].setdefault(object_id2, {})
                            cache[model_obj._name][object_id2][
                                'lastmodified'] = date
                if res is not None:
                    return res
        return time.time()

    def get_data(self, uri, cache=None):
        from pywebdav.lib.errors import DAV_NotFound
        pool = Pool()
        attachment_obj = pool.get('ir.attachment')
        report_obj = pool.get('ir.action.report')

        if uri:
            object_name, object_id = self._uri2object(uri, cache=cache)

            if object_name == 'ir.attachment' and object_id:
                if cache is not None:
                    cache.setdefault('ir.attachment', {})
                    ids = cache['ir.attachment'].keys()
                    if object_id not in ids:
                        ids.append(object_id)
                    elif 'data' in cache['ir.attachment'][object_id]:
                        res = cache['ir.attachment'][object_id]['data']
                        if res == DAV_NotFound:
                            raise DAV_NotFound
                        return res
                else:
                    ids = [object_id]
                attachments = attachment_obj.browse(ids)

                res = DAV_NotFound
                for attachment in attachments:
                    data = DAV_NotFound
                    try:
                        if attachment.data is not None:
                            data = str(attachment.data)
                    except Exception:
                        pass
                    if attachment.id == object_id:
                        res = data
                    if cache is not None:
                        cache['ir.attachment'].setdefault(attachment.id, {})
                        cache['ir.attachment'][attachment.id]['data'] = data
                if res == DAV_NotFound:
                    raise DAV_NotFound
                return res

            if object_name == 'ir.action.report' and object_id:
                report_id = int(uri.rsplit('/', 1)[-1].rsplit('-',
                    1)[-1].rsplit('.', 1)[0])
                report = report_obj.browse(report_id)
                if report.report_name:
                    report_obj = pool.get(report.report_name,
                            type='report')
                    val = report_obj.execute([object_id],
                            {'id': object_id, 'ids': [object_id]})
                    return val[1]
        raise DAV_NotFound

    def put(self, uri, data, content_type, cache=None):
        from pywebdav.lib.errors import DAV_Forbidden
        from pywebdav.lib.utils import get_uriparentpath, get_urifilename
        object_name, object_id = self._uri2object(get_uriparentpath(uri),
                cache=cache)
        if not object_name \
                or object_name in ('ir.attachment') \
                or not object_id:
            raise DAV_Forbidden
        pool = Pool()
        attachment_obj = pool.get('ir.attachment')
        object_name2, object_id2 = self._uri2object(uri, cache=cache)
        if not object_id2:
            name = get_urifilename(uri)
            try:
                attachment_obj.create({
                    'name': name,
                    'data': data,
                    'name': name,
                    'resource': '%s,%s' % (object_name, object_id),
                    })
            except Exception:
                raise DAV_Forbidden
        else:
            try:
                attachment_obj.write(object_id2, {
                    'data': data,
                    })
            except Exception:
                raise DAV_Forbidden
        return

    def mkcol(self, uri, cache=None):
        from pywebdav.lib.errors import DAV_Forbidden
        from pywebdav.lib.utils import get_uriparentpath, get_urifilename
        if uri[-1:] == '/':
            uri = uri[:-1]
        object_name, object_id = self._uri2object(get_uriparentpath(uri),
                cache=cache)
        if object_name != 'webdav.collection':
            raise DAV_Forbidden
        name = get_urifilename(uri)
        try:
            self.create({
                'name': name,
                'parent': object_id,
                })
        except Exception:
            raise DAV_Forbidden
        return 201

    def rmcol(self, uri, cache=None):
        from pywebdav.lib.errors import DAV_Forbidden
        object_name, object_id = self._uri2object(uri, cache=cache)
        if object_name != 'webdav.collection' \
                or not object_id:
            raise DAV_Forbidden
        try:
            self.delete(object_id)
        except Exception:
            raise DAV_Forbidden
        return 200

    def rm(self, uri, cache=None):
        from pywebdav.lib.errors import DAV_Forbidden
        object_name, object_id = self._uri2object(uri, cache=cache)
        if not object_name:
            raise DAV_Forbidden
        if object_name != 'ir.attachment' \
                or not object_id:
            raise DAV_Forbidden
        pool = Pool()
        model_obj = pool.get(object_name)
        try:
            model_obj.delete(object_id)
        except Exception:
            raise DAV_Forbidden
        return 200

    def exists(self, uri, cache=None):
        object_name, object_id = self._uri2object(uri, cache=cache)
        if object_name and object_id:
            return 1
        return None

    def current_user_privilege_set(self, uri, cache=None):
        return ['create', 'read', 'write', 'delete']

Collection()


class Share(ModelSQL, ModelView):
    "Share"
    _name = 'webdav.share'
    _description = __doc__
    _rec_name = 'key'

    path = fields.Char('Path', required=True, select=True)
    key = fields.Char('Key', required=True, select=True,
        states={
            'readonly': True,
            })
    user = fields.Many2One('res.user', 'User', required=True)
    expiration_date = fields.Date('Expiration Date', required=True)
    note = fields.Text('Note')
    url = fields.Function(fields.Char('URL'), 'get_url')

    def default_key(self):
        return uuid.uuid4().hex

    def default_user(self):
        return Transaction().user

    def default_expiration_date(self):
        return datetime.date.today() + relativedelta(months=1)

    def get_url(self, ids, name):
        urls = {}
        webdav_url = get_webdav_url()
        for share in self.browse(ids):
            urls[share.id] = urlparse.urljoin(webdav_url,
                urlparse.urlunsplit((None, None, urllib.quote(share.path),
                        urllib.urlencode([('key', share.key)]), None)))
        return urls

    def match(self, share, command, path):
        "Test if share match with command and path"
        today = datetime.date.today()
        return (path.startswith(share.path)
            and share.expiration_date > today
            and command == 'GET')

    def get_login(self, key, command, path):
        """Validate the key for the command and path
        Return the user id if succeed or None
        """
        share_ids = self.search([
                ('key', '=', key),
                ])
        if not share_ids:
            return None
        for share in self.browse(share_ids):
            if self.match(share, command, path):
                return share.user.id
        return None

Share()


class Attachment(ModelSQL, ModelView):
    _name = 'ir.attachment'

    path = fields.Function(fields.Char('Path'), 'get_path')
    url = fields.Function(fields.Char('URL'), 'get_url')
    shares = fields.Function(fields.One2Many('webdav.share', None, 'Shares',
            domain=[
                ('path', '=', Eval('path')),
                ],
            depends=['path']), 'get_shares', 'set_shares')

    def __init__(self):
        super(Attachment, self).__init__()
        self._constraints += [
            ('check_collection', 'collection_attachment_name'),
        ]
        self._error_messages.update({
            'collection_attachment_name': ('You can not create an attachment\n'
                    'in a collection with the name\n'
                    'of an existing child collection!'),
        })

    def check_collection(self, ids):
        pool = Pool()
        collection_obj = pool.get('webdav.collection')
        for attachment in self.browse(ids):
            if attachment.resource:
                model_name, record_id = attachment.resource.split(',')
                if model_name == 'webdav.collection':
                    collection = collection_obj.browse(int(record_id))
                    for child in collection.childs:
                        if child.name == attachment.name:
                            return False
        return True

    def get_path(self, ids, name):
        pool = Pool()
        collection_obj = pool.get('webdav.collection')
        paths = dict((x, None) for x in ids)

        attachments = self.browse(ids)
        resources = {}
        resource2attachments = {}
        for attachment in attachments:
            if not attachment.resource:
                paths[attachment.id] = None
            model_name, record_id = attachment.resource.split(',')
            record_id = int(record_id)
            resources.setdefault(model_name, set()).add(record_id)
            resource2attachments.setdefault((model_name, record_id),
                []).append(attachment)
        collection_ids = collection_obj.search([
                ('model.model', 'in', resources.keys()),
                ])
        for collection in collection_obj.browse(collection_ids):
            model_name = collection.model.model
            model_obj = pool.get(model_name)
            ids = list(resources[model_name])
            domain = safe_eval(collection.domain or '[]')
            domain = [domain, ('id', 'in', ids)]
            record_ids = model_obj.search(domain)
            for record in model_obj.browse(record_ids):
                for attachment in resource2attachments[
                        (model_name, record.id)]:
                    paths[attachment.id] = '/'.join((collection.rec_name,
                            record.rec_name + '-' + str(record.id),
                            attachment.name))
        if 'webdav.collection' in resources:
            collection_ids = list(resources['webdav.collection'])
            for collection in collection_obj.browse(collection_ids):
                for attachment in resource2attachments[
                        ('webdav.collection', collection.id)]:
                    paths[attachment.id] = '/'.join((collection.rec_name,
                            attachment.name))
        return paths

    def get_url(self, ids, name):
        webdav_url = get_webdav_url()
        urls = {}
        for attachment in self.browse(ids):
            if attachment.path:
                urls[attachment.id] = urlparse.urljoin(webdav_url,
                    urllib.quote(attachment.path))
            else:
                urls[attachment.id] = None
        return urls

    def get_shares(self, ids, name):
        share_obj = Pool().get('webdav.share')
        shares = dict((x, []) for x in ids)
        attachements = self.browse(ids)
        path2attachement = dict((a.path, a) for a in attachements)
        share_ids = share_obj.search([
                ('path', 'in', path2attachement.keys()),
                ])
        for share in share_obj.browse(share_ids):
            attachment = path2attachement[share.path]
            shares[attachment.id].append(share.id)
        return shares

    def set_shares(self, ids, name, value):
        share_obj = Pool().get('webdav.share')

        if not value:
            return

        attachments = self.browse(ids)
        for action in value:
            if action[0] == 'create':
                for attachment in attachments:
                    action[1]['path'] = attachment.path
                    share_obj.create(action[1])
            elif action[0] == 'write':
                share_obj.write(action[1], action[2])
            elif action[0] == 'delete':
                share_obj.delete(action[1])
            elif action[0] == 'delete_all':
                paths = [a.path for a in attachments]
                share_ids = share_obj.search([
                        ('path', 'in', paths),
                        ])
                share_obj.delete(share_ids)
            elif action[0] == 'unlink':
                pass
            elif action[0] == 'add':
                pass
            elif action[0] == 'unlink_all':
                pass
            elif action[0] == 'set':
                pass
            else:
                raise Exception('Bad arguments')

Attachment()
