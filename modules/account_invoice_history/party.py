#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL


class Party(ModelSQL, ModelView):
    _name = 'party.party'
    _history = True

Party()


class Address(ModelSQL, ModelView):
    _name = 'party.address'
    _history = True

Address()
