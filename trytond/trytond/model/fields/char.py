# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import string
import warnings

from sql import Expression, Query
from sql.conditionals import Coalesce, NullIf
from sql.functions import Trim
from sql.operators import Not

from trytond.rpc import RPC
from trytond.tools import is_full_text, unescape_wildcard
from trytond.transaction import Transaction

from .field import Field, FieldTranslate, order_method, size_validate


class Char(FieldTranslate):
    '''
    Define a char field (``unicode``).
    '''
    _type = 'char'
    _py_type = str
    forbidden_chars = '\t\n\r\x0b\x0c'
    search_unaccented = True
    search_full_text = False

    def __init__(self, string='', size=None, help='', required=False,
            readonly=False, domain=None, states=None, translate=False,
            on_change=None, on_change_with=None, depends=None, context=None,
            loading=None, autocomplete=None, strip=True):
        '''
        :param translate: A boolean. If ``True`` the field is translatable.
        :param size: A integer. If set defines the maximum size of the values.
        '''
        if loading is None:
            loading = 'lazy' if translate else 'eager'
        super(Char, self).__init__(string=string, help=help, required=required,
            readonly=readonly, domain=domain, states=states,
            on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        self.autocomplete = set()
        if autocomplete:
            warnings.warn('autocomplete argument is deprecated, use the '
                'depends decorator', DeprecationWarning, stacklevel=2)
            self.autocomplete.update(autocomplete)
        self.strip = strip
        self.translate = translate
        self.__size = None
        self.size = size
    __init__.__doc__ += Field.__init__.__doc__

    def _get_size(self):
        return self.__size

    def _set_size(self, value):
        size_validate(value)
        self.__size = value

    size = property(_get_size, _set_size)

    @property
    def strip(self):
        return self.__strip

    @strip.setter
    def strip(self, value):
        assert value in {False, True, 'leading', 'trailing'}
        self.__strip = value

    @property
    def _sql_type(self):
        if isinstance(self.size, int):
            return 'VARCHAR(%s)' % self.size
        else:
            return 'VARCHAR'

    def __set__(self, inst, value):
        if isinstance(value, str) and self.strip:
            if self.strip == 'leading':
                value = value.lstrip()
            elif self.strip == 'trailing':
                value = value.rstrip()
            else:
                value = value.strip()
        super().__set__(inst, value)

    def sql_format(self, value):
        if value is not None and self.strip:
            if isinstance(value, (Query, Expression)):
                if self.strip == 'leading':
                    position = 'LEADING'
                elif self.strip == 'trailing':
                    position = 'TRAILING'
                else:
                    position = 'BOTH'
                value = Trim(
                    value, position=position, characters=string.whitespace)
            else:
                if self.strip == 'leading':
                    value = value.lstrip()
                elif self.strip == 'trailing':
                    value = value.rstrip()
                else:
                    value = value.strip()
        return super().sql_format(value)

    def set_rpc(self, model):
        super(Char, self).set_rpc(model)
        if self.autocomplete:
            func_name = 'autocomplete_%s' % self.name
            assert hasattr(model, func_name), \
                'Missing %s on model %s' % (func_name, model.__name__)
            model.__rpc__.setdefault(func_name, RPC(instantiate=0))

    def _domain_column(self, operator, column):
        column = super(Char, self)._domain_column(operator, column)
        if self.search_unaccented and operator.endswith('ilike'):
            database = Transaction().database
            column = database.unaccent(column)
        return column

    def _domain_value(self, operator, value):
        value = super(Char, self)._domain_value(operator, value)
        if self.search_unaccented and operator.endswith('ilike'):
            database = Transaction().database
            value = database.unaccent(value)
        return value

    def convert_domain(self, domain, tables, Model):
        transaction = Transaction()
        context = transaction.context
        database = transaction.database
        expression = super().convert_domain(domain, tables, Model)
        name, operator, value = domain
        if operator.endswith('ilike'):
            table, _ = tables[None]
            if self.translate:
                language = transaction.language
                model, join, column = self._get_translation_column(
                    Model, name)
                column = Coalesce(NullIf(column, ''), self.sql_column(model))
            else:
                language = None
                column = self.sql_column(table)
            column = self._domain_column(operator, column)

            threshold = context.get(
                '%s.%s.search_similarity' % (Model.__name__, name),
                context.get('search_similarity'))
            if database.has_similarity() and is_full_text(value) and threshold:
                sim_value = unescape_wildcard(value)
                sim_value = self._domain_value(operator, sim_value)
                expression = (
                    database.similarity(column, sim_value) >= threshold)
                if operator.startswith('not'):
                    expression = Not(expression)
                if self.translate:
                    expression = table.id.in_(
                        join.select(model.id, where=expression))

            key = '%s.%s.search_full_text' % (Model.__name__, name)
            if ((self.search_full_text or context.get(key))
                    and context.get(key, True)
                    and database.has_search_full_text()):
                if context.get(key) or is_full_text(value):
                    fts_column = database.format_full_text(
                        column, language=language)
                    fts_value = value
                    if key not in context:
                        fts_value = unescape_wildcard(fts_value)
                    fts_value = self._domain_value(operator, fts_value)
                    fts_value = database.format_full_text_query(
                        fts_value, language=language)
                    fts = database.search_full_text(fts_column, fts_value)
                    if operator.startswith('not'):
                        fts = Not(fts)
                    if self.translate:
                        fts = table.id.in_(
                            join.select(model.id, where=fts))
                    if database.has_similarity() and is_full_text(value):
                        if operator.startswith('not'):
                            expression |= fts
                        else:
                            expression &= fts
                    else:
                        expression = fts
        return expression

    @order_method
    def convert_order(self, name, tables, Model):
        transaction = Transaction()
        context = transaction.context
        database = transaction.database
        key = '%s.%s.order' % (Model.__name__, name)
        value = context.get(key)
        order = super().convert_order(name, tables, Model)
        if value:
            expression = None
            table, _ = tables[None]
            if self.translate:
                language = transaction.language
                column = self._get_translation_order(tables, Model, name)
            else:
                language = None
                column = self.sql_column(table)
            column = self._domain_column('ilike', column)
            if database.has_similarity():
                sim_value = unescape_wildcard(value)
                sim_value = self._domain_value('ilike', sim_value)
                expression = database.similarity(column, sim_value)
            key = '%s.%s.search_full_text' % (Model.__name__, name)
            if ((self.search_full_text or context.get(key))
                    and database.has_search_full_text()):
                column = database.format_full_text(column, language=language)
                value = self._domain_value('ilike', value)
                value = database.format_full_text_query(
                    value, language=language)
                rank = database.rank_full_text(
                    column, value, normalize=['rank'])
                if expression:
                    expression += rank
                else:
                    expression = rank
            if expression:
                order = [expression]
        return order

    def definition(self, model, language):
        definition = super().definition(model, language)
        definition['autocomplete'] = list(self.autocomplete)
        definition['strip'] = self.strip
        if self.size is not None:
            definition['size'] = self.size
        return definition
