# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import base64
import csv
import datetime
import decimal
import math
import random
import time
import warnings
from collections import defaultdict
from decimal import Decimal
from functools import lru_cache
from itertools import chain, groupby, islice
from operator import itemgetter

from trytond.cache import Cache, LRUDictTransaction, freeze, unfreeze
from trytond.config import config
from trytond.const import OPERATORS
from trytond.exceptions import UserError
from trytond.i18n import gettext, lazy_gettext
from trytond.pool import Pool
from trytond.pyson import PYSON, PYSONDecoder, PYSONEncoder
from trytond.rpc import RPC
from trytond.tools import (
    grouped_slice, is_instance_method, likify, reduce_domain)
from trytond.tools.domain_inversion import domain_inversion, eval_domain
from trytond.tools.domain_inversion import parse as domain_parse
from trytond.transaction import (
    Transaction, inactive_records, record_cache_size, without_check_access)

from . import fields
from .descriptors import dualmethod
from .model import Model

__all__ = ['ModelStorage', 'EvalEnvironment']
_cache_field = config.getint('cache', 'field')
_cache_count_timeout = config.getint(
    'cache', 'count_timeout', default=60 * 60 * 24)
_cache_count_clear = config.getint(
    'cache', 'count_clear', default=1000)
_request_timeout = config.getint('request', 'timeout', default=0)
_request_records_limit = config.getint('request', 'records_limit')


def local_cache(Model, transaction=None):
    if transaction is None:
        transaction = Transaction()
    return LRUDictTransaction(record_cache_size(transaction), Model._record)


class AccessError(UserError):
    pass


class ImportDataError(UserError):
    pass


class ValidationError(UserError):
    pass


class DomainValidationError(ValidationError):
    pass


class RequiredValidationError(ValidationError):
    pass


class SizeValidationError(ValidationError):
    pass


class DigitsValidationError(ValidationError):
    pass


class ForbiddenCharValidationError(ValidationError):
    pass


class SelectionValidationError(ValidationError):
    pass


class TimeFormatValidationError(ValidationError):
    pass


class _UnsavedRecordError(ValueError):

    def __init__(self, record):
        self.record = record


def is_leaf(expression):
    return (isinstance(expression, (list, tuple))
        and len(expression) > 2
        and isinstance(expression[1], str)
        and expression[1] in OPERATORS)  # TODO remove OPERATORS test


class ModelStorage(Model):
    """
    Define a model with storage capability in Tryton.
    """
    __slots__ = ('_transaction', '_user', '_context', '_ids',
        '_transaction_cache', '_local_cache')

    create_uid = fields.Many2One(
        'res.user', lazy_gettext('ir.msg_created_by'), readonly=True)
    create_date = fields.Timestamp(
        lazy_gettext('ir.msg_created_at'), readonly=True)
    write_uid = fields.Many2One(
        'res.user', lazy_gettext('ir.msg_edited_by'), readonly=True)
    write_date = fields.Timestamp(
        lazy_gettext('ir.msg_edited_at'), readonly=True)
    rec_name = fields.Function(
        fields.Char(lazy_gettext('ir.msg_record_name')), 'get_rec_name',
        searcher='search_rec_name')
    xml_id = fields.Function(
        fields.Char(lazy_gettext('ir.msg_xml_id')), 'get_xml_id')
    _count_cache = Cache(
        'modelstorage.count', duration=_cache_count_timeout, context=False)
    _log = None

    @classmethod
    def __setup__(cls):
        from .modelview import ModelView
        super().__setup__()
        if issubclass(cls, ModelView):
            cls.__rpc__.update({
                    'create': RPC(
                        readonly=False,
                        size_limits={
                            0: _request_records_limit,
                            },
                        result=lambda r: list(map(int, r))),
                    'read': RPC(
                        timeout=_request_timeout,
                        size_limits={
                            0: _request_records_limit,
                            }),
                    'write': RPC(
                        readonly=False,
                        instantiate=slice(0, None, 2),
                        size_limits={
                            (0, None, 2): _request_records_limit,
                            }),
                    'delete': RPC(
                        readonly=False,
                        instantiate=0,
                        size_limits={
                            (0, None, 2): _request_records_limit,
                            }),
                    'copy': RPC(
                        readonly=False,
                        instantiate=0,
                        unique=False,
                        size_limits={
                            0: _request_records_limit,
                            },
                        result=lambda r: list(map(int, r))),
                    'search': RPC(
                        result=lambda r: list(map(int, r)),
                        size_limits={
                            2: _request_records_limit,
                            },
                        timeout=_request_timeout),
                    'search_count': RPC(
                        timeout=_request_timeout,
                        size_limits={
                            2: _request_records_limit,
                            }),
                    'search_read': RPC(
                        timeout=_request_timeout,
                        size_limits={
                            2: _request_records_limit,
                            }),
                    'resources': RPC(
                        instantiate=0,
                        unique=False,
                        timeout=_request_timeout),
                    'export_data_domain': RPC(
                        timeout=_request_timeout,
                        size_limits={
                            4: _request_records_limit,
                            }),
                    'export_data': RPC(
                        instantiate=0,
                        unique=False,
                        size_limits={
                            0: _request_records_limit,
                            },
                        timeout=_request_timeout),
                    'import_data': RPC(
                        readonly=False,
                        size_limits={
                            1: _request_records_limit,
                            }),
                    })
        if cls._log is None:
            cls._log = not cls.__name__.startswith('ir.')

    @classmethod
    def __post_setup__(cls):
        super().__post_setup__()

        cls._mptt_fields = set()
        cls._path_fields = set()
        for name, field in cls._fields.items():
            if (isinstance(field, fields.Many2One)
                    and field.model_name == cls.__name__):
                if field.path:
                    cls._path_fields.add(name)
                if field.left and field.right:
                    cls._mptt_fields.add(name)

    @staticmethod
    def default_create_uid():
        "Default value for uid field."
        return int(Transaction().user)

    @staticmethod
    def default_create_date():
        "Default value for create_date field."
        return datetime.datetime.today()

    @dualmethod
    def log(cls, records, event, target=None, user=None, **extra):
        if not cls._log:
            return
        pool = Pool()
        Log = pool.get('ir.model.log')
        transaction = Transaction()
        if user is None:
            user = transaction.user
        for record in records:
            assert record.id >= 0
            transaction.log_records.append(Log(
                    resource=record, event=event, target=target, user=user,
                    **extra))

    @classmethod
    def preprocess_values(cls, mode, values):
        assert mode in {'create', 'write'}
        return values.copy()

    @classmethod
    def _before_create(cls, vlist):
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        ModelFieldAccess = pool.get('ir.model.field.access')
        transaction = Transaction()

        ModelAccess.check(cls.__name__, 'create')

        all_fields = list(set().union(*vlist))
        ModelFieldAccess.check(cls.__name__, all_fields, 'write')

        # Increase transaction counter
        transaction.counter += 1

        count = cls._count_cache.get(cls.__name__)
        if count is not None:
            if random.random() < 1 / _cache_count_clear:
                cls._count_cache.set(cls.__name__, None)
            else:
                cls._count_cache.set(cls.__name__, count + len(vlist))
        with without_check_access():
            return [
                cls.preprocess_values('create', values) for values in vlist]

    @classmethod
    def create(cls, vlist):
        "Returns the list of created records."
        raise NotImplementedError

    @classmethod
    def _after_create(cls, ids):
        Trigger = Pool().get('ir.trigger')
        transaction = Transaction()
        check_access = transaction.user and transaction.check_access

        with without_check_access():
            triggers = Trigger.get_triggers(cls.__name__, 'create')

            for sub_ids in grouped_slice(ids, record_cache_size(transaction)):
                records = cls.browse(sub_ids)
                cls._validate(records)
                cls.check_modification(
                    'create', records, external=check_access)
                cls._compute_fields(records)
                cls.on_modification('create', records)
                if triggers:
                    for trigger in triggers:
                        trigger.queue_trigger_action(records)

            transaction.create_records[cls.__name__].update(ids)
            return ids

    @classmethod
    def _before_read(cls, ids, fields_names):
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        ModelFieldAccess = pool.get('ir.model.field.access')
        ModelAccess.check(cls.__name__, 'read')
        ModelFieldAccess.check(cls.__name__, fields_names, 'read')
        return ids, fields_names

    @classmethod
    def read(cls, ids, fields_names):
        """
        Read fields_names of record ids.
        The order is not guaranteed.
        """
        raise NotImplementedError

    @classmethod
    @without_check_access
    def _after_read(cls, vlist):
        return vlist

    @classmethod
    def index_get_field(cls, name):
        "Returns the index sort order of the field get calls."
        return 0

    @classmethod
    def _before_write(cls, *args):
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        ModelFieldAccess = pool.get('ir.model.field.access')
        Trigger = pool.get('ir.trigger')
        transaction = Transaction()
        check_access = transaction.user and transaction.check_access

        assert not len(args) % 2

        ModelAccess.check(cls.__name__, 'write')

        actions = iter(args)
        args = []
        field_names = set()
        on_write = []
        all_records, ids = [], []
        for records, values in zip(actions, actions):
            cls.__check_xml_record(records, values)
            ModelFieldAccess.check(cls.__name__, values.keys(), 'write')
            with without_check_access():
                cls.check_modification(
                    'write', records, values, external=check_access)
                on_write.extend(cls.on_write(records, values))
                args.append(records)
                args.append(cls.preprocess_values('write', values))
                if check_access and values:
                    cls.log(records, 'write', ','.join(sorted(values.keys())))
                field_names.update(values.keys())
                all_records.extend(records)
                ids.extend(map(int, records))

        trigger_eligibles = {}
        with without_check_access():
            # Call before cursor cache cleaning
            triggers = Trigger.get_triggers(cls.__name__, 'write')
            if triggers:
                for trigger in triggers:
                    trigger_eligibles[trigger] = []
                    for record in all_records:
                        if not Trigger.eval(trigger, record):
                            trigger_eligibles[trigger].append(record)

        # Increase transaction counter
        transaction.counter += 1

        # Clean local cache
        for record in all_records:
            record._local_cache.pop(record.id, None)

        # Clean transaction cache
        for cache in transaction.cache.values():
            if cls.__name__ in cache:
                cache_cls = cache[cls.__name__]
                for record in all_records:
                    cache_cls.pop(record.id, None)

        return ids, field_names, on_write, trigger_eligibles, *args

    @classmethod
    def write(cls, records, values, *args):
        '''
        Write values on records.
        '''
        raise NotImplementedError

    @classmethod
    @without_check_access
    def _after_write(cls, ids, field_names, on_write, trigger_eligibles):
        transaction = Transaction()

        for sub_ids in grouped_slice(ids, record_cache_size(transaction)):
            records = cls.browse(sub_ids)
            cls._validate(records, field_names=field_names)
            cls._compute_fields(records, field_names=field_names)
            cls.on_modification('write', records, field_names)
        for meth in on_write:
            meth()

        for trigger, records in trigger_eligibles.items():
            trigger.queue_trigger_action(records)

    @classmethod
    def on_write(cls, records, values):
        return []

    @classmethod
    def index_set_field(cls, name):
        "Returns the index sort order of the field set calls."
        return 0

    @classmethod
    def _before_delete(cls, records):
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        ModelData = pool.get('ir.model.data')
        Trigger = pool.get('ir.trigger')
        transaction = Transaction()
        check_access = transaction.user and transaction.check_access

        ModelAccess.check(cls.__name__, 'delete')
        cls.__check_xml_record(records, None)
        with without_check_access():
            cls.check_modification('delete', records, external=check_access)
            if ModelData.has_model(cls.__name__):
                ModelData.clean(records)
            if check_access:
                cls.log(records, 'delete')
            on_delete = cls.on_delete(records)
            cls.on_modification('delete', records)

            triggers = Trigger.get_triggers(cls.__name__, 'delete')
            if triggers:
                for trigger in triggers:
                    # Do not queue because records will be deleted
                    trigger.trigger_action(records)

        # Increase transaction counter
        transaction.counter += 1

        # Clean local cache
        for record in records:
            record._local_cache.pop(record.id, None)

        # Clean transaction cache
        for cache in transaction.cache.values():
            if cls.__name__ in cache:
                cache_cls = cache[cls.__name__]
                for record in records:
                    cache_cls.pop(record.id, None)

        count = cls._count_cache.get(cls.__name__)
        if count is not None:
            if random.random() < 1 / _cache_count_clear:
                cls._count_cache.set(cls.__name__, None)
            else:
                cls._count_cache.set(cls.__name__, count - len(records))

        ids = [r.id for r in records]
        if cls.__name__ in transaction.delete_records:
            ids = ids[:]
            for del_id in transaction.delete_records[cls.__name__]:
                while ids:
                    try:
                        ids.remove(del_id)
                    except ValueError:
                        break
        transaction.delete_records[cls.__name__].update(ids)
        return ids, on_delete

    @classmethod
    def delete(cls, records):
        "Delete records"
        raise NotImplementedError

    @classmethod
    @without_check_access
    def _after_delete(cls, ids, on_delete):
        pool = Pool()
        Translation = pool.get('ir.translation')
        if any(getattr(f, 'translate', False) and not hasattr(f, 'set')
                for f in cls._fields.values()):
            Translation.delete_ids(cls.__name__, 'model', ids)
        for meth in on_delete:
            meth()

    @classmethod
    def check_modification(cls, mode, records, values=None, external=False):
        assert mode in {'create', 'write', 'delete'}

    @classmethod
    def on_modification(cls, mode, records, field_names=None):
        assert mode in {'create', 'write', 'delete'}

    @classmethod
    def on_delete(cls, records):
        return []

    @classmethod
    def copy(cls, records, default=None):
        '''
        Duplicate the records and return a list of new records.
        '''
        pool = Pool()
        Lang = pool.get('ir.lang')
        if default is None:
            default = {}
        else:
            default = default.copy()

        def is_readonly(field):
            if field.readonly:
                return True
            if hasattr(field, 'get_relation'):
                Model = field.get_relation()
            elif hasattr(field, 'get_target'):
                Model = field.get_target()
            else:
                return False
            return (not issubclass(Model, ModelStorage)
                or callable(getattr(Model, 'table_query', None)))

        def get_default(name):
            prefix = name + '.'
            return {name[len(prefix):]: value
                for name, value in default.items()
                if name.startswith(prefix)}

        def convert_data(field_defs, origin, default_values):
            data = origin.copy()
            for field_name in field_defs:
                ftype = field_defs[field_name]['type']
                field = cls._fields[field_name]

                if field_name in (
                        'create_date',
                        'create_uid',
                        'write_date',
                        'write_uid',
                        ):
                    del data[field_name]
                    continue

                if field_name in default:
                    if callable(default[field_name]):
                        data[field_name] = default[field_name](origin)
                    else:
                        data[field_name] = default[field_name]
                if data[field_name] == default_values.get(field_name):
                    del data[field_name]
                elif (isinstance(field, fields.Function)
                        and not isinstance(field, fields.MultiValue)):
                    del data[field_name]
                elif ftype in ('many2one', 'one2one'):
                    try:
                        data[field_name] = data[field_name] and \
                            data[field_name][0]
                    except Exception:
                        pass
                elif ftype == 'one2many':
                    if is_readonly(field) or field.filter:
                        del data[field_name]
                    elif data[field_name]:
                        data[field_name] = [(
                                'copy', data[field_name],
                                get_default(field_name))]
                elif ftype == 'many2many':
                    if is_readonly(field) or field.filter:
                        del data[field_name]
                    elif data[field_name]:
                        data[field_name] = [('add', data[field_name])]
                elif ftype == 'binary':
                    # Copy only file_id
                    if (field.file_id
                            and origin.get(field.file_id)
                            and data[field_name] == origin.get(field_name)):
                        del data[field_name]
            if 'id' in data:
                del data['id']
            return data

        # Reset MPTT field to the default value
        mptt = set()
        for field in cls._fields.values():
            if (isinstance(field, fields.Many2One)
                    and field.model_name == cls.__name__
                    and field.left and field.right):
                mptt.add(field.left)
                mptt.add(field.right)
        fields_names = [n for n, f in cls._fields.items()
            if (not isinstance(f, fields.Function)
                or isinstance(f, fields.MultiValue))
            and n not in mptt]

        def _default_fields():
            return {k.split('.', 1)[0] for k in default.keys()}
        assert _default_fields() <= set(fields_names), (
            f"Invalid default fields {_default_fields() - set(fields_names)} "
            f"for {cls.__name__}")
        ids = list(map(int, records))
        with without_check_access():
            values = {
                d['id']: d for d in cls.read(ids, fields_names=fields_names)}
        field_defs = cls.fields_get(fields_names=fields_names)
        default_values = cls.default_get(fields_names, with_rec_name=False)
        to_create = []
        for id_ in ids:
            data = convert_data(field_defs, values[id_], default_values)
            to_create.append(data)
        new_records = cls.create(to_create)

        fields_translate = {}
        for field_name, field in field_defs.items():
            if (field_name in cls._fields
                    and getattr(cls._fields[field_name], 'translate', False)):
                fields_translate[field_name] = field

        if fields_translate:
            langs = Lang.search([
                ('translatable', '=', True),
                ])
            if langs:
                id2new_records = defaultdict(list)
                for id_, new_record in zip(ids, new_records):
                    id2new_records[id_].append(new_record)
                fields_names = list(fields_translate.keys()) + ['id']
                for lang in langs:
                    # Prevent fuzzing translations when copying as the terms
                    # should be the same.
                    with Transaction().set_context(language=lang.code,
                            fuzzy_translation=False):
                        default_values = cls.default_get(
                            fields_names, with_rec_name=False)
                        values = cls.read(ids, fields_names=fields_names)
                        to_write = []
                        for data in values:
                            to_write.append(id2new_records[data['id']])
                            to_write.append(
                                convert_data(
                                    fields_translate, data, default_values))
                        if to_write:
                            cls.write(*to_write)
        return new_records

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False):
        '''
        Return a list of records that match the domain.
        '''
        pool = Pool()
        transaction = Transaction()
        ModelAccess = pool.get('ir.model.access')
        ModelFieldAccess = pool.get('ir.model.field.access')

        ModelAccess.check(cls.__name__, 'read')

        def check_domain(domain, cls, to_check):
            if is_leaf(domain):
                local, relate = (domain[0].split('.', 1) + [None])[:2]
                to_check[cls.__name__].add(local)
                field = cls._fields[local]
                target = None
                if hasattr(field, 'get_target'):
                    target = cls._fields[local].get_target()
                    if (not relate
                            and (domain[1].endswith('child_of')
                                or domain[1].endswith('parent_of'))
                            and len(domain) >= 4):
                        relate = domain[3]
                        domain = domain[:3] + domain[4:]
                if field._type == 'reference' and len(domain) >= 4:
                    target = pool.get(domain[3])
                    domain = domain[:3] + domain[4:]
                if relate and target:
                    target_domain = [(relate,) + tuple(domain[1:])]
                    check_domain(target_domain, target, to_check)
            elif not domain:
                return
            else:
                i = 1 if domain[0] in ['OR', 'AND'] else 0
                for d in domain[i:]:
                    check_domain(d, cls, to_check)

        def check_order(order, cls, to_check):
            if not order:
                return
            for oexpr, otype in order:
                local, _, relate = oexpr.partition('.')
                to_check[cls.__name__].add(local)
                field = cls._fields[local]
                if relate and hasattr(field, 'get_target'):
                    target = field.get_target()
                    target_order = [(relate, otype)]
                    check_order(target_order, target, to_check)

        if transaction.user and transaction.check_access:
            to_check = defaultdict(set)
            check_domain(domain, cls, to_check)
            check_order(order, cls, to_check)
            for name, fields_names in to_check.items():
                ModelAccess.check(name, 'read')
                ModelFieldAccess.check(name, fields_names, 'read')
        if count:
            return 0
        return []

    @classmethod
    def search_count(cls, domain, offset=0, limit=None):
        '''
        Return the number of records that match the domain.
        '''
        res = cls.search(
            domain, order=[], count=True, offset=offset, limit=limit)
        if isinstance(res, list):
            return len(res)
        return res

    @classmethod
    def search_read(cls, domain, offset=0, limit=None, order=None,
            fields_names=None):
        '''
        Call search and read functions at once.
        Useful for the client to reduce the number of calls.
        '''
        records = cls.search(domain, offset=offset, limit=limit, order=order)

        if fields_names is None:
            fields_names = ['id']
        if 'id' not in fields_names:
            fields_names.append('id')
        rows = cls.read(list(map(int, records)), fields_names)
        index = {r.id: i for i, r in enumerate(records)}
        rows.sort(key=lambda r: index[r['id']])
        return rows

    @classmethod
    def _search_domain_active(cls, domain, active_test=True):
        # reduce_domain return a new instance so we can safety modify domain
        domain = reduce_domain(domain)
        # if the object has a field named 'active', filter out all inactive
        # records unless they were explicitly asked for
        if not ('active' in cls._fields and active_test):
            return domain

        def process(domain):
            i = 0
            active_found = False
            while i < len(domain):
                arg = domain[i]
                # add test for xmlrpc that doesn't handle tuple
                if is_leaf(arg):
                    if arg[0] == 'active':
                        active_found = True
                elif isinstance(arg, list):
                    domain[i] = process(domain[i])
                i += 1
            if not active_found:
                if (domain and ((isinstance(domain[0], str)
                                and domain[0] == 'AND')
                            or (not isinstance(domain[0], str)))):
                    domain.append(('active', '=', True))
                else:
                    domain = ['AND', domain, ('active', '=', True)]
            return domain
        return process(domain)

    @classmethod
    def estimated_count(cls):
        "Returns the estimation of the number of records."
        count = cls._count_cache.get(cls.__name__)
        if count is None:
            count = cls.search([], count=True)
            cls._count_cache.set(cls.__name__, count)
        return count

    def resources(self):
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        Note = pool.get('ir.note')

        return {
            'attachment_count': Attachment.search_count([
                    ('resource', '=', str(self)),
                    ]),
            'note_count': Note.search_count([
                    ('resource', '=', str(self)),
                    ]),
            'note_unread': Note.search_count([
                    ('resource', '=', str(self)),
                    ('unread', '=', True),
                    ]),
            }

    def get_rec_name(self, name):
        '''
        Return the rec_name of the instance.
        It is used by the Function field rec_name.
        '''
        rec_name = self._rec_name
        if rec_name not in self._fields:
            rec_name = 'id'
        return str(getattr(self, rec_name))

    @classmethod
    def search_rec_name(cls, name, clause):
        '''
        Return a list of arguments for search on rec_name.
        '''
        rec_name = cls._rec_name
        if rec_name not in cls._fields:
            return []
        return [(rec_name,) + tuple(clause[1:])]

    @classmethod
    def get_xml_id(cls, records, name):
        pool = Pool()
        ModelData = pool.get('ir.model.data')

        ids = dict.fromkeys(map(int, records))
        with without_check_access():
            for sub_records in grouped_slice(records):
                for record in ModelData.search([
                            ('model', '=', cls.__name__),
                            ('db_id', 'in', [r.id for r in sub_records]),
                            ]):
                    ids[record.db_id] = f'{record.module}.{record.fs_id}'
        return ids

    @classmethod
    def search_global(cls, text):
        '''
        Yield tuples (record, name, icon) for text
        '''
        for record in cls.search([
                    ('rec_name', 'ilike', likify(text)),
                    ]):
            yield record, record.rec_name, None

    @classmethod
    def browse(cls, ids):
        '''
        Return a list of instance for the ids
        '''
        transaction = Transaction()
        ids = list(map(int, ids))
        _local_cache = local_cache(cls, transaction)
        transaction_cache = transaction.get_cache()
        return [cls(x, _ids=ids,
                _local_cache=_local_cache,
                _transaction_cache=transaction_cache,
                _transaction=transaction) for x in ids]

    def __export_row(self, fields_names):
        pool = Pool()
        lines = []
        data = ['' for x in range(len(fields_names))]
        done = []
        for fpos in range(len(fields_names)):
            fields_tree = fields_names[fpos]
            if not fields_tree:
                continue
            value = self
            i = 0
            while i < len(fields_tree):
                if not isinstance(value, ModelStorage):
                    break
                field_name = fields_tree[i]
                descriptor = None
                language = None
                if '.' in field_name:
                    field_name, descriptor = field_name.split('.')
                elif ':lang=' in field_name:
                    field_name, language = field_name.split(':lang=')
                eModel = pool.get(value.__name__)
                field = eModel._fields[field_name]
                if field.states and 'invisible' in field.states:
                    invisible = _record_eval_pyson(
                        value, field.states['invisible'])
                    if invisible:
                        value = ''
                        break
                if descriptor:
                    value = getattr(field, descriptor)().__get__(value, eModel)
                elif language:
                    value = field.translated().__get__(value, eModel)(language)
                else:
                    value = getattr(value, field_name)
                if isinstance(value, (list, tuple)):
                    first = True
                    child_fields_names = [(x[:i + 1] == fields_tree[:i + 1]
                            and x[i + 1:]) or [] for x in fields_names]
                    if child_fields_names in done:
                        break
                    done.append(child_fields_names)
                    for child_record in value:
                        child_lines = child_record.__export_row(
                            child_fields_names)
                        if first:
                            if child_lines:
                                for child_fpos in range(len(fields_names)):
                                    if child_fields_names[child_fpos]:
                                        data[child_fpos] = (
                                            child_lines[0][child_fpos])
                            lines += child_lines[1:]
                            first = False
                        else:
                            lines += child_lines
                    break
                i += 1
            if i == len(fields_tree):
                if value is None:
                    value = ''
                elif isinstance(value, Model):
                    value = str(value)
                data[fpos] = value
        return [data] + lines

    @classmethod
    def _convert_field_names(cls, fields_names):
        pool = Pool()
        ModelField = pool.get('ir.model.field')
        Lang = pool.get('ir.lang')
        result = []
        for names in fields_names:
            descriptions = []
            class_ = cls
            for i, name in enumerate(names):
                translated = name.endswith('.translated')
                if translated:
                    name = name[:-len('.translated')]
                language = None
                if ':lang=' in name:
                    name, language = name.split(':lang=')
                field = class_._fields[name]
                field_name = ModelField.get_name(class_.__name__, name)
                if translated:
                    if isinstance(field, fields.Selection):
                        field_name = gettext(
                            'ir.msg_field_string', field=field_name)
                    elif isinstance(field, fields.Reference):
                        field_name = gettext(
                            'ir.msg_field_model_name', field=field_name)
                if language:
                    lang = Lang.get(language)
                    field_name += f' ({lang.name})'
                descriptions.append(field_name)
                if hasattr(field, 'get_target'):
                    class_ = field.get_target()
            result.append('/'.join(descriptions))
        return result

    @classmethod
    def export_data(cls, records, fields_names, header=False):
        fields_names = [x.split('/') for x in fields_names]
        data = []
        if header:
            data.append(cls._convert_field_names(fields_names))
        for record in records:
            data += record.__export_row(fields_names)
        return data

    @classmethod
    def export_data_domain(
            cls, domain, fields_names, offset=0, limit=None, order=None,
            header=False):
        records = cls.search(domain, limit=limit, offset=offset, order=order)
        return cls.export_data(records, fields_names, header=header)

    @classmethod
    def import_data(cls, fields_names, data):
        '''
        Create records for all values in data.
        The field names of values must be defined in fields_names.
        '''
        pool = Pool()

        row_index = data.index

        class _Error(Exception):
            def __init__(self, msg_id, **variables):
                self.msg_id = msg_id
                self.variables = variables

        def error(func):
            def wrapper(line, index, *args, **kwargs):
                try:
                    return func(line[index], *args, **kwargs)
                except _Error as e:
                    raise ImportDataError(gettext(
                            e.msg_id, **e.variables,
                            row=row_index(line) + 1,
                            column=index + 1)) from e
            return wrapper

        @error
        @lru_cache(maxsize=1000)
        def get_many2one(value, relation):
            if not value:
                return None
            Relation = pool.get(relation)
            res = Relation.search([
                ('rec_name', '=', value),
                ], limit=2)
            if len(res) < 1:
                raise _Error(
                    'ir.msg_relation_not_found',
                    value=value,
                    **Relation.__names__())
            elif len(res) > 1:
                raise _Error(
                    'ir.msg_too_many_relations_found',
                    value=value,
                    **Relation.__names__())
            else:
                res = res[0].id
            return res

        @error
        @lru_cache(maxsize=1000)
        def get_many2many(value, relation):
            if not value:
                return None
            res = []
            Relation = pool.get(relation)
            for word in next(csv.reader(value.splitlines(), delimiter=',',
                    quoting=csv.QUOTE_NONE, escapechar='\\')):
                res2 = Relation.search([
                    ('rec_name', '=', word),
                    ], limit=2)
                if len(res2) < 1:
                    raise _Error(
                        'ir.msg_relation_not_found',
                        value=word,
                        **Relation.__names__())
                elif len(res2) > 1:
                    raise _Error(
                        'ir.msg_too_many_relations_found',
                        value=word,
                        **Relation.__names__())
                else:
                    res.append(res2[0].id)
            return res

        def get_one2one(*args, **kwargs):
            return ('add', get_many2one(*args, **kwargs))

        @error
        @lru_cache(maxsize=1000)
        def get_reference(value, field, klass):
            if not value:
                return None
            try:
                relation, value = value.split(',', 1)
                Relation = pool.get(relation)
            except (ValueError, KeyError) as e:
                raise _Error(
                    'ir.msg_reference_syntax_error',
                    value=value,
                    **klass.__names__(field)) from e
            res = Relation.search([
                ('rec_name', '=', value),
                ], limit=2)
            if len(res) < 1:
                raise _Error(
                    'ir.msg_relation_not_found',
                    value=value,
                    **Relation.__names__())
            elif len(res) > 1:
                raise _Error(
                    'ir.msg_too_many_relations_found',
                    value=value,
                    **Relation.__names__())
            else:
                res = '%s,%s' % (relation, res[0].id)
            return res

        def dispatch(create, write, row, Relation=cls):
            id_ = row.pop('id', None)
            if id_:
                write.append([Relation(id_)])
                write.append(row)
            else:
                create.append(row)
            return id_

        @error
        def convert(value, ftype, field, klass):
            def convert_boolean(value):
                if value.lower() == 'true':
                    return True
                elif value.lower() == 'false':
                    return False
                elif not value:
                    return False
                else:
                    return bool(int(value))

            def convert_integer(value):
                if isinstance(value, int):
                    return value
                elif value:
                    return int(value)

            def convert_float(value):
                if isinstance(value, float):
                    return value
                elif value:
                    return float(value)

            def convert_numeric(value):
                if isinstance(value, Decimal):
                    return value
                elif value:
                    return Decimal(value)

            def convert_date(value):
                if isinstance(value, datetime.date):
                    return value
                elif value:
                    return datetime.date.fromisoformat(value)

            def convert_datetime(value):
                if isinstance(value, datetime.datetime):
                    return value
                elif value:
                    return datetime.datetime.strptime(
                        value, '%Y-%m-%d %H:%M:%S')

            def convert_timedelta(value):
                if isinstance(value, datetime.timedelta):
                    return value
                elif value:
                    try:
                        return float(value)
                    except ValueError:
                        hours, minutes, seconds = (
                            value.split(':') + ['00'])[:3]
                        return datetime.timedelta(
                            hours=int(hours), minutes=int(minutes),
                            seconds=float(seconds))

            def convert_binary(value):
                if not isinstance(value, bytes):
                    return base64.b64decode(value)
                elif value:
                    return value

            try:
                func = locals()['convert_%s' % ftype]
            except KeyError:
                return value
            try:
                return func(value)
            except (ValueError, TypeError, decimal.InvalidOperation) as e:
                raise _Error(
                    'ir.msg_value_syntax_error',
                    value=value,
                    **klass.__names__(field)) from e

        def process_lines(data, prefix, fields_def, position=0, klass=cls):
            line = data[position]
            row = {}
            translate = {}
            todo = set()
            prefix_len = len(prefix)
            many2many = set()
            if len(fields_names) > len(line):
                n = len(fields_names) - len(line)
                if n > 1:
                    raise ImportDataError(gettext(
                            'ir.msg_import_data_missing_columns',
                            n=n,
                            row=row_index(line) + 1))
                else:
                    raise ImportDataError(gettext(
                            'ir.msg_import_data_missing_column',
                            row=row_index(line) + 1))
            # Import normal fields_names
            for i, field in enumerate(fields_names):
                is_prefix_len = (len(field) == (prefix_len + 1))
                if is_prefix_len and ':lang=' in field[-1]:
                    field_name, lang = field[-1].split(':lang=')
                    translate.setdefault(lang, {})[field_name] = line[i]
                elif is_prefix_len and prefix == field[:-1]:
                    field_name = field[-1]
                    this_field_def = fields_def[field_name]
                    field_type = this_field_def['type']
                    res = None
                    if field_name == 'id':
                        try:
                            res = int(line[i])
                        except ValueError:
                            res = get_many2one(line, i, klass.__name__)
                    elif field_type == 'many2one':
                        res = get_many2one(line, i, this_field_def['relation'])
                    elif field_type == 'many2many':
                        many2many.add(field_name)
                        res = get_many2many(
                            line, i, this_field_def['relation'])
                        res = [('add', res)] if res else []
                    elif field_type == 'one2one':
                        res = get_one2one(line, i, this_field_def['relation'])
                    elif field_type == 'reference':
                        res = get_reference(line, i, field_name, klass)
                    else:
                        res = convert(line, i, field_type, field_name, klass)
                    row[field_name] = res
                elif prefix == field[0:prefix_len]:
                    todo.add(field[prefix_len])

            if 'id' in row:
                record = klass(row['id'])
                for field_name in many2many:
                    row[field_name].insert(
                        0, ('remove',
                            [x.id for x in getattr(record, field_name)]))
            else:
                record = None

            # Import one2many fields
            nbrmax = 1
            for field in todo:
                Relation = pool.get(fields_def[field]['relation'])
                newfd = Relation.fields_get()
                newrow, max2, _ = process_lines(
                    data, prefix + [field], newfd, position, klass=Relation)
                nbrmax = max(nbrmax, max2)
                create, write = [], []
                dispatch(create, write, newrow, Relation)
                i = max2
                while (position + i) < len(data):
                    test = True
                    for j, field2 in enumerate(fields_names):
                        if (len(field2) <= (prefix_len + 1)
                                and data[position + i][j]):
                            test = False
                            break
                    if not test:
                        break
                    newrow, max2, _ = process_lines(
                        data, prefix + [field], newfd, position + i,
                        klass=Relation)
                    dispatch(create, write, newrow, Relation)
                    i += max2
                    nbrmax = max(nbrmax, i)
                row[field] = []
                create = [v for v in create if any(v.values())]
                if create:
                    row[field].append(('create', create))
                if write:
                    row[field].append(('write',) + tuple(write))
                if record:
                    written = set(map(int, sum(write[0:None:2], [])))
                    delete = [
                        r.id for r in getattr(record, field)
                        if r.id not in written]
                    row[field].append(('delete', delete))

            if prefix_len == 0:
                for i in range(max(nbrmax, 1)):
                    data.pop(0)
            return (row, nbrmax, translate)

        fields_names = [x.split('/') for x in fields_names]
        fields_def = cls.fields_get()

        to_create, to_create_translations = [], []
        to_write, to_write_translations = [], []
        languages = set()
        data = data.copy()
        while data:
            (row, _, translate) = \
                process_lines(data, [], fields_def)
            if dispatch(to_create, to_write, row):
                to_write_translations.append(translate)
            else:
                to_create_translations.append(translate)
            languages.update(translate)

        def translate(records, translations):
            for language in languages:
                translated = [t.get(language, {}) for t in translations]
                with Transaction().set_context(language=language):
                    cls.write(*chain(*filter(itemgetter(1),
                                zip(([r] for r in records), translated))))
        count = 0
        if to_create:
            records = cls.create(to_create)
            translate(records, to_create_translations)
            count += len(records)
        if to_write:
            cls.write(*to_write)
            records = sum(to_write[0:None:2], [])
            translate(records, to_write_translations)
            count += len(records)
        return count

    @classmethod
    def __check_xml_record(cls, records, values):
        ModelData = Pool().get('ir.model.data')
        # Allow root user to update/delete
        if (Transaction().user == 0
                or not ModelData.has_model(cls.__name__)):
            return
        ModelData.can_modify(records, values)

    @classmethod
    @without_check_access
    def _compute_fields(cls, records, field_names=None):
        to_write = []
        for record in records:
            values = record.compute_fields(field_names)
            if values:
                to_write.extend([[record], values])
        if to_write:
            cls.write(*to_write)

    def compute_fields(self, field_names=None):
        return {}

    @classmethod
    def validate(cls, records):
        pass

    @classmethod
    def validate_fields(cls, records, field_names):
        pass

    @classmethod
    def _validate(cls, records, field_names=None):
        pool = Pool()

        def is_pyson(test):
            if isinstance(test, PYSON):
                return True
            if isinstance(test, (list, tuple)):
                for i in test:
                    if isinstance(i, PYSON):
                        return True
                    if isinstance(i, (list, tuple)):
                        if is_pyson(i):
                            return True
            if isinstance(test, dict):
                for key, value in list(test.items()):
                    if isinstance(value, PYSON):
                        return True
                    if isinstance(value, (list, tuple, dict)):
                        if is_pyson(value):
                            return True
            return False

        def validate_domain(field):
            if not field.domain:
                return
            if field._type == 'dict':
                return
            if (field._type not in {
                        'many2one', 'one2many', 'many2many', 'one2one',
                        'reference'}
                    and not field.searchable(cls)):
                return

            def get_relation(record):
                if field._type in ('many2one', 'one2many'):
                    Relation = pool.get(field.model_name)
                elif field._type in ('many2many', 'one2one'):
                    Relation = field.get_target()
                elif field._type == 'reference':
                    value = getattr(record, field.name)
                    Relation = (
                        value.__class__ if isinstance(value, ModelStorage)
                        else None)
                else:
                    Relation = cls
                return Relation

            domains = defaultdict(lambda: defaultdict(list))
            if is_pyson(field.domain) or is_pyson(field.context):
                encoder = PYSONEncoder()
                pyson_domain = encoder.encode(field.domain)
                pyson_context = encoder.encode(field.context)
                dict_domain = False
                for record in records:
                    domain = _record_eval_pyson(
                        record, pyson_domain, encoded=True)
                    if isinstance(domain, dict):
                        dict_domain = True
                        relation = get_relation(record)
                        if relation:
                            domain = domain.get(relation.__name__, [])
                        else:
                            domain = []
                    domain = freeze(domain)
                    context = freeze(_record_eval_pyson(
                            record, pyson_context, encoded=True))
                    domains[context][domain].append(record)
                # Select strategy depending if it is closer to one domain per
                # record or one domain for all records
                # Do not use IN_MAX to let spaces for the pyson domain
                in_max = Transaction().database.IN_MAX
                count = in_max // 10
                for context, ctx_domains in domains.items():
                    if (not dict_domain
                            and len(ctx_domains) > len(records) * 0.5):
                        new_domains = {}
                        for sub_domains in grouped_slice(
                                list(ctx_domains.keys()), count):
                            grouped_domain = ['OR']
                            grouped_records = []
                            for d in sub_domains:
                                sub_records = ctx_domains[d]
                                grouped_records.extend(sub_records)
                                relations = relation_domain(field, sub_records)
                                if len(relations) > in_max:
                                    break
                                grouped_domain.append(
                                    [('id', 'in',
                                            [r.id for r in relations]), d])
                            else:
                                new_domains[freeze(grouped_domain)] = \
                                    grouped_records
                                continue
                            break
                        else:
                            domains[context] = new_domains
            else:
                domains[freeze(field.context)][freeze(field.domain)].extend(
                    records)

            for context, ctx_domains in domains.items():
                for domain, ctx_records in ctx_domains.items():
                    domain = unfreeze(domain)
                    for Relation, sub_records in groupby(
                            ctx_records, key=get_relation):
                        if not Relation:
                            continue
                        if isinstance(domain, dict):
                            sub_domain = domain.get(Relation.__name__)
                            if not sub_domain:
                                continue
                        else:
                            sub_domain = domain
                        with Transaction().set_context(unfreeze(context)):
                            validate_relation_domain(
                                field, list(sub_records), Relation, sub_domain)

        def relation_domain(field, records):
            relations = set()
            if field._type in {'many2one', 'one2one', 'reference'}:
                relations.update(getattr(r, field.name) for r in records)
            elif field._type in {'one2many', 'many2many'}:
                relations.update(*(getattr(r, field.name) for r in records))
            else:
                # Cache alignment is not a problem
                relations = {
                    r for r in records
                    if getattr(r, field.name) is not None}
            relations.discard(None)
            return relations

        def validate_relation_domain(field, records, Relation, domain):
            relations = relation_domain(field, records)
            if relations:
                for sub_relations in grouped_slice(relations):
                    sub_relations = set(sub_relations)
                    finds = Relation.search(['AND',
                            [('id', 'in', [r.id for r in sub_relations])],
                            domain,
                            ])
                    invalid_relations = sub_relations - set(finds)
                    if Relation == cls and field._type not in {
                            'many2one', 'one2many', 'many2many', 'one2one',
                            'reference'}:
                        invalid_records = invalid_relations
                    elif field._type.endswith('2many'):
                        invalid_records = [
                            r for r in records
                            if invalid_relations.intersection(
                                getattr(r, field.name))]
                    else:
                        invalid_records = [
                            r for r in records
                            if getattr(r, field.name) in invalid_relations]
                    if invalid_records:
                        invalid_record = invalid_records.pop()
                        if invalid_relations == invalid_records:
                            invalid_relation = invalid_record
                        else:
                            invalid_relation = getattr(
                                invalid_record, field.name)
                        domain = field.domain
                        if is_pyson(domain):
                            domain = _record_eval_pyson(records[0], domain)
                        if isinstance(domain, dict):
                            domain = domain.get(Relation.__class__, [])
                        msg = gettext(
                            'ir.msg_domain_validation_record',
                            **cls.__names__(field.name, invalid_record))
                        fields = set()
                        level = 0
                        if field not in Relation._fields.values():
                            expression = domain_parse(domain)
                            for variable in expression.variables:
                                parts = variable.split('.')
                                fields.add(parts[0])
                                level = max(level, len(parts))
                        else:
                            fields.add(field.name)
                        for field_name in sorted(fields):
                            env = EvalEnvironment(invalid_relation, Relation)
                            invalid_domain = domain_inversion(
                                domain, field_name, env)
                            if isinstance(invalid_domain, bool):
                                continue
                            if (len(fields) > 1  # no need to evaluate
                                    and eval_domain(invalid_domain, env)):
                                continue
                            field_def = Relation.fields_get(
                                [field_name], level=level)
                            raise DomainValidationError(
                                msg, domain=(invalid_domain, field_def))
                        field_def = Relation.fields_get(fields, level=level)
                        raise DomainValidationError(
                            msg, domain=(domain, field_def))

        if field_names is None:
            field_names = cls._fields.keys()
        elif not isinstance(field_names, set):
            field_names = set(field_names)
        function_fields = {name for name, field in cls._fields.items()
            if isinstance(field, fields.Function)}
        with inactive_records():
            for field_name, field in cls._fields.items():
                if (field_name not in field_names
                        and not (field.validation_depends & field_names)
                        and not (field.validation_depends & function_fields)):
                    continue
                if isinstance(field, fields.Function) and not pool.test:
                    continue

                validate_domain(field)

                def required_test(record, field):
                    value = getattr(record, field.name)
                    if ((
                                isinstance(value,
                                    (type(None), bool, list, tuple, str, dict))
                                and not value)
                            or (field._type == 'reference'
                                and not isinstance(value, ModelStorage))):
                        raise RequiredValidationError(
                            gettext('ir.msg_required_validation_record',
                                **cls.__names__(field_name, record)))
                # validate states required
                if field.states and 'required' in field.states:
                    if is_pyson(field.states['required']):
                        pyson_required = PYSONEncoder().encode(
                                field.states['required'])
                        for record in records:
                            required = _record_eval_pyson(
                                record, pyson_required, encoded=True)
                            if required:
                                required_test(record, field)
                    else:
                        if field.states['required']:
                            for record in records:
                                required_test(record, field)
                # validate required
                if field.required:
                    for record in records:
                        required_test(record, field)
                # validate size
                if hasattr(field, 'size') and field.size is not None:
                    for record in records:
                        if isinstance(field.size, PYSON):
                            field_size = _record_eval_pyson(record, field.size)
                        else:
                            field_size = field.size
                        size = len(getattr(record, field_name) or '')
                        if field_size is not None and (size > field_size >= 0):
                            error_args = cls.__names__(field_name, record)
                            error_args['size'] = size
                            error_args['max_size'] = field_size
                            raise SizeValidationError(
                                gettext('ir.msg_size_validation_record',
                                    **error_args))

                def digits_test(record, digits, field_name):
                    def raise_error(value):
                        error_args = cls.__names__(field_name, record)
                        error_args['digits'] = digits
                        raise DigitsValidationError(
                            gettext('ir.msg_digits_validation_record',
                                **error_args))

                    value = getattr(record, field_name)
                    if isinstance(digits, str):
                        digit_record = getattr(record, digits)
                        if digit_record:
                            digits = digit_record.get_digits()
                        else:
                            digits = None
                    if value is None or not digits:
                        return

                    int_size, dec_size = digits
                    if int_size is not None and value:
                        if math.ceil(math.log10(abs(value))) > int_size:
                            raise_error(value)
                    if dec_size is not None:
                        if isinstance(value, Decimal):
                            if value.as_tuple().exponent < -dec_size:
                                raise_error(value)
                        else:
                            if round(value, dec_size) != value:
                                raise_error(value)
                # validate digits
                if getattr(field, 'digits', None):
                    if is_pyson(field.digits):
                        pyson_digits = PYSONEncoder().encode(field.digits)
                        for record in records:
                            digits = _record_eval_pyson(
                                record, pyson_digits, encoded=True)
                            digits_test(record, digits, field_name)
                    else:
                        for record in records:
                            digits_test(record, field.digits, field_name)

                if hasattr(field, 'forbidden_chars'):
                    for record in records:
                        value = getattr(record, field_name)
                        if value and any(
                                c in value for c in field.forbidden_chars):
                            error_args = cls.__names__(field_name, record)
                            error_args['chars'] = ','.join(
                                repr(c) for c in field.forbidden_chars
                                if c in value)
                            raise ForbiddenCharValidationError(gettext(
                                    'ir.msg_forbidden_char_validation_record',
                                    **error_args))

                # validate selection
                if hasattr(field, 'selection') and field.selection:
                    if isinstance(field.selection, (tuple, list)):
                        test = set(dict(field.selection).keys())
                        instance_sel_func = False
                    else:
                        sel_func = getattr(cls, field.selection)
                        instance_sel_func = is_instance_method(
                            cls, field.selection)
                        if not instance_sel_func:
                            test = set(dict(sel_func()))

                    for record in records:
                        value = getattr(record, field_name)
                        if field._type == 'reference':
                            if isinstance(value, ModelStorage):
                                value = value.__class__.__name__
                            elif value:
                                value, _ = value.split(',')
                        if instance_sel_func:
                            test = set(dict(sel_func(record)))
                        # None and '' are equivalent
                        if '' in test or None in test:
                            test.add('')
                            test.add(None)
                        if field._type != 'multiselection':
                            values = [value]
                        else:
                            values = value or []
                        for value in values:
                            if value not in test:
                                error_args = cls.__names__(field_name, record)
                                error_args['value'] = value
                                raise SelectionValidationError(gettext(
                                        'ir.msg_selection_validation_record',
                                        **error_args))

                def format_test(record, format, field_name):
                    value = getattr(record, field_name)
                    if not value:
                        return
                    if not isinstance(value, datetime.time):
                        value = value.time()
                    if value != datetime.datetime.strptime(
                            value.strftime(format), format).time():
                        error_args = cls.__names__(field_name, record)
                        raise TimeFormatValidationError(
                            gettext('ir.msg_time_format_validation_record',
                                **error_args))

                # validate time format
                if (field._type in ('datetime', 'time')
                        and field_name not in ('create_date', 'write_date')):
                    if is_pyson(field.format):
                        pyson_format = PYSONDecoder().encode(field.format)
                        for record in records:
                            env = EvalEnvironment(record, cls)
                            env.update(Transaction().context)
                            env['current_date'] = datetime.datetime.today()
                            env['time'] = time
                            env['context'] = Transaction().context
                            env['active_id'] = record.id
                            format = PYSONDecoder(env).decode(pyson_format)
                            format_test(record, format, field_name)
                    else:
                        for record in records:
                            format_test(record, field.format, field_name)

        for record in records:
            record.pre_validate()

        cls.validate(records)
        cls.validate_fields(records, field_names)

    @classmethod
    def _clean_defaults(cls, defaults):
        pool = Pool()
        vals = {}
        for field in defaults.keys():
            if '.' in field:  # skip all related fields
                continue
            fld_def = cls._fields[field]
            if fld_def._type in ('many2one', 'one2one'):
                if isinstance(defaults[field], (list, tuple)):
                    vals[field] = defaults[field][0]
                else:
                    vals[field] = defaults[field]
            elif fld_def._type in ('one2many',):
                obj = pool.get(fld_def.model_name)
                vals[field] = []
                for defaults2 in defaults[field]:
                    vals2 = obj._clean_defaults(defaults2)
                    if vals2:
                        vals[field].append(('create', [vals2]))
            elif fld_def._type in ('many2many',):
                vals2 = defaults[field]
                if vals2:
                    vals[field] = [('add', vals2)]
            elif fld_def._type in ('boolean',):
                vals[field] = bool(defaults[field])
            else:
                vals[field] = defaults[field]
        return vals

    def __init__(self, id=None, **kwargs):
        _ids = kwargs.pop('_ids', None)
        _local_cache = kwargs.pop('_local_cache', None)
        _transaction_cache = kwargs.pop('_transaction_cache', None)
        transaction = kwargs.pop('_transaction', None)
        if transaction is None:
            transaction = Transaction()
        self._transaction = transaction
        self._user = transaction.user
        self._context = transaction.context
        if id is not None:
            id = int(id)
        if _ids is not None:
            assert id in _ids
            assert all(isinstance(i, int) for i in _ids)
            self._ids = _ids
        else:
            self._ids = [id]

        if _transaction_cache is not None:
            self._transaction_cache = _transaction_cache
        else:
            self._transaction_cache = transaction.get_cache()

        if _local_cache is not None:
            assert isinstance(_local_cache, LRUDictTransaction)
            self._local_cache = _local_cache
        else:
            self._local_cache = local_cache(self.__class__, transaction)

        super().__init__(id, **kwargs)

    @property
    def _cache(self):
        return self._transaction_cache[self.__name__]

    def __getattr__(self, name):
        try:
            return super().__getattr__(name)
        except AttributeError:
            if name.startswith('_') or self.id is None or self.id < 0:
                raise

        self._local_cache.refresh()

        try:
            return self._local_cache[self.id][name]
        except KeyError:
            pass

        # fetch the definition of the field
        try:
            field = self._fields[name]
        except KeyError:
            raise AttributeError('"%s" has no attribute "%s"' % (self, name))

        try:
            if field._type not in (
                    'many2one', 'reference',
                    'one2many', 'many2many', 'one2one',
                    ):
                # fill local cache for quicker access later
                value \
                        = self._local_cache[self.id][name] \
                        = self._cache[self.id][name]
                return value
            else:
                skip_eager = (
                    name in self._cache[self.id]
                    and not field.context
                    and (not getattr(field, 'datetime_field', None)
                        or field.datetime_field in self._cache[self.id]))
        except KeyError:
            skip_eager = False

        pool = Pool()

        # build the list of fields we will fetch
        ffields = {
            name: field,
            }
        load_eager = field.loading == 'eager' and not skip_eager
        multiple_getter = None
        if (field.loading == 'lazy'
                and isinstance(field, fields.Function)
                and field.getter_multiple(
                    getattr(self.__class__, field.getter))):
            multiple_getter = field.getter

        if load_eager or multiple_getter:
            FieldAccess = pool.get('ir.model.field.access')
            fread_accesses = {}
            fread_accesses.update(FieldAccess.check(self.__name__,
                list(self._fields.keys()), 'read', access=True))
            to_remove = set(x for x, y in fread_accesses.items()
                    if not y and x != name)

            def not_cached(item):
                fname, field = item
                return ((self.id not in self._cache
                        or fname not in self._cache[self.id])
                    and (self.id not in self._local_cache
                        or fname not in self._local_cache[self.id]))

            def to_load(item):
                fname, field = item
                if fname in to_remove:
                    return False
                if multiple_getter:
                    return getattr(field, 'getter', None) == multiple_getter
                return field.loading == 'eager'

            ifields = filter(to_load,
                filter(not_cached,
                    iter(self._fields.items())))
            ifields = islice(ifields, 0, _cache_field)
            ffields.update(ifields)

        # add datetime_field
        for field in list(ffields.values()):
            if hasattr(field, 'datetime_field') and field.datetime_field:
                if field.datetime_field not in ffields:
                    datetime_field = self._fields[field.datetime_field]
                    ffields[field.datetime_field] = datetime_field

        # add depends of field with context
        for field in list(ffields.values()):
            if field.context:
                eval_fields = fields.get_eval_fields(field.context)
                for context_field_name in eval_fields:
                    if context_field_name not in field.validation_depends:
                        continue
                    if context_field_name not in ffields:
                        context_field = self._fields.get(context_field_name)
                        ffields[context_field_name] = context_field

        delete_records = self._transaction.delete_records.get(
            self.__name__, set())

        def cached(id_):
            names = set()
            if id_ in self._cache:
                names.update(self._cache[id_]._keys())
            if id_ in self._local_cache:
                names.update(self._local_cache[id_]._keys())
            return names

        def filter_(id_):
            return (id_ == self.id  # Ensure the value is read
                or (id_ not in delete_records
                    and not ffields.keys() <= cached(id_)))

        def unique(ids):
            s = set()
            for id_ in ids:
                if id_ not in s:
                    s.add(id_)
                    yield id_
        read_size = max(1, min(
                self._cache.size_limit, self._local_cache.size_limit,
                self._transaction.database.IN_MAX))
        index = self._ids.index(self.id)
        ids = islice(self._ids, index, index + read_size)
        ids = unique(filter(filter_, ids))

        kwargs_cache = {}
        pysoned_ctx = {}
        transaction = self._transaction

        def create_instances(Model, value, cache_key=None):
            cache_key = (Model, cache_key)
            if not (kwargs := kwargs_cache.get(cache_key)):
                if cache_key not in model2cache:
                    model2cache[cache_key] = local_cache(Model, transaction)
                kwargs_cache[cache_key] = kwargs = {
                    '_local_cache': model2cache[cache_key],
                    '_ids': model2ids.setdefault(cache_key, []),
                    '_transaction_cache': transaction.get_cache(),
                    '_transaction': transaction,
                    }
            ids = kwargs['_ids']
            if field._type in {'many2one', 'one2one', 'reference'}:
                ids.append(value)
                return Model(value, **kwargs)
            elif field._type in {'one2many', 'many2many'}:
                ids.extend(value)
                return tuple(Model(id, **kwargs) for id in value)

        def instantiate(field, value, data):
            if field._type in ('many2one', 'one2one', 'reference'):
                if value is None or value is False:
                    return None
            elif field._type in ('one2many', 'many2many'):
                if not value:
                    return ()
            try:
                if field._type == 'reference':
                    model_name, record_id = value.split(',')
                    Model = pool.get(model_name)
                    try:
                        record_id = int(record_id)
                    except ValueError:
                        return value
                    if record_id < 0:
                        return value
                    value = record_id
                else:
                    Model = field.get_target()
            except KeyError:
                return value
            if ((datetime_field := getattr(field, 'datetime_field', None))
                    or field.context):
                ctx = {}
                if field.context:
                    if not (pyson_context := pysoned_ctx.get(field)):
                        pyson_context = PYSONEncoder().encode(field.context)
                        pysoned_ctx[field] = pyson_context
                    ctx.update(PYSONDecoder(data).decode(pyson_context))
                if datetime_field:
                    ctx['_datetime'] = data.get(datetime_field)
                with transaction.set_context(**ctx):
                    return create_instances(Model, value, freeze(ctx))
            else:
                return create_instances(Model, value)

        model2ids = {}
        model2cache = {}
        # Read the data
        with Transaction().set_current_transaction(transaction), \
                self._transaction.set_user(self._user), \
                self._transaction.reset_context(), \
                self._transaction.set_context(self._context), \
                without_check_access():
            if (self.id in self._cache and name in self._cache[self.id]
                    and ffields.keys() <= set(self._cache[self.id]._keys())):
                # Use values from cache
                read_data = []
                for id_ in islice(self._ids, index, index + read_size):
                    if id_ in self._cache:
                        data = {'id': id_}
                        for fname in ffields:
                            if fname not in self._cache[id_]:
                                break
                            data[fname] = self._cache[id_][fname]
                        else:
                            read_data.append(data)
            else:
                # Order data read to update cache in the same order
                index = {i: n for n, i in enumerate(ids)}
                read_data = self.read(list(index.keys()), list(ffields.keys()))
                read_data.sort(key=lambda r: index[r['id']])
            # create browse records for 'remote' models
            no_local_cache = {'binary'}
            if not transaction.readonly:
                no_local_cache |= {
                    'one2one', 'one2many', 'many2many', 'reference'}
            for data in read_data:
                id_ = data['id']
                to_delete = set()
                for fname, field in ffields.items():
                    fvalue = data[fname]
                    if field._type in {
                            'many2one', 'one2one', 'one2many', 'many2many',
                            'reference'}:
                        if (fname != name
                                and field._type not in no_local_cache):
                            continue
                        fvalue = instantiate(field, data[fname], data)
                    if id_ == self.id and fname == name:
                        value = fvalue
                    if fname not in self._local_cache[id_]:
                        self._local_cache[id_][fname] = fvalue
                    if (field._type in no_local_cache
                            or (isinstance(field, fields.Function)
                                and (not transaction.readonly
                                    or field.getter_with_context))):
                        to_delete.add(fname)
                self._cache[id_]._update(
                    **{k: v for k, v in data.items() if k not in to_delete})
        return value

    def _save_values(self):
        values = {}
        if not self._values:
            return values
        for fname, value in self._values._items():
            field = self._fields[fname]
            if isinstance(field, fields.Function) and not field.setter:
                continue
            if field._type in ('many2one', 'one2one', 'reference'):
                if value:
                    if ((value.id is None or value.id < 0)
                            and field._type != 'reference'):
                        raise _UnsavedRecordError(value)
                    if field._type == 'reference':
                        value = str(value)
                    else:
                        value = value.id
            if field._type in ('one2many', 'many2many'):
                targets = value
                if self.id is not None and self.id >= 0:
                    _values, self._values = self._values, None
                    try:
                        previous = [t.id for t in getattr(self, fname)]
                    finally:
                        self._values = _values
                else:
                    previous = []
                to_add = []
                to_create = []
                to_write = []
                for target in targets:
                    if (field._type == 'one2many'
                            and field.field
                            and target._values):
                        t_values = target._values._copy()
                        # Don't look at reverse field
                        target._values._pop(field.field, None)
                    else:
                        t_values = None
                    try:
                        if target.id is None or target.id < 0:
                            to_create.append(target._save_values())
                        else:
                            if target.id in previous:
                                previous.remove(target.id)
                            else:
                                to_add.append(target.id)
                            target_values = target._save_values()
                            if target_values:
                                to_write.append(
                                    ('write', [target.id], target_values))
                    finally:
                        if t_values:
                            target._values = t_values
                value = []
                if previous:
                    to_delete, to_remove = [], []
                    deleted = removed = None
                    if self._deleted:
                        deleted = self._deleted[fname]
                    if self._removed:
                        removed = self._removed[fname]
                    for id_ in previous:
                        if deleted and id_ in deleted:
                            to_delete.append(id_)
                        elif removed and id_ in removed:
                            to_remove.append(id_)
                        elif field._type == 'one2many':
                            to_delete.append(id_)
                        else:
                            to_remove.append(id_)
                    if to_delete:
                        value.append(('delete', to_delete))
                    if to_remove:
                        value.append(('remove', to_remove))
                if to_add:
                    value.append(('add', to_add))
                if to_create:
                    value.append(('create', to_create))
                if to_write:
                    value.extend(to_write)
            values[fname] = value
        try:
            values.update(self.compute_fields(values.keys()))
        except AttributeError:
            if self.id is not None and self.id >= 0:
                raise
        return values

    @dualmethod
    def save(cls, records):
        while records:
            latter = []
            values = {}
            save_values = {}
            to_create = []
            to_write = []
            first = next(iter(records))
            transaction = first._transaction
            user = first._user
            context = first._context
            for record in records:
                assert isinstance(record, cls), (record, cls)
                if (record._transaction != transaction
                        or user != record._user
                        or context != record._context):
                    latter.append(record)
                    continue
                while True:
                    try:
                        save_values[record] = record._save_values()
                        break
                    except _UnsavedRecordError as e:
                        warnings.warn(
                            f"Using an unsaved relation record: {e.record}")
                        e.record.save()
                values[record] = record._values
                record._values = None
                if record.id is None or record.id < 0:
                    to_create.append(record)
                elif save_values[record]:
                    to_write.append(record)
            try:
                with Transaction().set_current_transaction(transaction), \
                        transaction.set_user(user), \
                        transaction.reset_context(), \
                        transaction.set_context(context), \
                        without_check_access():
                    if to_create:
                        news = cls.create([save_values[r] for r in to_create])
                        new_ids = []
                        new_local_cache = local_cache(cls, transaction)
                        for record, new in zip(to_create, news):
                            record._ids.remove(record.id)
                            record._id = new.id
                            # Group all records that are alone
                            if not record._ids:
                                record._ids = new_ids
                                record._local_cache = new_local_cache
                            record._ids.append(record.id)
                    if to_write:
                        cls.write(*sum(
                                (([r], save_values[r]) for r in to_write), ()))
            except Exception:
                for record in to_create + to_write:
                    record._values = values[record]
                raise
            for record in to_create + to_write:
                record._init_values = None
                record._deleted = None
                record._removed = None
            records = latter


class EvalEnvironment(dict):
    __slots__ = ('_record', '_model')

    def __init__(self, record, Model):
        super().__init__()
        self._record = record
        self._model = Model

    def __getitem__(self, item):
        if item.startswith('_parent_'):
            field = item[8:]
            model_name = self._model._fields[field].model_name
            ParentModel = Pool().get(model_name)
            return EvalEnvironment(getattr(self._record, field), ParentModel)
        if item in self._model._fields:
            value = getattr(self._record, item)
            if isinstance(value, Model):
                if self._model._fields[item]._type == 'reference':
                    return str(value)
                return value.id
            elif (isinstance(value, (list, tuple))
                    and value and isinstance(value[0], Model)):
                return [r.id for r in value]
            else:
                return value
        return super().__getitem__(item)

    def __getattr__(self, item):
        try:
            return self.__getitem__(item)
        except KeyError as exception:
            raise AttributeError(*exception.args)

    def get(self, item, default=None):
        try:
            return self.__getitem__(item)
        except Exception:
            pass
        return super().get(item, default)

    def __bool__(self):
        return bool(self._record)


def _record_eval_pyson(record, source, encoded=False):
    transaction = Transaction()
    if not encoded:
        pyson = _pyson_encoder.encode(source)
    else:
        pyson = source
    env = EvalEnvironment(record, record.__class__)
    env['context'] = transaction.context
    env['active_model'] = record.__class__.__name__
    env['active_id'] = record.id
    return PYSONDecoder(env).decode(pyson)


_pyson_encoder = PYSONEncoder()
