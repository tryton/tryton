# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import time
import urllib
import urlparse
import socket
import encodings
import uuid
import datetime
from ast import literal_eval

from dateutil.relativedelta import relativedelta
from sql.functions import Extract
from sql.conditionals import Coalesce

from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import reduce_ids
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.config import config
from trytond.pyson import Eval
from trytond.tools import grouped_slice

__all__ = [
    'Collection', 'Share', 'Attachment',
    ]


def get_webdav_url():
    if config.get('ssl', 'privatekey'):
        protocol = 'https'
    else:
        protocol = 'http'
    hostname = (config.get('webdav', 'hostname')
        or unicode(socket.getfqdn(), 'utf8'))
    hostname = '.'.join(encodings.idna.ToASCII(part) for part in
        hostname.split('.'))
    return urlparse.urlunsplit((protocol, hostname,
        urllib.quote(
            Transaction().cursor.database_name.encode('utf-8') + '/'),
            None, None))


class Collection(ModelSQL, ModelView):
    "Collection"
    __name__ = "webdav.collection"
    name = fields.Char('Name', required=True, select=True)
    parent = fields.Many2One('webdav.collection', 'Parent',
       ondelete='RESTRICT', domain=[('model', '=', None)])
    childs = fields.One2Many('webdav.collection', 'parent', 'Children')
    model = fields.Many2One('ir.model', 'Model')
    domain = fields.Char('Domain')
    complete_name = fields.Function(fields.Char('Complete Name'),
        'get_rec_name')

    @classmethod
    def __setup__(cls):
        super(Collection, cls).__setup__()
        cls._sql_constraints += [
            ('name_parent_uniq', 'UNIQUE (name, parent)',
                'The collection name must be unique inside a collection!'),
        ]
        cls._error_messages.update({
                'collection_file_name': ('You can not create a collection '
                    'named "%(parent)s" in collection "%(child)s" because '
                    'there is already a file with that name.'),
                })
        cls.ext2mime = {
            '.png': 'image/png',
            '.odt': 'application/vnd.oasis.opendocument.text',
            '.pdf': 'application/pdf',
        }

    @classmethod
    def order_complet_name(cls, tables):
        return cls.name.convert_order('name', tables, cls)

    @staticmethod
    def default_domain():
        return '[]'

    def get_rec_name(self, name):
        if self.parent:
            return self.parent.rec_name + '/' + self.name
        else:
            return self.name

    @classmethod
    def validate(cls, collections):
        super(Collection, cls).validate(collections)
        cls.check_recursion(collections, rec_name='name')
        cls.check_attachment(collections)

    @classmethod
    def check_attachment(cls, collections):
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        for collection in collections:
            if collection.parent:
                attachments = Attachment.search([
                    ('resource', '=', '%s,%s' %
                        (cls.__name__, collection.parent.id)),
                    ])
                for attachment in attachments:
                    if attachment.name == collection.name:
                        cls.raise_user_error('collection_file_name', {
                                'parent': collection.parent.rec_name,
                                'child': collection.rec_name,
                                })

    @classmethod
    def _uri2object(cls, uri, object_name=__name__, object_id=None,
            cache=None):
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        Report = pool.get('ir.action.report')
        cache_uri = uri

        if cache is not None:
            cache.setdefault('_uri2object', {})
            if cache_uri in cache['_uri2object']:
                return cache['_uri2object'][cache_uri]

        if not uri:
            if cache is not None:
                cache['_uri2object'][cache_uri] = (cls.__name__, None)
            return cls.__name__, None
        name, uri = (uri.split('/', 1) + [None])[0:2]
        if object_name == cls.__name__:
            collection_ids = None
            if cache is not None:
                cache.setdefault('_parent2collection_ids', {})
                if object_id in cache['_parent2collection_ids']:
                    collection_ids = cache['_parent2collection_ids'][
                        object_id].get(name, [])
            if collection_ids is None:
                collections = cls.search([
                    ('parent', '=', object_id),
                    ])
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
                                cls.__name__
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
                    collection = cls(object_id)
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
                    attachments = Attachment.search([
                        ('resource', '=', '%s,%s' % (object_name, object_id)),
                        ])
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
                reports = Report.search([
                    ('model', '=', object_name),
                    ])
                for report in reports:
                    report_name = (report.name + '-' + str(report.id)
                        + '.' + report.extension)
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
                    attachments = Attachment.search([
                        ('resource', '=', '%s,%s' % (object_name, object_id)),
                        ])
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
            res = cls._uri2object(uri, object_name, object_id, cache=cache)
            if cache is not None:
                cache['_uri2object'][cache_uri] = res
            return res
        if cache is not None:
            cache['_uri2object'][cache_uri] = (object_name, object_id)
        return object_name, object_id

    @classmethod
    def get_childs(cls, uri, filter=None, cache=None):
        pool = Pool()
        Report = pool.get('ir.action.report')
        res = []
        if filter:
            return []
        if not uri:
            collections = cls.search([
                ('parent', '=', None),
                ])
            for collection in collections:
                if '/' in collection.name:
                    continue
                res.append(collection.name)
                if cache is not None:
                    cache.setdefault(cls.__name__, {})
                    cache[cls.__name__][collection.id] = {}
            return res
        object_name, object_id = cls._uri2object(uri, cache=cache)
        if object_name == cls.__name__ and object_id:
            collection = cls(object_id)
            if collection.model:
                Model = pool.get(collection.model.model)
                if not Model:
                    return res
                models = Model.search(
                    literal_eval(collection.domain))
                for child in models:
                    if '/' in child.rec_name:
                        continue
                    res.append(child.rec_name + '-' + str(child.id))
                    if cache is not None:
                        cache.setdefault(Model.__name__, {})
                        cache[Model.__name__][child.id] = {}
                return res
            else:
                for child in collection.childs:
                    if '/' in child.name:
                        continue
                    res.append(child.name)
                    if cache is not None:
                        cache.setdefault(cls.__name__, {})
                        cache[cls.__name__][child.id] = {}
        if object_name not in ('ir.attachment', 'ir.action.report'):
            reports = Report.search([
                ('model', '=', object_name),
                ])
            for report in reports:
                report_name = (report.name + '-' + str(report.id)
                    + '.' + report.extension)
                if '/' in report_name:
                    continue
                res.append(report_name)
                if cache is not None:
                    cache.setdefault(Report.__name__, {})
                    cache[Report.__name__][report.id] = {}

            Attachment = pool.get('ir.attachment')
            attachments = Attachment.search([
                    ('resource', '=', '%s,%s' % (object_name, object_id)),
                    ])
            for attachment in attachments:
                if attachment.name and not attachment.link:
                    if '/' in attachment.name:
                        continue
                    res.append(attachment.name)
                    if cache is not None:
                        cache.setdefault(Attachment.__name__, {})
                        cache[Attachment.__name__][attachment.id] = {}
        return res

    @classmethod
    def get_resourcetype(cls, uri, cache=None):
        from pywebdav.lib.constants import COLLECTION, OBJECT
        object_name, object_id = cls._uri2object(uri, cache=cache)
        if object_name in ('ir.attachment', 'ir.action.report'):
            return OBJECT
        return COLLECTION

    @classmethod
    def get_displayname(cls, uri, cache=None):
        object_name, object_id = cls._uri2object(uri, cache=cache)
        Model = Pool().get(object_name)
        return Model(object_id).rec_name

    @classmethod
    def get_contentlength(cls, uri, cache=None):
        pool = Pool()
        Attachment = pool.get('ir.attachment')

        object_name, object_id = cls._uri2object(uri, cache=cache)
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

            attachments = Attachment.browse(ids)

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

    @classmethod
    def get_contenttype(cls, uri, cache=None):
        object_name, object_id = cls._uri2object(uri, cache=cache)
        if object_name in ('ir.attachment', 'ir.action.report'):
            ext = os.path.splitext(uri)[1]
            if not ext:
                return "application/octet-stream"
            return cls.ext2mime.get(ext, 'application/octet-stream')
        return "application/octet-stream"

    @classmethod
    def get_creationdate(cls, uri, cache=None):
        pool = Pool()
        object_name, object_id = cls._uri2object(uri, cache=cache)
        if object_name == 'ir.attachment':
            Model = pool.get(object_name)
            if object_id:
                if cache is not None:
                    cache.setdefault(Model.__name__, {})
                    ids = cache[Model.__name__].keys()
                    if object_id not in ids:
                        ids.append(object_id)
                    elif 'creationdate' in cache[Model.__name__][object_id]:
                        return cache[Model.__name__][object_id][
                            'creationdate']
                else:
                    ids = [object_id]
                res = None
                cursor = Transaction().cursor
                table = Model.__table__()
                for sub_ids in grouped_slice(ids):
                    red_sql = reduce_ids(table.id, sub_ids)
                    cursor.execute(*table.select(table.id,
                            Extract('EPOCH', table.create_date),
                            where=red_sql))
                    for object_id2, date in cursor.fetchall():
                        if object_id2 == object_id:
                            res = date
                        if cache is not None:
                            cache[Model.__name__].setdefault(object_id2, {})
                            cache[Model.__name__][object_id2][
                                'creationdate'] = date
                if res is not None:
                    return res
        return time.time()

    @classmethod
    def get_lastmodified(cls, uri, cache=None):
        pool = Pool()
        object_name, object_id = cls._uri2object(uri, cache=cache)
        if object_name == 'ir.attachment':
            Model = pool.get(object_name)
            if object_id:
                if cache is not None:
                    cache.setdefault(Model.__name__, {})
                    ids = cache[Model.__name__].keys()
                    if object_id not in ids:
                        ids.append(object_id)
                    elif 'lastmodified' in cache[Model.__name__][object_id]:
                        return cache[Model.__name__][object_id][
                            'lastmodified']
                else:
                    ids = [object_id]
                res = None
                cursor = Transaction().cursor
                table = Model.__table__()
                for sub_ids in grouped_slice(ids):
                    red_sql = reduce_ids(table.id, sub_ids)
                    cursor.execute(*table.select(table.id,
                            Extract('EPOCH',
                                Coalesce(table.write_date, table.create_date)),
                            where=red_sql))
                    for object_id2, date in cursor.fetchall():
                        if object_id2 == object_id:
                            res = date
                        if cache is not None:
                            cache[Model.__name__].setdefault(object_id2, {})
                            cache[Model.__name__][object_id2][
                                'lastmodified'] = date
                if res is not None:
                    return res
        return time.time()

    @classmethod
    def get_data(cls, uri, cache=None):
        from pywebdav.lib.errors import DAV_NotFound
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        Report = pool.get('ir.action.report')

        if uri:
            object_name, object_id = cls._uri2object(uri, cache=cache)

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
                attachments = Attachment.browse(ids)

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
                report = Report(report_id)
                if report.report_name:
                    Report = pool.get(report.report_name,
                            type='report')
                    val = Report.execute([object_id],
                        {'id': object_id, 'ids': [object_id]})
                    return val[1]
        raise DAV_NotFound

    @classmethod
    def put(cls, uri, data, content_type, cache=None):
        from pywebdav.lib.errors import DAV_Forbidden
        from pywebdav.lib.utils import get_uriparentpath, get_urifilename
        object_name, object_id = cls._uri2object(get_uriparentpath(uri),
                cache=cache)
        if not object_name \
                or object_name == 'ir.attachment' \
                or not object_id:
            raise DAV_Forbidden
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        object_name2, object_id2 = cls._uri2object(uri, cache=cache)
        if not object_id2:
            name = get_urifilename(uri)
            try:
                Attachment.create([{
                            'name': name,
                            'data': data,
                            'resource': '%s,%s' % (object_name, object_id),
                            }])
            except Exception:
                raise DAV_Forbidden
        else:
            try:
                Attachment.write(object_id2, {
                    'data': data,
                    })
            except Exception:
                raise DAV_Forbidden
        return

    @classmethod
    def mkcol(cls, uri, cache=None):
        from pywebdav.lib.errors import DAV_Forbidden
        from pywebdav.lib.utils import get_uriparentpath, get_urifilename
        if uri[-1:] == '/':
            uri = uri[:-1]
        object_name, object_id = cls._uri2object(get_uriparentpath(uri),
                cache=cache)
        if object_name != 'webdav.collection':
            raise DAV_Forbidden
        name = get_urifilename(uri)
        try:
            cls.create([{
                        'name': name,
                        'parent': object_id,
                        }])
        except Exception:
            raise DAV_Forbidden
        return 201

    @classmethod
    def rmcol(cls, uri, cache=None):
        from pywebdav.lib.errors import DAV_Forbidden
        object_name, object_id = cls._uri2object(uri, cache=cache)
        if object_name != 'webdav.collection' \
                or not object_id:
            raise DAV_Forbidden
        try:
            cls.delete([cls(object_id)])
        except Exception:
            raise DAV_Forbidden
        return 200

    @classmethod
    def rm(cls, uri, cache=None):
        from pywebdav.lib.errors import DAV_Forbidden
        object_name, object_id = cls._uri2object(uri, cache=cache)
        if not object_name:
            raise DAV_Forbidden
        if object_name != 'ir.attachment' \
                or not object_id:
            raise DAV_Forbidden
        pool = Pool()
        Model = pool.get(object_name)
        try:
            Model.delete([Model(object_id)])
        except Exception:
            raise DAV_Forbidden
        return 200

    @classmethod
    def exists(cls, uri, cache=None):
        object_name, object_id = cls._uri2object(uri, cache=cache)
        if object_name and object_id:
            return 1
        return None

    @staticmethod
    def current_user_privilege_set(uri, cache=None):
        return ['create', 'read', 'write', 'delete']


class Share(ModelSQL, ModelView):
    "Share"
    __name__ = 'webdav.share'
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

    @staticmethod
    def default_key():
        return uuid.uuid4().hex

    @staticmethod
    def default_user():
        return Transaction().user

    @staticmethod
    def default_expiration_date():
        return datetime.date.today() + relativedelta(months=1)

    def get_url(self, name):
        return urlparse.urljoin(get_webdav_url(),
            urlparse.urlunsplit((None, None,
                    urllib.quote(self.path.encode('utf-8')),
                    urllib.urlencode([('key', self.key)]), None)))

    @staticmethod
    def match(share, command, path):
        "Test if share match with command and path"
        today = datetime.date.today()
        return (path.startswith(share.path)
            and share.expiration_date > today
            and command == 'GET')

    @classmethod
    def get_login(cls, key, command, path):
        """Validate the key for the command and path
        Return the user id if succeed or None
        """
        shares = cls.search([
                ('key', '=', key),
                ])
        if not shares:
            return None
        for share in shares:
            if cls.match(share, command, path):
                return share.user.id
        return None


class Attachment(ModelSQL, ModelView):
    __name__ = 'ir.attachment'

    path = fields.Function(fields.Char('Path'), 'get_path')
    url = fields.Function(fields.Char('URL'), 'get_url')
    shares = fields.Function(fields.One2Many('webdav.share', None, 'Shares',
            domain=[
                ('path', '=', Eval('path')),
                ],
            depends=['path']), 'get_shares', 'set_shares')

    @classmethod
    def __setup__(cls):
        super(Attachment, cls).__setup__()
        cls._error_messages.update({
                'collection_attachment_name': ('You can not create an '
                    'attachment named "%(attachment)s" in collection '
                    '"%(collection)s" because there is already a collection '
                    'with that name.')
                })

    @classmethod
    def validate(cls, attachments):
        super(Attachment, cls).validate(attachments)
        cls.check_collection(attachments)

    @classmethod
    def check_collection(cls, attachments):
        pool = Pool()
        Collection = pool.get('webdav.collection')
        for attachment in attachments:
            if attachment.resource:
                model_name = attachment.resource.__name__
                record_id = attachment.resource.id
                if model_name == 'webdav.collection':
                    collection = Collection(int(record_id))
                    for child in collection.childs:
                        if child.name == attachment.name:
                            cls.raise_user_error(
                                'collection_attachment_name', {
                                    'attachment': attachment.rec_name,
                                    'collection': collection.rec_name,
                                    })

    @classmethod
    def get_path(cls, attachments, name):
        pool = Pool()
        Collection = pool.get('webdav.collection')
        paths = dict((a.id, None) for a in attachments)

        resources = {}
        resource2attachments = {}
        for attachment in attachments:
            if not attachment.resource:
                paths[attachment.id] = None
                continue
            model_name = attachment.resource.__name__
            record_id = attachment.resource.id
            resources.setdefault(model_name, set()).add(record_id)
            resource2attachments.setdefault((model_name, record_id),
                []).append(attachment)
        collections = Collection.search([
                ('model.model', 'in', resources.keys()),
                ])
        for collection in collections:
            model_name = collection.model.model
            Model = pool.get(model_name)
            ids = list(resources[model_name])
            domain = literal_eval(collection.domain)
            domain = [domain, ('id', 'in', ids)]
            records = Model.search(domain)
            for record in records:
                for attachment in resource2attachments[
                        (model_name, record.id)]:
                    paths[attachment.id] = '/'.join((collection.rec_name,
                            record.rec_name + '-' + str(record.id),
                            attachment.name))
        if 'webdav.collection' in resources:
            collection_ids = list(resources['webdav.collection'])
            for collection in Collection.browse(collection_ids):
                for attachment in resource2attachments[
                        ('webdav.collection', collection.id)]:
                    paths[attachment.id] = '/'.join((collection.rec_name,
                            attachment.name))
        return paths

    def get_url(self, name):
        if self.path:
            return urlparse.urljoin(get_webdav_url(),
                urllib.quote(self.path.encode('utf-8')))

    @classmethod
    def get_shares(cls, attachments, name):
        Share = Pool().get('webdav.share')
        result = dict((a.id, []) for a in attachments)
        path2attachement = dict((a.path, a) for a in attachments)
        shares = Share.search([
                ('path', 'in', path2attachement.keys()),
                ])
        for share in shares:
            attachment = path2attachement[share.path]
            result[attachment.id].append(share.id)
        return result

    @classmethod
    def set_shares(cls, attachments, name, values):
        Share = Pool().get('webdav.share')

        if not values:
            return

        def create(vlist):
            to_create = []
            for attachment in attachments:
                for values in vlist:
                    values = values.copy()
                    values['path'] = attachment.path
                    to_create.append(values)
            if to_create:
                Share.create(to_create)

        def write(ids, values):
            Share.write(Share.browse(ids), values)

        def delete(share_ids):
            Share.delete(Share.browse(share_ids))

        actions = {
            'create': create,
            'write': write,
            'delete': delete,
            }
        for value in values:
            action = value[0]
            args = value[1:]
            actions[action](*args)
