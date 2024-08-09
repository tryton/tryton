# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta


class Company(metaclass=PoolMeta):
    __name__ = 'company.company'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.header.help += "- ${siren}\n"
        cls.footer.help += "- ${siren}\n"

    @property
    def _substitutions(self):
        substitutions = super()._substitutions
        siren = self.party.siren
        substitutions['siren'] = siren.code if siren else ''
        return substitutions
