# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from .field import Field


class Boolean(Field):
    '''
    Define a boolean field (``True`` or ``False``).
    '''
    _type = 'boolean'
    _sql_type = 'BOOL'
    _py_type = bool

    def __init__(self, string='', help='', readonly=False, domain=None,
            states=None, select=False, on_change=None, on_change_with=None,
            depends=None, context=None, loading='eager'):
        super(Boolean, self).__init__(string=string, help=help, required=False,
            readonly=readonly, domain=domain, states=states, select=select,
            on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)

    __init__.__doc__ = Field.__init__.__doc__

    def _domain_add_null(self, column, operator, value, expression):
        expression = super(Boolean, self)._domain_add_null(
            column, operator, value, expression)
        if operator in ('=', '!='):
            conv = {
                False: None,
                None: False,
                }
            if value is False or value is None:
                if operator == '=':
                    expression |= (column == conv[value])
                else:
                    expression &= (column != conv[value])
        return expression
