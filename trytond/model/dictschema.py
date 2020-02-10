# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
import json
from collections import OrderedDict

from trytond.cache import Cache
from trytond.config import config
from trytond.i18n import gettext, lazy_gettext
from trytond.model import fields
from trytond.model.exceptions import ValidationError
from trytond.pyson import Eval, PYSONDecoder
from trytond.rpc import RPC
from trytond.tools import slugify
from trytond.transaction import Transaction
from trytond.pool import Pool


class DomainError(ValidationError):
    pass


class SelectionError(ValidationError):
    pass


class DictSchemaMixin(object):
    __slots__ = ()
    _rec_name = 'string'
    name = fields.Char(lazy_gettext('ir.msg_dict_schema_name'), required=True)
    string = fields.Char(
        lazy_gettext('ir.msg_dict_schema_string'),
        translate=True, required=True)
    help = fields.Text(
        lazy_gettext('ir.msg_dict_schema_help'),
        translate=True)
    type_ = fields.Selection([
            ('boolean', lazy_gettext('ir.msg_dict_schema_boolean')),
            ('integer', lazy_gettext('ir.msg_dict_schema_integer')),
            ('char', lazy_gettext('ir.msg_dict_schema_char')),
            ('float', lazy_gettext('ir.msg_dict_schema_float')),
            ('numeric', lazy_gettext('ir.msg_dict_schema_numeric')),
            ('date', lazy_gettext('ir.msg_dict_schema_date')),
            ('datetime', lazy_gettext('ir.msg_dict_schema_datetime')),
            ('selection', lazy_gettext('ir.msg_dict_schema_selection')),
            ('multiselection',
                lazy_gettext('ir.msg_dict_schema_multiselection')),
            ], lazy_gettext('ir.msg_dict_schema_type'), required=True)
    digits = fields.Integer(
        lazy_gettext('ir.msg_dict_schema_digits'),
        states={
            'invisible': ~Eval('type_').in_(['float', 'numeric']),
            }, depends=['type_'])
    domain = fields.Char(lazy_gettext('ir.msg_dict_schema_domain'))
    selection = fields.Text(
        lazy_gettext('ir.msg_dict_schema_selection'),
        states={
            'invisible': ~Eval('type_').in_(['selection', 'multiselection']),
            }, translate=True, depends=['type_'],
        help=lazy_gettext('ir.msg_dict_schema_selection_help'))
    selection_sorted = fields.Boolean(
        lazy_gettext('ir.msg_dict_schema_selection_sorted'),
        states={
            'invisible': ~Eval('type_').in_(['selection', 'multiselection']),
            }, depends=['type_'],
        help=lazy_gettext('ir.msg_dict_schema_selection_sorted_help'))
    selection_json = fields.Function(fields.Char(
            lazy_gettext('ir.msg_dict_schema_selection_json'),
            states={
                'invisible': ~Eval('type_').in_(
                    ['selection', 'multiselection']),
                },
            depends=['type_']), 'get_selection_json')
    _relation_fields_cache = Cache('_dict_schema_mixin.get_relation_fields')

    @classmethod
    def __setup__(cls):
        super(DictSchemaMixin, cls).__setup__()
        cls.__rpc__.update({
                'get_keys': RPC(instantiate=0),
                })

    @staticmethod
    def default_digits():
        return 2

    @staticmethod
    def default_selection_sorted():
        return True

    @fields.depends('name', 'string')
    def on_change_string(self):
        if not self.name and self.string:
            self.name = slugify(self.string.lower(), hyphenate='_')

    @classmethod
    def validate(cls, schemas):
        super(DictSchemaMixin, cls).validate(schemas)
        cls.check_domain(schemas)
        cls.check_selection(schemas)

    @classmethod
    def check_domain(cls, schemas):
        for schema in schemas:
            if not schema.domain:
                continue
            try:
                value = PYSONDecoder().decode(schema.domain)
            except Exception:
                raise DomainError(
                    gettext('ir.msg_dict_schema_invalid_domain',
                        schema=schema.rec_name))
            if not isinstance(value, list):
                raise DomainError(
                    gettext('ir.msg_dict_schema_invalid_domain',
                        schema=schema.rec_name))

    @classmethod
    def check_selection(cls, schemas):
        for schema in schemas:
            if schema.type_ not in {'selection', 'multiselection'}:
                continue
            try:
                dict(json.loads(schema.get_selection_json()))
            except Exception:
                raise SelectionError(
                    gettext('ir.msg_dict_schema_invalid_selection',
                        schema=schema.rec_name))

    def get_selection_json(self, name=None):
        db_selection = self.selection or ''
        selection = [[w.strip() for w in v.split(':', 1)]
            for v in db_selection.splitlines() if v]
        return json.dumps(selection, separators=(',', ':'))

    @classmethod
    def get_keys(cls, records):
        pool = Pool()
        Config = pool.get('ir.configuration')
        keys = []
        for record in records:
            new_key = {
                'id': record.id,
                'name': record.name,
                'string': record.string,
                'help': record.help,
                'type': record.type_,
                'domain': record.domain,
                'sequence': getattr(record, 'sequence', record.name),
                }
            if record.type_ in {'selection', 'multiselection'}:
                with Transaction().set_context(language=Config.get_language()):
                    english_key = cls(record.id)
                    selection = OrderedDict(json.loads(
                            english_key.selection_json))
                selection.update(dict(json.loads(record.selection_json)))
                new_key['selection'] = list(selection.items())
                new_key['sort'] = record.selection_sorted
            elif record.type_ in ('float', 'numeric'):
                new_key['digits'] = (16, record.digits)
            keys.append(new_key)
        return keys

    @classmethod
    def get_relation_fields(cls):
        if not config.get('dict', cls.__name__, default=True):
            return {}
        fields = cls._relation_fields_cache.get(cls.__name__)
        if fields is not None:
            return fields
        keys = cls.get_keys(cls.search([]))
        fields = {k['name']: k for k in keys}
        cls._relation_fields_cache.set(cls.__name__, fields)
        return fields

    @classmethod
    def create(cls, vlist):
        records = super().create(vlist)
        cls._relation_fields_cache.clear()
        return records

    @classmethod
    def write(cls, *args):
        super().write(*args)
        cls._relation_fields_cache.clear()

    @classmethod
    def delete(cls, records):
        super().delete(records)
        cls._relation_fields_cache.clear()
