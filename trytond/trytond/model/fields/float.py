# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pyson import PYSON, PYSONEncoder
from trytond.tools import cached_property

from .field import Field, get_eval_fields


def digits_validate(value):
    if value:
        assert isinstance(value, (tuple, str)), \
                'digits must be a tuple or a string'
        if isinstance(value, tuple):
            for i in value:
                assert isinstance(i, (int, PYSON)), \
                    'digits must be tuple of integers or PYSON'
                if isinstance(i, PYSON):
                    assert i.types() == {int}, \
                        'PYSON digits must return an integer'


def _get_digits_depends(field):
    if isinstance(field.digits, str):
        return {field.digits}
    else:
        return get_eval_fields(field.digits)


class Float(Field):
    '''
    Define a float field (``float``).
    '''
    _type = 'float'
    _sql_type = 'FLOAT'
    _py_type = float

    def __init__(self, string='', digits=None, help='', required=False,
            readonly=False, domain=None, states=None,
            on_change=None, on_change_with=None, depends=None,
            context=None, loading='eager'):
        '''
        :param digits: a list of two integers defining the total
            of digits and the number of decimals of the float.
        '''
        super(Float, self).__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        self.__digits = None
        self.digits = digits

    __init__.__doc__ += Field.__init__.__doc__

    def _get_digits(self):
        return self.__digits

    def _set_digits(self, value):
        digits_validate(value)
        self.__digits = value

    digits = property(_get_digits, _set_digits)

    def definition(self, model, language):
        encoder = PYSONEncoder()
        definition = super().definition(model, language)
        definition['digits'] = encoder.encode(self.digits)
        return definition

    @cached_property
    def display_depends(self):
        return super().display_depends | _get_digits_depends(self)

    @cached_property
    def edition_depends(self):
        return super().edition_depends | _get_digits_depends(self)

    @cached_property
    def validation_depends(self):
        return super().validation_depends | _get_digits_depends(self)
