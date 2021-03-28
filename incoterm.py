# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.cache import Cache
from trytond.model import ModelSQL, ModelView, MatchMixin, fields
from trytond.pool import Pool


class Incoterm(MatchMixin, ModelSQL, ModelView):
    "Incoterm"
    __name__ = 'incoterm.incoterm'
    _rec_name = 'code'

    name = fields.Char("Name", required=True)
    code = fields.Char("Code", required=True)
    version = fields.Char("Version", required=True)

    mode = fields.Selection([
            (None, "Any"),
            ('waterway', "Sea and Inland Waterway"),
            ], "Mode",
        help="The transport mode for which the term is available.")
    carrier = fields.Selection([
            ('buyer', "Buyer"),
            ('seller', "Seller"),
            ], "Carrier", required=True,
        help="Who contracts the main carriage.")
    risk = fields.Selection([
            ('before', "Before"),
            ('after', "After"),
            ], "Risk", required=True,
        help="When the risk is transferred relative to the main carriage.")
    location = fields.Boolean(
        "Location",
        help="If checked then a location is required.")

    companies = fields.Many2Many(
        'incoterm.incoterm-company.company', 'incoterm', 'company',
        "Companies",
        help="The companies that can use the incoterm.")

    _get_incoterms_cache = Cache(
        'incoterm.incoterm.get_incoterms', context=False)

    @classmethod
    def get_incoterms(cls, company, pattern):
        company_id = company.id if company else -1
        key = (company_id,) + tuple(sorted(pattern.items()))
        incoterms = cls._get_incoterms_cache.get(key)
        if incoterms is not None:
            return cls.browse(incoterms)

        incoterms = []
        for incoterm in cls.search([
                    ('companies', '=', company_id),
                    ]):
            if incoterm.match(pattern):
                incoterms.append(incoterm)

        cls._get_incoterms_cache.set(key, list(map(int, incoterms)))
        return incoterms

    def get_rec_name(self, name):
        return '%s (%s)' % (self.code, self.version)


class Incoterm_Company(ModelSQL):
    "Incoterm - Company"
    __name__ = 'incoterm.incoterm-company.company'

    incoterm = fields.Many2One(
        'incoterm.incoterm', "Incoterm", required=True, select=True)
    company = fields.Many2One(
        'company.company', "Company", required=True, select=True)

    @classmethod
    def create(cls, *args, **kwargs):
        pool = Pool()
        Incoterm = pool.get('incoterm.incoterm')
        records = super().create(*args, **kwargs)
        Incoterm._get_incoterms_cache.clear()
        return records

    @classmethod
    def write(cls, *args, **kwargs):
        pool = Pool()
        Incoterm = pool.get('incoterm.incoterm')
        super().write(*args, **kwargs)
        Incoterm._get_incoterms_cache.clear()

    @classmethod
    def delete(cls, *args, **kwargs):
        pool = Pool()
        Incoterm = pool.get('incoterm.incoterm')
        super().delete(*args, **kwargs)
        Incoterm._get_incoterms_cache.clear()
