#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class Sha(Field):
    '''
    Define a sha field (``unicode``) of len 40.
    '''
    _type = 'sha'
