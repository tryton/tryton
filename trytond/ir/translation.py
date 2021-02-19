# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import xml.dom.minidom
from difflib import SequenceMatcher
from collections import defaultdict
from io import BytesIO
from lxml import etree

import polib
from sql import Column, Null, Literal
from sql.functions import Substring, Position
from sql.conditionals import Case
from sql.aggregate import Max

from genshi.filters.i18n import extract as genshi_extract
from relatorio.reporting import MIMETemplateLoader
from relatorio.templates.opendocument import get_zip_file

from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.tools.string_ import LazyString
from ..model import ModelView, ModelSQL, fields
from ..wizard import Wizard, StateView, StateTransition, StateAction, \
    Button
from ..tools import file_open, grouped_slice, cursor_dict
from ..pyson import PYSONEncoder, Eval
from ..transaction import Transaction
from ..pool import Pool
from ..cache import Cache
from ..config import config

from trytond.ir.lang import get_parent_language as get_parent

__all__ = ['Translation',
    'TranslationSetStart', 'TranslationSetSucceed', 'TranslationSet',
    'TranslationCleanStart', 'TranslationCleanSucceed', 'TranslationClean',
    'TranslationUpdateStart', 'TranslationUpdate',
    'TranslationExportStart', 'TranslationExportResult', 'TranslationExport',
    'TranslationReport',
    ]

TRANSLATION_TYPE = [
    ('field', 'Field'),
    ('model', 'Model'),
    ('report', 'Report'),
    ('selection', 'Selection'),
    ('view', 'View'),
    ('wizard_button', 'Wizard Button'),
    ('help', 'Help'),
]


class OverriddenError(UserError):
    pass


class TrytonPOFile(polib.POFile):

    def sort(self):
        return super(TrytonPOFile, self).sort(
            key=lambda x: (x.msgctxt, x.msgid))


class Translation(ModelSQL, ModelView):
    "Translation"
    __name__ = "ir.translation"

    name = fields.Char('Field Name', required=True)
    res_id = fields.Integer('Resource ID', select=True, required=True)
    lang = fields.Selection('get_language', string='Language')
    type = fields.Selection(TRANSLATION_TYPE, string='Type',
       required=True)
    src = fields.Text('Source')
    value = fields.Text('Translation Value')
    module = fields.Char('Module', readonly=True)
    fuzzy = fields.Boolean('Fuzzy')
    model = fields.Function(fields.Char('Model'), 'get_model',
            searcher='search_model')
    overriding_module = fields.Char('Overriding Module', readonly=True)
    _translation_cache = Cache('ir.translation', size_limit=10240,
        context=False)
    _get_language_cache = Cache('ir.translation.get_language')

    @classmethod
    def __register__(cls, module_name):
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        ir_translation = cls.__table__()
        table = cls.__table_handler__(module_name)

        # Migration from 5.0: remove src_md5
        if table.column_exist('src_md5'):
            table.drop_constraint('translation_md5_uniq')
            table.drop_column('src_md5')

        super(Translation, cls).__register__(module_name)

        # Migration from 3.8: rename odt type in report
        cursor.execute(*ir_translation.update(
                [ir_translation.type],
                ['report'],
                where=ir_translation.type == 'odt'))

        table = cls.__table_handler__(module_name)
        table.index_action(['lang', 'type', 'name'], 'add')

    @classmethod
    def register_model(cls, model, module_name):
        cursor = Transaction().connection.cursor()
        ir_translation = cls.__table__()

        if not model.__doc__:
            return

        name = model.__name__ + ',name'
        src = model._get_name()
        if not src:
            return
        cursor.execute(*ir_translation.select(ir_translation.id,
                where=(ir_translation.lang == 'en')
                & (ir_translation.type == 'model')
                & (ir_translation.name == name)
                # Keep searching on all values for migration
                & ((ir_translation.res_id == -1)
                    | (ir_translation.res_id == Null)
                    | (ir_translation.res_id == 0))))
        trans_id = None
        if cursor.rowcount == -1 or cursor.rowcount is None:
            data = cursor.fetchone()
            if data:
                trans_id, = data
        elif cursor.rowcount != 0:
            trans_id, = cursor.fetchone()
        if trans_id is None:
            cursor.execute(*ir_translation.insert(
                    [Column(ir_translation, c)
                        for c in ('name', 'lang', 'type', 'src',
                            'value', 'module', 'fuzzy', 'res_id')],
                    [[name, 'en', 'model', src,
                            '', module_name, False, -1]]))
        else:
            cursor.execute(*ir_translation.update(
                    [ir_translation.src],
                    [src],
                    where=ir_translation.id == trans_id))

    @classmethod
    def register_fields(cls, model, module_name):
        cursor = Transaction().connection.cursor()
        ir_translation = cls.__table__()

        # Prefetch field translations
        translations = dict(
            field=defaultdict(dict),
            help=defaultdict(dict),
            selection=defaultdict(dict))
        if model._fields:
            names = ['%s,%s' % (model.__name__, f) for f in model._fields]
            cursor.execute(*ir_translation.select(ir_translation.id,
                    ir_translation.name, ir_translation.src,
                    ir_translation.type,
                    where=((ir_translation.lang == 'en')
                        & ir_translation.type.in_(
                            ('field', 'help', 'selection'))
                        & ir_translation.name.in_(names))))
            for trans in cursor_dict(cursor):
                sources = translations[trans['type']][trans['name']]
                sources[trans['src']] = trans

        columns = [ir_translation.name, ir_translation.lang,
            ir_translation.type, ir_translation.src, ir_translation.value,
            ir_translation.module, ir_translation.fuzzy, ir_translation.res_id]

        def insert(field, type, name, string):
            for val in string:
                if not val or val in translations[type][name]:
                    continue
                if isinstance(val, LazyString):
                    continue
                cursor.execute(
                    *ir_translation.insert(columns,
                        [[name, 'en', type, val, '', module_name, False, -1]]))

        for field_name, field in model._fields.items():
            name = model.__name__ + ',' + field_name
            insert(field, 'field', name, field.string)
            insert(field, 'help', name, field.help)
            if (hasattr(field, 'selection')
                    and isinstance(field.selection, (tuple, list))
                    and getattr(field, 'translate_selection', True)):
                selection = [s for _, s in field.selection]
                insert(field, 'selection', name, selection)

    @classmethod
    def register_wizard(cls, wizard, module_name):
        cursor = Transaction().connection.cursor()
        ir_translation = cls.__table__()

        # Prefetch button translations
        cursor.execute(*ir_translation.select(
                ir_translation.id, ir_translation.name, ir_translation.src,
                where=((ir_translation.lang == 'en')
                    & (ir_translation.type == 'wizard_button')
                    & (ir_translation.name.like(wizard.__name__ + ',%')))))
        trans_buttons = {t['name']: t for t in cursor_dict(cursor)}

        def update_insert_button(state_name, button):
            if not button.string:
                return
            trans_name = '%s,%s,%s' % (
                wizard.__name__, state_name, button.state)
            if trans_name not in trans_buttons:
                cursor.execute(*ir_translation.insert(
                        [ir_translation.name, ir_translation.lang,
                            ir_translation.type, ir_translation.src,
                            ir_translation.value, ir_translation.module,
                            ir_translation.fuzzy, ir_translation.res_id],
                        [[
                                trans_name, 'en',
                                'wizard_button', button.string,
                                '', module_name,
                                False, -1]]))
            elif trans_buttons[trans_name] != button.string:
                cursor.execute(*ir_translation.update(
                        [ir_translation.src],
                        [button.string],
                        where=ir_translation.id
                        == trans_buttons[trans_name]['id']))

        for state_name, state in wizard.states.items():
            if not isinstance(state, StateView):
                continue
            for button in state.buttons:
                update_insert_button(state_name, button)

    @staticmethod
    def default_fuzzy():
        return False

    @staticmethod
    def default_res_id():
        return -1

    def get_model(self, name):
        return self.name.split(',')[0]

    @classmethod
    def search_rec_name(cls, name, clause):
        clause = tuple(clause)
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('src',) + clause[1:],
            ('value',) + clause[1:],
            (cls._rec_name,) + clause[1:],
            ]

    @classmethod
    def search_model(cls, name, clause):
        table = cls.__table__()
        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]
        return [('id', 'in', table.select(table.id,
                    where=Operator(Substring(table.name, 1,
                            Case((
                                    Position(',', table.name) > 0,
                                    Position(',', table.name) - 1),
                                else_=0)), value)))]

    @classmethod
    def get_language(cls):
        result = cls._get_language_cache.get(None)
        if result is not None:
            return result
        pool = Pool()
        Lang = pool.get('ir.lang')
        langs = Lang.search([])
        result = [(lang.code, lang.name) for lang in langs]
        cls._get_language_cache.set(None, result)
        return result

    @classmethod
    def view_attributes(cls):
        return [('/form//field[@name="value"]', 'spell', Eval('lang'))]

    @classmethod
    def get_ids(cls, name, ttype, lang, ids, cached_after=None):
        "Return translation for each id"
        pool = Pool()
        ModelFields = pool.get('ir.model.field')
        Model = pool.get('ir.model')
        context = Transaction().context
        fuzzy_translation = context.get('fuzzy_translation', False)

        translations, to_fetch = {}, []
        name = str(name)
        ttype = str(ttype)
        lang = str(lang)
        if name.split(',')[0] in ('ir.model.field', 'ir.model'):
            field_name = name.split(',')[1]
            with Transaction().set_context(_check_access=False):
                if name.split(',')[0] == 'ir.model.field':
                    if field_name == 'field_description':
                        ttype = 'field'
                    else:
                        ttype = 'help'
                    records = ModelFields.browse(ids)
                else:
                    ttype = 'model'
                    records = Model.browse(ids)

            trans_args = []
            for record in records:
                if ttype in ('field', 'help'):
                    name = record.model.model + ',' + record.name
                else:
                    name = record.model + ',' + field_name
                trans_args.append((name, ttype, lang, None))
            cls.get_sources(trans_args)

            for record in records:
                if ttype in ('field', 'help'):
                    name = record.model.model + ',' + record.name
                else:
                    name = record.model + ',' + field_name
                translations[record.id] = cls.get_source(name, ttype, lang)
            return translations

        # Don't use cache for fuzzy translation
        if (not fuzzy_translation
                and (not cached_after
                    or not cls._translation_cache.sync_since(cached_after))):
            for obj_id in ids:
                trans = cls._translation_cache.get((name, ttype, lang, obj_id),
                    -1)
                if trans != -1:
                    translations[obj_id] = trans
                else:
                    to_fetch.append(obj_id)
        else:
            to_fetch = ids

        if to_fetch:
            # Get parent translations
            parent_lang = get_parent(lang)
            if parent_lang:
                translations.update(
                    cls.get_ids(name, ttype, parent_lang, to_fetch))

            if fuzzy_translation:
                fuzzy_clause = []
            else:
                fuzzy_clause = [('fuzzy', '=', False)]
            for sub_to_fetch in grouped_slice(to_fetch):
                for translation in cls.search([
                            ('lang', '=', lang),
                            ('type', '=', ttype),
                            ('name', '=', name),
                            ('value', '!=', ''),
                            ('value', '!=', None),
                            ('res_id', 'in', list(sub_to_fetch)),
                            ] + fuzzy_clause):
                    translations[translation.res_id] = translation.value
            # Don't store fuzzy translation in cache
            if not fuzzy_translation:
                for res_id in to_fetch:
                    value = translations.setdefault(res_id)
                    cls._translation_cache.set(
                        (name, ttype, lang, res_id), value)
        return translations

    @classmethod
    def set_ids(cls, name, ttype, lang, ids, values):
        "Set translation for each id"
        pool = Pool()
        ModelFields = pool.get('ir.model.field')
        Model = pool.get('ir.model')
        Config = pool.get('ir.configuration')
        transaction = Transaction()
        in_max = transaction.database.IN_MAX

        if len(ids) > in_max:
            for i in range(0, len(ids), in_max):
                sub_ids = ids[i:i + in_max]
                sub_values = values[i:i + in_max]
                cls.set_ids(name, ttype, lang, sub_ids, sub_values)
            return

        model_name, field_name = name.split(',')
        if model_name in ('ir.model.field', 'ir.model'):
            if model_name == 'ir.model.field':
                if field_name == 'field_description':
                    ttype = 'field'
                else:
                    ttype = 'help'
                with Transaction().set_context(language='en'):
                    records = ModelFields.browse(ids)
            else:
                ttype = 'model'
                with Transaction().set_context(language='en'):
                    records = Model.browse(ids)

            def get_name(record):
                if ttype in ('field', 'help'):
                    return record.model.model + ',' + record.name
                else:
                    return record.model + ',' + field_name

            with Transaction().set_context(_check_access=False):
                name2translations = defaultdict(list)
                for translation in cls.search([
                            ('lang', '=', lang),
                            ('type', '=', ttype),
                            ('name', 'in', [get_name(r) for r in records]),
                            ]):
                    name2translations[translation.name].append(translation)

                to_save = []
                for record, value in zip(records, values):
                    translations = name2translations.get(get_name(record))
                    if lang == 'en':
                        src = value
                    else:
                        src = getattr(record, field_name)
                    if not translations:
                        if not src and not value:
                            continue
                        translation = cls()
                        translation.name = name
                        translation.lang = lang
                        translation.type = ttype
                        translations.append(translation)
                    for translation in translations:
                        translation.src = src
                        translation.value = value
                        translation.fuzzy = False
                        to_save.append(translation)
                cls.save(to_save)
            return

        Model = pool.get(model_name)
        with Transaction().set_context(language=Config.get_language()):
            records = Model.browse(ids)

        id2translations = defaultdict(list)
        other_translations = defaultdict(list)
        with Transaction().set_context(_check_access=False):
            for translation in cls.search([
                        ('lang', '=', lang),
                        ('type', '=', ttype),
                        ('name', '=', name),
                        ('res_id', 'in', ids),
                        ]):
                id2translations[translation.res_id].append(translation)

            if (lang == Config.get_language()
                    and Transaction().context.get('fuzzy_translation', True)):
                for translation in cls.search([
                            ('lang', '!=', lang),
                            ('type', '=', ttype),
                            ('name', '=', name),
                            ('res_id', 'in', ids),
                            ]):
                    other_translations[translation.res_id].append(translation)

            to_save = []
            for record, value in zip(records, values):
                translations = id2translations[record.id]
                if lang == Config.get_language():
                    src = value
                else:
                    src = getattr(record, field_name)
                if not translations:
                    if not src and not value:
                        continue
                    translation = cls()
                    translation.name = name
                    translation.lang = lang
                    translation.type = ttype
                    translation.res_id = record.id
                    translations.append(translation)
                else:
                    other_langs = other_translations[record.id]
                    if other_langs:
                        for other_lang in other_langs:
                            other_lang.src = src
                            other_lang.fuzzy = True
                            to_save.append(other_lang)
                for translation in translations:
                    translation.value = value
                    translation.src = src
                    translation.fuzzy = False
                    to_save.append(translation)
            cls.save(to_save)

    @classmethod
    def delete_ids(cls, model, ttype, ids):
        "Delete translation for each id"
        translations = []
        with Transaction().set_context(_check_access=False):
            for sub_ids in grouped_slice(ids):
                translations += cls.search([
                        ('type', '=', ttype),
                        ('name', 'like', model + ',%'),
                        ('res_id', 'in', list(sub_ids)),
                        ])
            cls.delete(translations)

    @classmethod
    def get_source(cls, name, ttype, lang, source=None):
        "Return translation for source"
        args = (name, ttype, lang, source)
        result = cls.get_sources([args])
        return result[args]

    @classmethod
    def get_sources(cls, args):
        '''
        Take a list of (name, ttype, lang, source).
        Add the translations to the cache.
        Return a dict with the translations.
        '''
        res = {}
        parent_args = []
        parent_langs = []
        clauses = []
        transaction = Transaction()
        if len(args) > transaction.database.IN_MAX:
            for sub_args in grouped_slice(args):
                res.update(cls.get_sources(list(sub_args)))
            return res

        to_cache = []
        for name, ttype, lang, source in args:
            name = str(name)
            ttype = str(ttype)
            lang = str(lang)
            if source is not None:
                source = str(source)
            trans = cls._translation_cache.get((name, ttype, lang, source), -1)
            if trans != -1:
                res[(name, ttype, lang, source)] = trans
            else:
                to_cache.append((name, ttype, lang, source))
                parent_lang = get_parent(lang)
                if parent_lang:
                    parent_args.append((name, ttype, parent_lang, source))
                    parent_langs.append(lang)
                res[(name, ttype, lang, source)] = None
                clause = [
                    ('lang', '=', lang),
                    ('type', '=', ttype),
                    ('name', '=', name),
                    ('value', '!=', ''),
                    ('value', '!=', None),
                    ('fuzzy', '=', False),
                    ('res_id', '=', -1),
                    ]
                if source is not None:
                    clause.append(('src', '=', source))
                clauses.append(clause)

        # Get parent transactions
        if parent_args:
            parent_src = cls.get_sources(parent_args)
            for (name, ttype, parent_lang, source), lang in zip(
                    parent_args, parent_langs):
                res[(name, ttype, lang, source)] = parent_src[
                    (name, ttype, parent_lang, source)]

        in_max = transaction.database.IN_MAX // 7
        for sub_clause in grouped_slice(clauses, in_max):
            for translation in cls.search(['OR'] + list(sub_clause)):
                key = (translation.name, translation.type,
                    translation.lang, translation.src)
                if key not in args:
                    key = key[:-1] + (None,)
                res[key] = translation.value
        for key in to_cache:
            cls._translation_cache.set(key, res[key])
        return res

    @classmethod
    def delete(cls, translations):
        pool = Pool()
        Message = pool.get('ir.message')
        Model = pool.get('ir.model')
        ModelField = pool.get('ir.model.field')
        Message._message_cache.clear()
        Model._get_name_cache.clear()
        ModelField._get_name_cache.clear()
        cls._translation_cache.clear()
        ModelView._fields_view_get_cache.clear()
        return super(Translation, cls).delete(translations)

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Message = pool.get('ir.message')
        Model = pool.get('ir.model')
        ModelField = pool.get('ir.model.field')
        Message._message_cache.clear()
        Model._get_name_cache.clear()
        ModelField._get_name_cache.clear()
        cls._translation_cache.clear()
        ModelView._fields_view_get_cache.clear()
        vlist = [x.copy() for x in vlist]

        for vals in vlist:
            if not vals.get('module'):
                if Transaction().context.get('module'):
                    vals['module'] = Transaction().context['module']
        return super(Translation, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Message = pool.get('ir.message')
        Model = pool.get('ir.model')
        ModelField = pool.get('ir.model.field')
        Message._message_cache.clear()
        Model._get_name_cache.clear()
        ModelField._get_name_cache.clear()
        cls._translation_cache.clear()
        ModelView._fields_view_get_cache.clear()
        return super(Translation, cls).write(*args)

    @classmethod
    def extra_model_data(cls, model_data):
        "Yield extra model linked to the model data"
        if model_data.model in (
                'ir.action.report',
                'ir.action.act_window',
                'ir.action.wizard',
                'ir.action.url',
                ):
            yield 'ir.action'

    @property
    def unique_key(self):
        if self.type in {
                'report', 'view', 'wizard_button', 'selection'}:
            return (self.name, self.res_id, self.type, self.src)
        elif self.type in ('field', 'model', 'help'):
            return (self.name, self.res_id, self.type)

    @classmethod
    def from_poentry(cls, entry):
        'Returns a translation instance for a entry of pofile and its res_id'
        ttype, name, res_id = entry.msgctxt.split(':')
        src = entry.msgid
        value = entry.msgstr
        fuzzy = 'fuzzy' in entry.flags

        translation = cls(name=name, type=ttype, src=src, fuzzy=fuzzy,
            value=value)
        return translation, res_id

    @classmethod
    def translation_import(cls, lang, module, po_path):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        if isinstance(po_path, str):
            po_path = [po_path]
        models_data = ModelData.search([
                ('module', '=', module),
                ])
        fs_id2prop = {}
        for model_data in models_data:
            fs_id2prop.setdefault(model_data.model, {})
            fs_id2prop[model_data.model][model_data.fs_id] = \
                (model_data.db_id, model_data.noupdate)
            for extra_model in cls.extra_model_data(model_data):
                fs_id2prop.setdefault(extra_model, {})
                fs_id2prop[extra_model][model_data.fs_id] = \
                    (model_data.db_id, model_data.noupdate)

        translations = set()
        to_save = []

        id2translation = {}
        key2ids = {}
        module_translations = cls.search([
                ('lang', '=', lang),
                ('module', '=', module),
                ], order=[])
        for translation in module_translations:
            # Migration from 5.0: ignore error type
            if translation.type == 'error':
                continue
            key = translation.unique_key
            if not key:
                raise ValueError('Unknow translation type: %s' %
                    translation.type)
            key2ids.setdefault(key, []).append(translation.id)
            if len(module_translations) <= config.getint('cache', 'record'):
                id2translation[translation.id] = translation

        def override_translation(ressource_id, new_translation):
            res_id_module, res_id = ressource_id.split('.')
            if res_id:
                model_data, = ModelData.search([
                        ('module', '=', res_id_module),
                        ('fs_id', '=', res_id),
                        ])
                res_id = model_data.db_id
            else:
                res_id = -1
            with Transaction().set_context(module=res_id_module):
                domain = [
                    ('name', '=', new_translation.name),
                    ('res_id', '=', res_id),
                    ('lang', '=', new_translation.lang),
                    ('type', '=', new_translation.type),
                    ('module', '=', res_id_module),
                    ]
                if new_translation.type in {
                        'report', 'view', 'wizard_button', 'selection'}:
                    domain.append(('src', '=', new_translation.src))
                translation, = cls.search(domain)
                if translation.value != new_translation.value:
                    translation.value = new_translation.value
                    translation.overriding_module = module
                    translation.fuzzy = new_translation.fuzzy
                    return translation

        # Make a first loop to retreive translation ids in the right order to
        # get better read locality and a full usage of the cache.
        translation_ids = []
        if len(module_translations) <= config.getint('cache', 'record'):
            processes = (True,)
        else:
            processes = (False, True)
        for processing in processes:
            if (processing
                    and len(module_translations) > config.getint('cache',
                        'record')):
                id2translation = dict((t.id, t)
                    for t in cls.browse(translation_ids))
            for pofile in po_path:
                for entry in polib.pofile(pofile):
                    if entry.obsolete:
                        continue
                    translation, res_id = cls.from_poentry(entry)
                    # Migration from 5.0: ignore error type
                    if translation.type == 'error':
                        continue
                    translation.lang = lang
                    translation.module = module
                    noupdate = False

                    if '.' in res_id:
                        to_save.append(override_translation(res_id,
                                translation))
                        continue

                    model = translation.name.split(',')[0]
                    if (model in fs_id2prop
                            and res_id in fs_id2prop[model]):
                        res_id, noupdate = fs_id2prop[model][res_id]

                    if res_id:
                        try:
                            res_id = int(res_id)
                        except ValueError:
                            res_id = None
                    if not res_id:
                        res_id = -1

                    translation.res_id = res_id
                    key = translation.unique_key
                    if not key:
                        raise ValueError('Unknow translation type: %s' %
                            translation.type)
                    ids = key2ids.get(key, [])

                    if not processing:
                        translation_ids.extend(ids)
                        continue

                    if not ids:
                        to_save.append(translation)
                    else:
                        for translation_id in ids:
                            old_translation = id2translation[translation_id]
                            if not noupdate:
                                old_translation.value = translation.value
                                old_translation.fuzzy = translation.fuzzy
                                to_save.append(old_translation)
                            else:
                                translations.add(old_translation)
        cls.save([_f for _f in to_save if _f])
        translations |= set(to_save)

        if translations:
            all_translations = set(cls.search([
                        ('module', '=', module),
                        ('lang', '=', lang),
                        ]))
            translations_to_delete = all_translations - translations
            cls.delete(list(translations_to_delete))
        return len(translations)

    @classmethod
    def translation_export(cls, lang, module):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Config = pool.get('ir.configuration')

        models_data = ModelData.search([
                ('module', '=', module),
                ])
        db_id2fs_id = {}
        for model_data in models_data:
            db_id2fs_id.setdefault(model_data.model, {})
            db_id2fs_id[model_data.model][model_data.db_id] = model_data.fs_id
            for extra_model in cls.extra_model_data(model_data):
                db_id2fs_id.setdefault(extra_model, {})
                db_id2fs_id[extra_model][model_data.db_id] = model_data.fs_id

        pofile = TrytonPOFile(wrapwidth=78)
        pofile.metadata = {
            'Content-Type': 'text/plain; charset=utf-8',
            }

        with Transaction().set_context(language=Config.get_language()):
            translations = cls.search([
                ('lang', '=', lang),
                ('module', '=', module),
                ], order=[])
        for translation in translations:
            if (translation.overriding_module
                    and translation.overriding_module != module):
                raise OverriddenError(
                    gettext('ir.msg_translation_overridden',
                        name=translation.name,
                        overriding_module=translation.overriding_module))
            flags = [] if not translation.fuzzy else ['fuzzy']
            trans_ctxt = '%(type)s:%(name)s:' % {
                'type': translation.type,
                'name': translation.name,
                }
            res_id = translation.res_id
            if res_id >= 0:
                model, _ = translation.name.split(',')
                if model in db_id2fs_id:
                    res_id = db_id2fs_id[model].get(res_id)
                else:
                    continue
                trans_ctxt += '%s' % res_id
            entry = polib.POEntry(msgid=(translation.src or ''),
                msgstr=(translation.value or ''), msgctxt=trans_ctxt,
                flags=flags)
            if entry.msgid or entry.msgstr:
                pofile.append(entry)

        if pofile:
            pofile.sort()
            return str(pofile).encode('utf-8')
        else:
            return


class TranslationSetStart(ModelView):
    "Set Translation"
    __name__ = 'ir.translation.set.start'


class TranslationSetSucceed(ModelView):
    "Set Translation"
    __name__ = 'ir.translation.set.succeed'


class TranslationSet(Wizard):
    "Set Translation"
    __name__ = "ir.translation.set"

    start = StateView('ir.translation.set.start',
        'ir.translation_set_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Set', 'set_', 'tryton-ok', default=True),
            ])
    set_ = StateTransition()
    succeed = StateView('ir.translation.set.succeed',
        'ir.translation_set_succeed_view_form', [
            Button('OK', 'end', 'tryton-ok', default=True),
            ])

    def extract_report_opendocument(self, content):
        def extract(node):
            if node.nodeType in {node.CDATA_SECTION_NODE, node.TEXT_NODE}:
                if (node.parentNode
                        and node.parentNode.tagName in {
                            'text:placeholder',
                            'text:page-number',
                            'text:page-count',
                            }):
                    return
                if node.nodeValue:
                    txt = node.nodeValue.strip()
                    if txt:
                        yield txt

            for child in [x for x in node.childNodes]:
                for string in extract(child):
                    yield string

        zip_ = get_zip_file(BytesIO(content))
        for content_xml in [
                zip_.read('content.xml'),
                zip_.read('styles.xml'),
                ]:
            document = xml.dom.minidom.parseString(content_xml)
            for string in extract(document.documentElement):
                yield string

    extract_report_odt = extract_report_opendocument
    extract_report_odp = extract_report_opendocument
    extract_report_ods = extract_report_opendocument
    extract_report_odg = extract_report_opendocument

    def extract_report_genshi(template_class):
        def method(self, content,
                keywords=None, comment_tags=None, **options):
            options['template_class'] = template_class
            content = BytesIO(content)
            if keywords is None:
                keywords = []
            if comment_tags is None:
                comment_tags = []

            for _, _, string, _ in genshi_extract(
                    content, keywords, comment_tags, options):
                if string:
                    yield string
        if not template_class:
            raise ValueError('a template class is required')
        return method
    factories = MIMETemplateLoader().factories
    extract_report_txt = extract_report_genshi(factories['text'])
    extract_report_xml = extract_report_genshi(
        factories.get('markup', factories.get('xml')))
    extract_report_html = extract_report_genshi(
        factories.get('markup', factories.get('xml')))
    extract_report_xhtml = extract_report_genshi(
        factories.get('markup', factories.get('xml')))
    del factories

    def set_report(self):
        pool = Pool()
        Report = pool.get('ir.action.report')
        Translation = pool.get('ir.translation')
        context = Transaction().context

        if context.get('active_model') == Report.__name__:
            reports = Report.browse(context.get('active_ids', []))
        elif context.get('active_model', 'ir.ui.menu') == 'ir.ui.menu':
            with Transaction().set_context(active_test=False):
                reports = Report.search([('translatable', '=', True)])
        else:
            return

        cursor = Transaction().connection.cursor()
        translation = Translation.__table__()
        for report in reports:
            content = None
            if report.report:
                with file_open(report.report.replace('/', os.sep),
                        mode='rb') as fp:
                    content = fp.read()
            for content, module in [
                    (report.report_content_custom, None),
                    (content, report.module)]:
                if not content:
                    continue

                cursor.execute(*translation.select(
                        translation.id, translation.name, translation.src,
                        where=(translation.lang == 'en')
                        & (translation.type == 'report')
                        & (translation.name == report.report_name)
                        & (translation.module == module)))
                trans_reports = {t['src']: t for t in cursor_dict(cursor)}

                strings = set()
                func_name = 'extract_report_%s' % report.template_extension
                strings.update(getattr(self, func_name)(content))

                for string in strings:
                    done = False
                    if string in trans_reports:
                        del trans_reports[string]
                        continue
                    for string_trans in trans_reports:
                        if string_trans in strings:
                            continue
                        seqmatch = SequenceMatcher(lambda x: x == ' ',
                                string, string_trans)
                        if seqmatch.ratio() == 1.0:
                            del trans_reports[report.report_name][string_trans]
                            done = True
                            break
                        if seqmatch.ratio() > 0.6:
                            cursor.execute(*translation.update(
                                    [translation.src, translation.fuzzy],
                                    [string, True],
                                    where=(
                                        translation.name == report.report_name)
                                    & (translation.type == 'report')
                                    & (translation.src == string_trans)
                                    & (translation.module == module)))
                            del trans_reports[string_trans]
                            done = True
                            break
                    if not done:
                        cursor.execute(*translation.insert(
                                [translation.name, translation.lang,
                                    translation.type, translation.src,
                                    translation.value, translation.module,
                                    translation.fuzzy, translation.res_id],
                                [[
                                        report.report_name, 'en',
                                        'report', string,
                                        '', module,
                                        False, -1]]))
                if strings:
                    cursor.execute(*translation.delete(
                            where=(translation.name == report.report_name)
                            & (translation.type == 'report')
                            & (translation.module == module)
                            & ~translation.src.in_(list(strings))))

    def _translate_view(self, element):
        strings = []
        for attr in ('string', 'sum', 'confirm', 'help'):
            if element.get(attr):
                string = element.get(attr)
                if string:
                    strings.append(string)
        for child in element:
            strings.extend(self._translate_view(child))
        return strings

    def set_view(self):
        pool = Pool()
        View = pool.get('ir.ui.view')
        Translation = pool.get('ir.translation')
        context = Transaction().context

        if context.get('active_model') == View.__name__:
            views = View.browse(context.get('active_ids', []))
        elif context.get('active_model', 'ir.ui.menu') == 'ir.ui.menu':
            with Transaction().set_context(active_test=False):
                views = View.search([])
        else:
            return

        cursor = Transaction().connection.cursor()
        translation = Translation.__table__()
        for view in views:
            cursor.execute(*translation.select(
                    translation.id, translation.name, translation.src,
                    where=(translation.lang == 'en')
                    & (translation.type == 'view')
                    & (translation.name == view.model)
                    & (translation.module == view.module)))
            trans_views = {t['src']: t for t in cursor_dict(cursor)}

            xml = (view.arch or '').strip()
            if not xml:
                continue
            tree = etree.fromstring(xml)
            root_element = tree.getroottree().getroot()
            strings = self._translate_view(root_element)
            with Transaction().set_context(active_test=False):
                views2 = View.search([
                    ('model', '=', view.model),
                    ('id', '!=', view.id),
                    ('module', '=', view.module),
                    ])
            for view2 in views2:
                xml2 = view2.arch
                if not xml2:
                    continue
                tree2 = etree.fromstring(xml2)
                root2_element = tree2.getroottree().getroot()
                strings += self._translate_view(root2_element)
            if not strings:
                continue
            for string in set(strings):
                done = False
                if string in trans_views:
                    del trans_views[string]
                    continue
                for string_trans in trans_views:
                    if string_trans in strings:
                        continue
                    seqmatch = SequenceMatcher(lambda x: x == ' ',
                            string, string_trans)
                    if seqmatch.ratio() == 1.0:
                        del trans_views[string_trans]
                        done = True
                        break
                    if seqmatch.ratio() > 0.6:
                        cursor.execute(*translation.update(
                                [translation.src,
                                    translation.fuzzy],
                                [string, True],
                                where=(translation.id
                                    == trans_views[string_trans]['id'])))
                        del trans_views[string_trans]
                        done = True
                        break
                if not done:
                    cursor.execute(*translation.insert(
                            [translation.name, translation.lang,
                                translation.type, translation.src,
                                translation.value, translation.module,
                                translation.fuzzy, translation.res_id],
                            [[
                                    view.model, 'en',
                                    'view', string,
                                    '', view.module,
                                    False, -1]]))
            if strings:
                cursor.execute(*translation.delete(
                        where=(translation.name == view.model)
                        & (translation.type == 'view')
                        & (translation.module == view.module)
                        & ~translation.src.in_(strings)))

    def transition_set_(self):
        self.set_report()
        self.set_view()
        return 'succeed'


class TranslationCleanStart(ModelView):
    'Clean translation'
    __name__ = 'ir.translation.clean.start'


class TranslationCleanSucceed(ModelView):
    'Clean translation'
    __name__ = 'ir.translation.clean.succeed'


class TranslationClean(Wizard):
    "Clean translation"
    __name__ = 'ir.translation.clean'

    start = StateView('ir.translation.clean.start',
        'ir.translation_clean_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Clean', 'clean', 'tryton-ok', default=True),
            ])
    clean = StateTransition()
    succeed = StateView('ir.translation.clean.succeed',
        'ir.translation_clean_succeed_view_form', [
            Button('OK', 'end', 'tryton-ok', default=True),
            ])

    @staticmethod
    def _clean_field(translation):
        pool = Pool()
        try:
            model_name, field_name = translation.name.split(',', 1)
        except ValueError:
            return True
        try:
            Model = pool.get(model_name)
        except KeyError:
            return True
        field = Model._fields.get(field_name)
        if not field:
            return True
        if translation.src not in list(field.string):
            return True

    @staticmethod
    def _clean_model(translation):
        pool = Pool()
        try:
            model_name, field_name = translation.name.split(',', 1)
        except ValueError:
            return True
        try:
            Model = pool.get(model_name)
        except KeyError:
            return True
        if translation.res_id >= 0:
            if field_name not in Model._fields:
                return True
            field = Model._fields[field_name]
            if (not hasattr(field, 'translate')
                    or not field.translate):
                return True
        elif field_name not in ('name'):
            return True

    @staticmethod
    def _clean_report(translation):
        pool = Pool()
        Report = pool.get('ir.action.report')
        with Transaction().set_context(active_test=False):
            if not Report.search([
                        ('report_name', '=', translation.name),
                        ('translatable', '=', True),
                        ]):
                return True

    @staticmethod
    def _clean_selection(translation):
        pool = Pool()
        try:
            model_name, field_name = translation.name.split(',', 1)
        except ValueError:
            return True
        try:
            Model = pool.get(model_name)
        except KeyError:
            return True
        if field_name not in Model._fields:
            return True
        field = Model._fields[field_name]
        if (not hasattr(field, 'selection')
                or not field.selection
                or not getattr(field, 'translate_selection', True)):
            return True
        if (isinstance(field.selection, (tuple, list))
                and translation.src not in dict(field.selection).values()):
            return True

    @staticmethod
    def _clean_view(translation):
        pool = Pool()
        model_name = translation.name
        try:
            pool.get(model_name)
        except KeyError:
            return True

    @staticmethod
    def _clean_wizard_button(translation):
        pool = Pool()
        try:
            wizard_name, state_name, button_name = \
                translation.name.split(',', 2)
        except ValueError:
            return True
        try:
            Wizard = pool.get(wizard_name, type='wizard')
        except KeyError:
            return True
        if not Wizard:
            return True
        state = Wizard.states.get(state_name)
        if not state or not hasattr(state, 'buttons'):
            return True
        if button_name in [b.state for b in state.buttons]:
            return False
        return True

    @staticmethod
    def _clean_help(translation):
        pool = Pool()
        try:
            model_name, field_name = translation.name.split(',', 1)
        except ValueError:
            return True
        try:
            Model = pool.get(model_name)
        except KeyError:
            return True
        field = Model._fields.get(field_name)
        if not field:
            return True
        if not field.help:
            return True
        if translation.src not in list(field.help):
            return True

    def transition_clean(self):
        pool = Pool()
        Translation = pool.get('ir.translation')
        ModelData = pool.get('ir.model.data')

        to_delete = []
        keys = set()
        translations = Translation.search([])
        for translation in translations:
            if getattr(self, '_clean_%s' % translation.type)(translation):
                to_delete.append(translation.id)
            elif translation.type in ('field', 'model', 'wizard_button',
                    'help'):
                key = (translation.module, translation.lang, translation.type,
                    translation.name, translation.res_id)
                if key in keys:
                    to_delete.append(translation.id)
                else:
                    keys.add(key)
        # skip translation handled in ir.model.data
        models_data = ModelData.search([
            ('db_id', 'in', to_delete),
            ('model', '=', 'ir.translation'),
            ])
        for mdata in models_data:
            if mdata.db_id in to_delete:
                to_delete.remove(mdata.db_id)

        Translation.delete(Translation.browse(to_delete))
        return 'succeed'


class TranslationUpdateStart(ModelView):
    "Update translation"
    __name__ = 'ir.translation.update.start'

    language = fields.Many2One('ir.lang', 'Language', required=True,
        domain=[('translatable', '=', True)])

    @staticmethod
    def default_language():
        Lang = Pool().get('ir.lang')
        code = Transaction().context.get('language')
        try:
            lang, = Lang.search([
                    ('code', '=', code),
                    ('translatable', '=', True),
                    ], limit=1)
            return lang.id
        except ValueError:
            return None


class TranslationUpdate(Wizard):
    "Update translation"
    __name__ = "ir.translation.update"

    _source_types = ['report', 'view', 'wizard_button', 'selection']
    _ressource_types = ['field', 'model', 'help']
    _updatable_types = ['field', 'model', 'selection', 'help']

    start = StateView('ir.translation.update.start',
        'ir.translation_update_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Update', 'update', 'tryton-ok', default=True),
            ])
    update = StateAction('ir.act_translation_form')

    @staticmethod
    def transition_update():
        return 'end'

    def do_update(self, action):
        pool = Pool()
        Translation = pool.get('ir.translation')
        Report = pool.get('ir.action.report')
        View = pool.get('ir.ui.view')
        context = Transaction().context
        cursor = Transaction().connection.cursor()
        cursor_update = Transaction().connection.cursor()
        translation = Translation.__table__()
        lang = self.start.language.code
        parent_lang = get_parent(lang)

        if context.get('active_model') == Report.__name__:
            reports = Report.browse(context.get('active_ids', []))
            source_clause = ((translation.type == 'report')
                & translation.name.in_([r.report_name for r in reports]))
        elif context.get('active_model') == View.__name__:
            views = View.browse(context.get('active_ids', []))
            source_clause = ((translation.type == 'view')
                & translation.name.in_([v.model for v in views]))
        else:
            source_clause = Literal(True)

        columns = [translation.name.as_('name'),
            translation.res_id.as_('res_id'), translation.type.as_('type'),
            translation.src.as_('src'), translation.module.as_('module')]
        cursor.execute(*(translation.select(*columns,
                    where=(translation.lang == 'en')
                    & source_clause
                    & translation.type.in_(self._source_types))
                - translation.select(*columns,
                    where=(translation.lang == lang)
                    & source_clause
                    & translation.type.in_(self._source_types))))
        to_create = []
        for row in cursor_dict(cursor):
            to_create.append({
                'name': row['name'],
                'res_id': row['res_id'],
                'lang': lang,
                'type': row['type'],
                'src': row['src'],
                'module': row['module'],
                })
        if to_create:
            Translation.create(to_create)

        if parent_lang:
            columns.append(translation.value)
            cursor.execute(*(translation.select(*columns,
                        where=(translation.lang == parent_lang)
                        & source_clause
                        & translation.type.in_(self._source_types))
                    & translation.select(*columns,
                        where=(translation.lang == lang)
                        & source_clause
                        & translation.type.in_(self._source_types))))
            for row in cursor_dict(cursor):
                cursor_update.execute(*translation.update(
                        [translation.value],
                        [''],
                        where=(translation.name == row['name'])
                        & (translation.res_id == row['res_id'])
                        & (translation.type == row['type'])
                        & (translation.src == row['src'])
                        & (translation.module == row['module'])
                        & (translation.lang == lang)))

        if context.get('active_model') in {Report.__name__, View.__name__}:
            return

        columns = [translation.name.as_('name'),
            translation.res_id.as_('res_id'), translation.type.as_('type'),
            translation.module.as_('module')]
        cursor.execute(*(translation.select(*columns,
                    where=(translation.lang == 'en')
                    & translation.type.in_(self._ressource_types))
                - translation.select(*columns,
                    where=(translation.lang == lang)
                    & translation.type.in_(self._ressource_types))))
        to_create = []
        for row in cursor_dict(cursor):
            to_create.append({
                'name': row['name'],
                'res_id': row['res_id'],
                'lang': lang,
                'type': row['type'],
                'module': row['module'],
                })
        if to_create:
            Translation.create(to_create)

        if parent_lang:
            columns.append(translation.value)
            cursor.execute(*(translation.select(*columns,
                        where=(translation.lang == parent_lang)
                        & translation.type.in_(self._ressource_types))
                    & translation.select(*columns,
                        where=(translation.lang == lang)
                        & translation.type.in_(self._ressource_types))))
            for row in cursor_dict(cursor):
                cursor_update.execute(*translation.update(
                        [translation.value],
                        [''],
                        where=(translation.name == row['name'])
                        & (translation.res_id == row['res_id'])
                        & (translation.type == row['type'])
                        & (translation.module == row['module'])
                        & (translation.lang == lang)))

        columns = [translation.name.as_('name'),
            translation.res_id.as_('res_id'), translation.type.as_('type'),
            translation.src.as_('src'), translation.module.as_('module')]
        cursor.execute(*(translation.select(*columns,
                    where=(translation.lang == 'en')
                    & translation.type.in_(self._updatable_types))
                - translation.select(*columns,
                    where=(translation.lang == lang)
                    & translation.type.in_(self._updatable_types))))
        for row in cursor_dict(cursor):
            cursor_update.execute(*translation.update(
                    [translation.fuzzy, translation.src],
                    [True, row['src']],
                    where=(translation.name == row['name'])
                    & (translation.type == row['type'])
                    & (translation.lang == lang)
                    & (translation.res_id == (row['res_id'] or -1))
                    & (translation.module == row['module'])))

        cursor.execute(*translation.select(
                translation.src.as_('src'),
                Max(translation.value).as_('value'),
                where=(translation.lang == lang)
                & translation.src.in_(
                    translation.select(translation.src,
                        where=((translation.value == '')
                            | (translation.value == Null))
                        & (translation.lang == lang)))
                & (translation.value != '')
                & (translation.value != Null),
                group_by=translation.src))

        for row in cursor_dict(cursor):
            cursor_update.execute(*translation.update(
                    [translation.fuzzy, translation.value],
                    [True, row['value']],
                    where=(translation.src == row['src'])
                    & ((translation.value == '') | (translation.value == Null))
                    & (translation.lang == lang)))

        cursor_update.execute(*translation.update(
                [translation.fuzzy],
                [False],
                where=((translation.value == '') | (translation.value == Null))
                & (translation.lang == lang)))

        action['pyson_domain'] = PYSONEncoder().encode([
            ('module', '!=', None),
            ('lang', '=', lang),
        ])
        return action, {}


class TranslationExportStart(ModelView):
    "Export translation"
    __name__ = 'ir.translation.export.start'

    language = fields.Many2One('ir.lang', 'Language', required=True,
        domain=[
            ('translatable', '=', True),
            ('code', '!=', 'en'),
            ])
    module = fields.Many2One('ir.module', 'Module', required=True,
        domain=[
            ('state', 'in', ['activated', 'to upgrade', 'to remove']),
            ])

    @classmethod
    def default_language(cls):
        Lang = Pool().get('ir.lang')
        code = Transaction().context.get('language')
        domain = [('code', '=', code)] + cls.language.domain
        try:
            lang, = Lang.search(domain, limit=1)
            return lang.id
        except ValueError:
            return None


class TranslationExportResult(ModelView):
    "Export translation"
    __name__ = 'ir.translation.export.result'

    language = fields.Many2One('ir.lang', 'Language', readonly=True)
    module = fields.Many2One('ir.module', 'Module', readonly=True)
    file = fields.Binary('File', readonly=True, filename='filename')
    filename = fields.Char('Filename')


class TranslationExport(Wizard):
    "Export translation"
    __name__ = "ir.translation.export"

    start = StateView('ir.translation.export.start',
        'ir.translation_export_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Export', 'export', 'tryton-ok', default=True),
            ])
    export = StateTransition()
    result = StateView('ir.translation.export.result',
        'ir.translation_export_result_view_form', [
            Button('Close', 'end', 'tryton-close'),
            ])

    def transition_export(self):
        pool = Pool()
        Translation = pool.get('ir.translation')
        self.result.file = Translation.translation_export(
            self.start.language.code, self.start.module.name)
        return 'result'

    def default_result(self, fields):
        file_ = self.result.file
        cast = self.result.__class__.file.cast
        self.result.file = False  # No need to store it in session
        return {
            'module': self.start.module.id,
            'language': self.start.language.id,
            'file': cast(file_) if file_ else None,
            'filename': '%s.po' % self.start.language.code,
            }


class TranslationReport(Wizard):
    "Open translations of report"
    __name__ = 'ir.translation.report'
    start_state = 'open_'
    open_ = StateAction('ir.act_translation_report')

    def do_open_(self, action):
        pool = Pool()
        Report = pool.get('ir.action.report')
        context = Transaction().context
        assert context['active_model'] == Report.__name__
        reports = Report.browse(context['active_ids'])
        action['pyson_domain'] = PYSONEncoder().encode([
                ('type', '=', 'report'),
                ('name', 'in', [r.report_name for r in reports]),
                ])
        # Behaves like a relate to have name suffix
        action['keyword'] = 'form_relate'
        return action, {
            'model': context['active_model'],
            'ids': context['active_ids'],
            'id': context['active_id'],
            }
