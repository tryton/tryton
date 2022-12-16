#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL
from trytond.model.cacheable import Cacheable


class Lang(ModelSQL, ModelView, Cacheable):
    _name = 'ir.lang'

    def get_translatable_languages(self, cursor, user, context=None):
        res = self.get(cursor, 'translatable_languages')
        if res is None:
            lang_ids = self.search(cursor, user, [
                    ('translatable', '=', True),
                    ], context=context)
            res = [x.code for x in self.browse(cursor, user, lang_ids,
                context=context)]
            self.add(cursor, 'translatable_languages', res)
        return res

    def create(self, cursor, user, vals, context=None):
        # Clear cache
        if self.get(cursor, 'translatable_languages'):
            self.invalidate(cursor, 'translatable_languages')
        return super(Lang, self).create(cursor, user, vals,
                     context=context)

    def write(self, cursor, user, ids, vals, context=None):
        # Clear cache
        if self.get(cursor, 'translatable_languages'):
            self.invalidate(cursor, 'translatable_languages')
        return super(Lang, self).write(cursor, user, ids, vals,
                     context=context)

    def delete(self, cursor, user, ids, context=None):
        # Clear cache
        if self.get(cursor, 'translatable_languages'):
            self.invalidate(cursor, 'translatable_languages')
        return super(Lang, self).delete(cursor, user, ids,
                     context=context)
Lang()
