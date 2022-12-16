# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import warnings

from trytond.transaction import Transaction
from .field import Field, FieldTranslate, size_validate
from ...rpc import RPC


class Char(FieldTranslate):
    '''
    Define a char field (``unicode``).
    '''
    _type = 'char'
    _py_type = str

    def __init__(self, string='', size=None, help='', required=False,
            readonly=False, domain=None, states=None, translate=False,
            select=False, on_change=None, on_change_with=None, depends=None,
            context=None, loading=None, autocomplete=None):
        '''
        :param translate: A boolean. If ``True`` the field is translatable.
        :param size: A integer. If set defines the maximum size of the values.
        '''
        if loading is None:
            loading = 'lazy' if translate else 'eager'
        super(Char, self).__init__(string=string, help=help, required=required,
            readonly=readonly, domain=domain, states=states, select=select,
            on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        self.autocomplete = set()
        if autocomplete:
            warnings.warn('autocomplete argument is deprecated, use the '
                'depends decorator', DeprecationWarning, stacklevel=2)
            self.autocomplete |= set(autocomplete)
        self.translate = translate
        self.__size = None
        self.size = size
        self.search_unaccented = True
    __init__.__doc__ += Field.__init__.__doc__

    def _get_size(self):
        return self.__size

    def _set_size(self, value):
        size_validate(value)
        self.__size = value

    size = property(_get_size, _set_size)

    @property
    def _sql_type(self):
        return 'VARCHAR(%s)' % self.size if self.size else 'VARCHAR'

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

    def definition(self, model, language):
        definition = super().definition(model, language)
        definition['autocomplete'] = list(self.autocomplete)
        if self.size is not None:
            definition['size'] = self.size
        return definition
