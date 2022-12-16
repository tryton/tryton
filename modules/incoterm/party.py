# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Literal
from sql.conditionals import Coalesce

from trytond.model import ModelSQL, ModelView, fields, sequence_ordered
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    purchase_incoterms = fields.One2Many(
        'party.incoterm', 'party', "Purchase Incoterms",
        filter=[
            ('type', '=', 'purchase'),
            ],
        help="Incoterms available for use with the supplier.\n"
        "Leave empty for all.")
    sale_incoterms = fields.One2Many(
        'party.incoterm', 'party', "Sale Incoterms",
        filter=[
            ('type', '=', 'sale'),
            ],
        help="Incoterms available for use with the customer.\n"
        "Leave empty for all.")


class Address(metaclass=PoolMeta):
    __name__ = 'party.address'

    is_incoterm_related = fields.Function(
        fields.Boolean("Is Incoterm Related"),
        'get_is_incoterm_related')

    @classmethod
    def _is_incoterm_related_query(cls, type=None, party=None):
        pool = Pool()
        Incoterm = pool.get('party.incoterm')
        context = Transaction().context
        if party is None:
            party = context.get('related_party')
        if type is None:
            type = context.get('incoterm_type')
        if not party:
            return
        table = Incoterm.__table__()
        where = table.party == party
        if type:
            where &= table.type == type
        return table.select(
            table.incoterm_location.as_('address'),
            Literal(True).as_('is_related'),
            where=where,
            group_by=[table.incoterm_location])

    @classmethod
    def get_is_incoterm_related(cls, addresses, name):
        is_related = {a.id: False for a in addresses}
        query = cls._is_incoterm_related_query()
        if query:
            cursor = Transaction().connection.cursor()
            cursor.execute(*query)
            is_related.update(cursor)
        return is_related

    @classmethod
    def order_is_incoterm_related(cls, tables):
        address, _ = tables[None]
        key = 'is_incoterm_related'
        if key not in tables:
            query = cls._is_incoterm_related_query()
            if not query:
                return []
            join = address.join(query, type_='LEFT',
                condition=query.address == address.id)
            tables[key] = {
                None: (join.right, join.condition),
                }
        else:
            query, _ = tables[key][None]
        return [Coalesce(query.is_related, False)]


class Incoterm(sequence_ordered(), ModelView, ModelSQL):
    "Party Incoterm"
    __name__ = 'party.incoterm'

    party = fields.Many2One(
        'party.party', "Party", required=True, ondelete='CASCADE', select=True,
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    company = fields.Many2One('company.company', "Company")
    type = fields.Selection([
            ('purchase', "Purchase"),
            ('sale', "Sale"),
            ], "Type", required=True)
    incoterm = fields.Many2One(
        'incoterm.incoterm', "Incoterm", required=True, ondelete='CASCADE')
    incoterm_location = fields.Many2One(
        'party.address', "Incoterm Location", ondelete='CASCADE',
        search_context={
            'related_party': Eval('party'),
            },
        search_order=[
            ('party.distance', 'ASC NULLS LAST'),
            ('id', None),
            ],
        depends={'party'})

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('party')

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')
