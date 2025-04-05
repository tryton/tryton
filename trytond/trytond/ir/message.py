# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from collections import defaultdict

from trytond.cache import Cache
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.tools import grouped_slice
from trytond.transaction import Transaction

from .lang import get_parent_language as get_parent
from .translation import INTERNAL_LANG


class Message(ModelSQL, ModelView):
    __name__ = "ir.message"

    _message_cache = Cache('ir.message', context=False)
    text = fields.Text("Text", required=True, translate=True)
    text_plural = fields.Text("Text Plural")

    @classmethod
    def gettext(cls, *args, **variables):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        context = Transaction().context
        module, message_id, language = args
        fuzzy = bool(context.get('fuzzy_translation', False))

        key = (module, message_id, language, fuzzy)
        text = cls._message_cache.get(key)
        if text is None:
            message = cls(ModelData.get_id(module, message_id))
            translation = message._get_translation(language, fuzzy=fuzzy)
            if translation:
                text = translation.value or message.text
            else:
                text = message.text
            cls._message_cache.set(key, text)
        return text if not variables else text % variables

    @classmethod
    def ngettext(cls, *args, **variables):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Lang = pool.get('ir.lang')
        context = Transaction().context
        module, message_id, n, language = args
        fuzzy = bool(context.get('fuzzy_translation', False))

        lang = Lang.get(language)
        index = lang.get_plural(n)

        key = (module, message_id, index, language, fuzzy)
        text = cls._message_cache.get(key)
        if text is None:
            message = cls(ModelData.get_id(module, message_id))
            if not index:
                fallback = message.text
            else:
                fallback = message.text_plural or message.text
            translation = message._get_translation(language, fuzzy=fuzzy)
            if translation:
                values = [
                    translation.value, translation.value_1,
                    translation.value_2, translation.value_3]
                text = values[index] or fallback
            else:
                text = fallback
            cls._message_cache.set(key, text)
        return text if not variables else text % variables

    def _get_translation(self, language, fuzzy=False):
        pool = Pool()
        Translation = pool.get('ir.translation')
        if fuzzy:
            fuzzy_clause = []
        else:
            fuzzy_clause = [('fuzzy', '=', False)]
        while language:
            translations = Translation.search([
                    ('lang', '=', language),
                    ('type', '=', 'model'),
                    ('name', '=', f'{self.__name__},text'),
                    ('res_id', '=', self.id),
                    ] + fuzzy_clause,
                limit=1)
            if translations:
                translation, = translations
                return translation
            language = get_parent(language)

    @classmethod
    def on_modification(cls, mode, messages, field_names=None):
        pool = Pool()
        Translation = pool.get('ir.translation')
        super().on_modification(mode, messages, field_names=field_names)
        if mode in {'create', 'write'}:
            cls._set_translations(messages)
        if mode in {'write', 'delete'}:
            cls._message_cache.clear()
        if mode == 'delete':
            Translation.delete_ids(
                cls.__name__, 'model', [m.id for m in messages])

    @classmethod
    def _set_translations(cls, messages):
        pool = Pool()
        Translation = pool.get('ir.translation')

        id2translations = {}
        other_translations = defaultdict(list)
        for sub_messages in grouped_slice(messages):
            res_ids = [m.id for m in sub_messages]
            translations = Translation.search([
                    ('lang', '=', INTERNAL_LANG),
                    ('type', '=', 'model'),
                    ('name', '=', f'{cls.__name__},text'),
                    ('res_id', 'in', res_ids),
                    ])
            id2translations.update((t.res_id, t) for t in translations)
            for translation in Translation.search([
                        ('lang', '!=', INTERNAL_LANG),
                        ('type', '=', 'model'),
                        ('name', '=', f'{cls.__name__},text'),
                        ('res_id', 'in', res_ids),
                        ]):
                other_translations[translation.res_id].append(translation)

        to_save = []
        for message in messages:
            translation = id2translations.get(message.id)
            if translation:
                if ((translation.src == message.text)
                        and (translation.src_plural == message.text_plural)):
                    continue
            else:
                translation = Translation(
                    lang=INTERNAL_LANG,
                    type='model',
                    name=f'{cls.__name__},text',
                    res_id=message.id)
            translation.src = message.text
            translation.src_plural = message.text_plural
            translation.value = message.text
            translation.value_1 = message.text_plural
            to_save.append(translation)
            for other_translation in other_translations[message.id]:
                other_translation.src = message.text
                other_translation.src_plural = message.text_plural
                other_translation.fuzzy = True
                to_save.append(other_translation)

        if to_save:
            Translation.save(to_save)

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('text',) + tuple(clause[1:])]
