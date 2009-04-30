#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"WebDAV"
import os
import base64
import time
from trytond.osv import fields, OSV
from trytond.version import PACKAGE, VERSION, WEBSITE
from trytond import pooler
from trytond.pooler import get_pool_report
from trytond.report import Report


class Collection(OSV):
    "Collection"
    _name = "webdav.collection"
    _description = __doc__
    name = fields.Char('Name', size=128, required=True, select=1)
    parent = fields.Many2One('webdav.collection', 'Parent',
       ondelete='restrict', domain=[('model', '=', False)])
    childs = fields.One2Many('webdav.collection', 'parent', 'Childs')
    model = fields.Many2One('ir.model', 'Model')
    domain = fields.Char('Domain', size=250)

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
                    'with the same name of an existing file\n'
                    'inside the same collection!',
        })
        self.ext2mime = {
            '.png': 'image/png',
            '.odt': 'application/vnd.oasis.opendocument.text',
            '.pdf': 'application/pdf',
        }

    def default_domain(self, cursor, user, context=None):
        return '[]'

    def check_attachment(self, cursor, user, ids):
        attachment_obj = self.pool.get('ir.attachment')
        for collection in self.browse(cursor, user, ids):
            if collection.parent:
                attachment_ids = attachment_obj.search(cursor, user, [
                    ('res_model', '=', self._name),
                    ('res_id', '=', collection.parent.id),
                    ])
                for attachment in attachment_obj.browse(cursor, user,
                        attachment_ids):
                    if attachment.name == collection.name:
                        return False
        return True

    def _uri2object(self, cursor, user, uri, object_name=_name, object_id=False,
            context=None):
        attachment_obj = self.pool.get('ir.attachment')
        report_obj = self.pool.get('ir.action.report')
        if not uri:
            return self._name, False
        name, uri = (uri.split('/', 1) + [None])[0:2]
        if object_name == self._name:
            collection_ids = self.search(cursor, user, [
                ('name', '=', name),
                ('parent', '=', object_id),
                ], limit=1, context=context)
            if collection_ids:
                object_id = collection_ids[0]
                collection = self.browse(cursor, user, object_id,
                        context=context)
                if collection.model and uri:
                    object_name = collection.model.model
            else:
                if uri:
                    return None, 0
                attachment_ids = attachment_obj.search(cursor, user, [
                    ('res_model', '=', object_name),
                    ('res_id', '=', object_id),
                    ('name', '=', name),
                    ], limit=1, context=context)
                if attachment_ids:
                    object_name = 'ir.attachment'
                    object_id = attachment_ids[0]
                else:
                    object_name = None
                    object_id = False
        else:
            splitted_name = name.rsplit('-', 1)
            if len(splitted_name) != 2:
                return object_name, 0
            object_id = int(splitted_name[1].strip())
            if uri:
                if '/' in uri:
                    return None, 0
                report_ids = report_obj.search(cursor, user, [
                    ('model', '=', object_name),
                    ], context=context)
                reports = report_obj.browse(cursor, user, report_ids,
                    context=context)
                for report in reports:
                    report_name = report.name + '-' + str(report.id) \
                            + '.' + report.output_format.format
                    if uri == report_name:
                        return 'ir.action.report', object_id
                name = uri
                attachment_ids = attachment_obj.search(cursor, user, [
                    ('res_model', '=', object_name),
                    ('res_id', '=', object_id),
                    ('name', '=', name),
                    ], limit=1, context=context)
                if attachment_ids:
                    object_name = 'ir.attachment'
                    object_id = attachment_ids[0]
                else:
                    object_name = None
                    object_id = False
                return object_name, object_id
        if uri:
            return self._uri2object(cursor, user, uri, object_name,
                    object_id, context)
        return object_name, object_id

    def get_childs(self, cursor, user, uri, context=None):
        report_obj = self.pool.get('ir.action.report')
        res = []
        if not uri:
            collection_ids = self.search(cursor, user, [
                ('parent', '=', False),
                ], context=context)
            for collection in self.browse(cursor, user, collection_ids,
                    context=context):
                if '/' in collection.name:
                    continue
                res.append(collection.name)
            return res
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name == self._name and object_id:
            collection = self.browse(cursor, user, object_id, context=context)
            if collection.model:
                model_obj = self.pool.get(collection.model.model)
                if not model_obj:
                    return res
                model_ids = model_obj.search(cursor, user,
                        eval(collection.domain or "[]"), context=context)
                for child_id, child_name in model_obj.name_get(cursor, user,
                        model_ids, context=context):
                    if '/' in child_name:
                        continue
                    res.append(child_name + '-' + str(child_id))
                return res
            else:
                for child in collection.childs:
                    if '/' in child.name:
                        continue
                    res.append(child.name)
        if object_name not in ('ir.attachment', 'ir.action.report'):
            report_ids = report_obj.search(cursor, user, [
                ('model', '=', object_name),
                ], context=context)
            reports = report_obj.browse(cursor, user, report_ids,
                context=context)
            for report in reports:
                report_name = report.name + '-' + str(report.id) \
                        + '.' + report.output_format.format
                if '/' in report_name:
                    continue
                res.append(report_name)

            attachment_obj = self.pool.get('ir.attachment')
            attachment_ids = attachment_obj.search(cursor, user, [
                ('res_model', '=', object_name),
                ('res_id', '=', object_id),
                ], context=context)
            for attachment in attachment_obj.browse(cursor, user, attachment_ids,
                    context=context):
                if attachment.name and not attachment.link:
                    if '/' in attachment.name:
                        continue
                    res.append(attachment.name)
        return res

    def get_resourcetype(self, cursor, user, uri, context=None):
        from DAV.constants import COLLECTION, OBJECT
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name in ('ir.attachment', 'ir.action.report'):
            return OBJECT
        return COLLECTION

    def get_contentlength(self, cursor, user, uri, context=None):
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name == 'ir.attachment':
            attachment_obj = self.pool.get('ir.attachment')
            attachment = attachment_obj.browse(cursor, user, object_id,
                    context=context)
            try:
                if attachment.datas_size:
                    return str(attachment.datas_size)
            except:
                return '0'
        return '0'

    def get_contenttype(self, cursor, user, uri, context=None):
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name in ('ir.attachment', 'ir.action.report'):
            ext = os.path.splitext(uri)[1]
            if not ext:
                return "application/octet-stream"
            return self.ext2mime.get(ext, 'application/octet-stream')
        return "application/octet-stream"

    def get_creationdate(self, cursor, user, uri, context=None):
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name:
            model_obj = self.pool.get(object_name)
            if object_id:
                cursor.execute('SELECT EXTRACT(epoch FROM create_date) ' \
                        'FROM "' + model_obj._table +'" ' \
                        'WHERE id = %s', (object_id,))
                if cursor.rowcount:
                    return cursor.fetchone()[0]
        return time.time()

    def get_lastmodified(self, cursor, user, uri, context=None):
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name:
            model_obj = self.pool.get(object_name)
            if object_id:
                cursor.execute('SELECT ' \
                            'EXTRACT(epoch FROM COALESCE(write_date, create_date)) ' \
                        'FROM "' + model_obj._table +'" ' \
                        'WHERE id = %s', (object_id,))
                if cursor.rowcount:
                    return cursor.fetchone()[0]
        return time.time()

    def get_data(self, cursor, user, uri, context=None):
        from DAV.errors import DAV_NotFound
        if uri:
            object_name, object_id = self._uri2object(cursor, user, uri,
                    context=context)
            if object_name == 'ir.attachment' and object_id:
                attachment_obj = self.pool.get('ir.attachment')
                attachment = attachment_obj.browse(cursor, user, object_id,
                        context=context)
                try:
                    if attachment.datas:
                        return base64.decodestring(attachment.datas)
                except:
                    raise DAV_NotFound
            if object_name == 'ir.action.report' and object_id:
                report_obj = self.pool.get('ir.action.report')
                report_id = int(uri.rsplit('/', 1)[-1].rsplit('-',
                    1)[-1].rsplit('.', 1)[0])
                report = report_obj.browse(cursor, user, report_id,
                        context=context)
                if report.report_name:
                    reportsvc = get_pool_report(cursor.dbname)
                    report_svc = reportsvc.get(report.report_name)
                    if not report_svc:
                        report_svc = Report.create_instance(reportsvc,
                                'report', pooler.get_pool(cursor.dbname))
                        report_svc._name = report.report_name
                    val = report_svc.execute(cursor, user, [object_id],
                            {'id': object_id, 'ids': [object_id]},
                            context=context)
                    return base64.decodestring(val[1])
        raise DAV_NotFound

    def put(self, cursor, user, uri, data, content_type, context=None):
        from DAV.errors import DAV_Forbidden
        from DAV.utils import get_uriparentpath, get_urifilename
        object_name, object_id = self._uri2object(cursor, user,
                get_uriparentpath(uri), context=context)
        if not object_name \
                or object_name in ('ir.attachment') \
                or not object_id:
            raise DAV_Forbidden
        attachment_obj = self.pool.get('ir.attachment')
        object_name2, object_id2 = self._uri2object(cursor, user, uri,
                context=context)
        if not object_id2:
            name = get_urifilename(uri)
            try:
                attachment_obj.create(cursor, user, {
                    'name': name,
                    'datas': base64.encodestring(data),
                    'name': name,
                    'res_model': object_name,
                    'res_id': object_id,
                    }, context=context)
            except:
                raise DAV_Forbidden
        else:
            try:
                attachment_obj.write(cursor, user, object_id2, {
                    'datas': base64.encodestring(data),
                    }, context=context)
            except:
                raise DAV_Forbidden
        return 201

    def mkcol(self, cursor, user, uri, context=None):
        from DAV.errors import DAV_Forbidden
        from DAV.utils import get_uriparentpath, get_urifilename
        if uri[-1:] == '/':
            uri = uri[:-1]
        object_name, object_id = self._uri2object(cursor, user,
                get_uriparentpath(uri), context=context)
        if object_name != 'webdav.collection':
            raise DAV_Forbidden
        name = get_urifilename(uri)
        try:
            self.create(cursor, user, {
                'name': name,
                'parent': object_id,
                }, context=context)
        except:
            raise DAV_Forbidden
        return 201

    def rmcol(self, cursor, user, uri, context=None):
        from DAV.errors import DAV_Forbidden
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name != 'webdav.collection' \
                or not object_id:
            raise DAV_Forbidden
        try:
            self.delete(cursor, user, object_id, context=context)
        except:
            raise DAV_Forbidden
        return 200

    def rm(self, cursor, user, uri, context=None):
        from DAV.errors import DAV_Forbidden
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if not object_name:
            raise DAV_Forbidden
        if object_name != 'ir.attachment' \
                or not object_id:
            raise DAV_Forbidden
        model_obj = self.pool.get(object_name)
        try:
            model_obj.delete(cursor, user, object_id, context=context)
        except:
            raise DAV_Forbidden
        return 200

    def exists(self, cursor, user, uri, context=None):
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name and object_id:
            return 1
        return None

Collection()


class Attachment(OSV):
    _name = 'ir.attachment'

    def __init__(self):
        super(Attachment, self).__init__()
        self._constraints += [
            ('check_collection', 'collection_attachment_name'),
        ]
        self._error_messages.update({
            'collection_attachment_name': 'You can not create a attachment\n' \
                    'on a collection that have the same name\n' \
                    'than a child collection!',
        })

    def check_collection(self, cursor, user, ids):
        collection_obj = self.pool.get('webdav.collection')
        for attachment in self.browse(cursor, user, ids):
            if attachment.res_model == 'webdav.collection':
                collection = collection_obj.browse(cursor, user,
                        attachment.res_id)
                for child in collection.childs:
                    if child.name == attachment.name:
                        return False
        return True

Attachment()
