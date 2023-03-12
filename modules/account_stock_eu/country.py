# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

_ANY_DATE = object()


class Country(metaclass=PoolMeta):
    __name__ = 'country.country'

    def in_intrastat(self, date=_ANY_DATE):
        pool = Pool()
        Date = pool.get('ir.date')
        ModelData = pool.get('ir.model.data')
        Organization = pool.get('country.organization')

        ctx = {}
        if date is _ANY_DATE:
            ctx['active_test'] = False
        else:
            ctx['active_test'] = True
            if date is None:
                date = Date.today()
            ctx['date'] = date

        with Transaction().set_context(ctx):
            eu = Organization(ModelData.get_id('country', 'organization_eu'))
        return self in eu.countries


class Subdivision(metaclass=PoolMeta):
    __name__ = 'country.subdivision'

    intrastat_code = fields.Char(
        "Intrastat Code",
        states={
            'invisible': ~Eval('country_in_intrastat'),
            })

    country_in_intrastat = fields.Function(
        fields.Boolean("Country in Intrastat"),
        'on_change_with_country_in_intrastat')

    @fields.depends('country', '_parent_country.id')
    def on_change_with_country_in_intrastat(self, name=None):
        if self.country:
            return self.country.in_intrastat()

    def get_intrastat(self):
        "Return the first subdivision with intrastat code in parents"
        subdivision = self
        while not subdivision.intrastat_code:
            subdivision = subdivision.parent
            if not subdivision:
                break
        return subdivision
