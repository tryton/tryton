# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import re

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Selection(metaclass=PoolMeta):
    __name__ = 'carrier.selection'

    from_subdivision = fields.Many2One(
        'country.subdivision', "From Subdivision", ondelete='RESTRICT',
        domain=[
            ('country', '=', Eval('from_country', -1)),
            ],
        states={
            'invisible': ~Eval('from_country'),
            },
        depends=['from_country'],
        help="The subdivision the carrier collects from.\n"
        "Leave empty to allow collection from any subdivision.")
    from_zip = fields.Char("From ZIP",
        help=""
        "The regular expression to match the zips the carrier collects from."
        "\nLeave empty to allow collection from any ZIP.")
    to_subdivision = fields.Many2One(
        'country.subdivision', "To Subdivision", ondelete='RESTRICT',
        domain=[
            ('country', '=', Eval('to_country', -1)),
            ],
        states={
            'invisible': ~Eval('to_country'),
            },
        depends=['to_country'],
        help="The subdivision the carrier delivers to.\n"
        "Leave empty to allow delivery to any subdivision.")
    to_zip = fields.Char("To ZIP",
        help=""
        "The regular expression to match the zips the carrier collects to."
        "\nLeave empty to allow collection to any ZIP.")

    def match(self, pattern):
        pool = Pool()
        Subdivision = pool.get('country.subdivision')

        def parents(subdivision):
            if subdivision is None:
                return []
            subdivision = Subdivision(subdivision)
            while subdivision:
                yield subdivision
                subdivision = subdivision.parent

        if 'from_subdivision' in pattern:
            pattern = pattern.copy()
            from_subdivision = pattern.pop('from_subdivision')
            if (self.from_subdivision is not None
                    and self.from_subdivision not in parents(
                        from_subdivision)):
                return False
        if 'from_zip' in pattern:
            pattern = pattern.copy()
            from_zip = pattern.pop('from_zip') or ''
            if (self.from_zip is not None
                    and not re.match(self.from_zip, from_zip)):
                return False
        if 'to_subdivision' in pattern:
            pattern = pattern.copy()
            to_subdivision = pattern.pop('to_subdivision')
            if (self.to_subdivision is not None
                    and self.to_subdivision not in parents(to_subdivision)):
                return False
        if 'to_zip' in pattern:
            pattern = pattern.copy()
            to_zip = pattern.pop('to_zip') or ''
            if (self.to_zip is not None
                    and not re.search(self.to_zip, to_zip)):
                return False
        return super().match(pattern)
