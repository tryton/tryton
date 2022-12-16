#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field, size_validate


def autocomplete_validate(value):
    if value:
        assert isinstance(value, list), 'autocomplete must be a list'


class Char(Field):
    '''
    Define a char field (``unicode``).
    '''
    _type = 'char'

    def __init__(self, string='', size=None, help='', required=False,
            readonly=False, domain=None, states=None, translate=False,
            select=False, on_change=None, on_change_with=None, depends=None,
            order_field=None, context=None, loading=None,
            autocomplete=None):
        '''
        :param translate: A boolean. If ``True`` the field is translatable.
        :param size: A integer. If set defines the maximum size of the values.
        '''
        if loading is None:
            loading = 'lazy' if translate else 'eager'
        super(Char, self).__init__(string=string, help=help, required=required,
            readonly=readonly, domain=domain, states=states, select=select,
            on_change=on_change, on_change_with=on_change_with,
            depends=depends, order_field=order_field, context=context,
            loading=loading)
        self.__autocomplete = None
        self.autocomplete = autocomplete if autocomplete else None
        self.translate = translate
        self.__size = None
        self.size = size
    __init__.__doc__ += Field.__init__.__doc__

    def _get_autocomplete(self):
        return self.__autocomplete

    def _set_autocomplete(self, value):
        autocomplete_validate(value)
        self.__autocomplete = value

    autocomplete = property(_get_autocomplete, _set_autocomplete)

    def _get_size(self):
        return self.__size

    def _set_size(self, value):
        size_validate(value)
        self.__size = value

    size = property(_get_size, _set_size)
