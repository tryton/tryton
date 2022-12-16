# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields


class MarketingAutomationMixin:
    __slots__ = ()

    marketing_party = fields.Function(
        fields.Many2One('party.party', "Marketing Party"),
        'get_marketing_party', searcher='search_marketing_party')

    def get_marketing_party(self, name):
        raise NotImplementedError

    @classmethod
    def search_marketing_party(cls, name, clause):
        raise NotImplementedError
