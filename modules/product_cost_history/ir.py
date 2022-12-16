#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL


class Property(ModelSQL, ModelView):
    _name = 'ir.property'
    _history = True

Property()
