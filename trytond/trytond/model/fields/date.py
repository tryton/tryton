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


class Time(Field):
    '''
    Define a time field (``time``).
    '''
    _type = 'time'
