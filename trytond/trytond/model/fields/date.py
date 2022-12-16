#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class Date(Field):
    '''
    Define a date field (``date``).
    '''
    _type = 'date'


class DateTime(Field):
    '''
    Define a datetime field (``datetime``).
    '''
    _type = 'datetime'

    def __init__(self, string='', format='%H:%M:%S', help='', required=False,
            readonly=False, domain=None, states=None, select=False,
            on_change=None, on_change_with=None, depends=None,
            order_field=None, context=None, loading='eager'):
        '''
        :param format: The validation format as used by strftime.
        '''
        super(DateTime, self).__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            select=select, on_change=on_change, on_change_with=on_change_with,
            depends=depends, order_field=order_field, context=context,
            loading=loading)
        self.format = format

    __init__.__doc__ += Field.__init__.__doc__


class Time(DateTime):
    '''
    Define a time field (``time``).
    '''
    _type = 'time'
