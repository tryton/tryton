# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from itertools import groupby

from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, Workflow, fields
from trytond.modules.company.model import CompanyValueMixin
from trytond.modules.product import round_price
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id
from trytond.transaction import Transaction

from .exceptions import NoShipmentWarning, SamePartiesWarning


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'
    shipment_cost_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Shipment Cost Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('account_stock_shipment_cost',
                        'sequence_type_shipment_cost')),
                ]))

    @classmethod
    def default_shipment_cost_sequence(cls, **pattern):
        return cls.multivalue_model(
            'shipment_cost_sequence').default_shipment_cost_sequence()


class ConfigurationShipmentCostSequence(ModelSQL, CompanyValueMixin):
    "Account Configuration Shipment Cost Sequence"
    __name__ = 'account.configuration.shipment_cost_sequence'
    shipment_cost_sequence = fields.Many2One(
        'ir.sequence', "Shipment Cost Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('account_stock_shipment_cost',
                    'sequence_type_shipment_cost')),
            ])

    @classmethod
    def default_shipment_cost_sequence(cls, **pattern):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id(
                'account_stock_shipment_cost', 'sequence_shipment_cost')
        except KeyError:
            return None


class ShipmentCost(Workflow, ModelSQL, ModelView):
    "Shipment Cost"
    __name__ = 'account.shipment_cost'
    _rec_name = 'number'

    _states = {
        'readonly': Eval('state') != 'draft',
        }

    number = fields.Char(
        "Number", select=True, readonly=True,
        help="The main identifier for the shipment cost.")
    company = fields.Many2One(
        'company.company', "Company", required=True,
        states=_states,
        help="The company the shipment cost is associated with.")

    shipments = fields.Many2Many(
        'account.shipment_cost-stock.shipment.out',
        'shipment_cost', 'shipment', "Shipments",
        domain=[
            ('company', '=', Eval('company', -1)),
            ('state', '=', 'done'),
            ],
        states=_states)
    shipment_returns = fields.Many2Many(
        'account.shipment_cost-stock.shipment.out.return',
        'shipment_cost', 'shipment', "Shipment Returns",
        domain=[
            ('company', '=', Eval('company', -1)),
            ('state', 'in', ['received', 'done']),
            ],
        states=_states)

    invoice_lines = fields.One2Many(
        'account.invoice.line', 'shipment_cost', 'Invoice Lines',
        add_remove=[
            ('shipment_cost', '=', None),
            ],
        domain=[
            ('company', '=', Eval('company', -1)),
            ('invoice.state', 'in', ['posted', 'paid']),
            ('invoice.type', '=', 'in'),
            ('product.shipment_cost', '=', True),
            ('type', '=', 'line'),
            ],
        states=_states)
    allocation_method = fields.Selection([
            ('shipment', "By Shipment"),
            ], "Allocation Method", required=True,
        states=_states)

    posted_date = fields.Date("Posted Date", readonly=True)
    state = fields.Selection([
            ('draft', "Draft"),
            ('posted', "Posted"),
            ('cancelled', "Cancelled"),
            ], "State", readonly=True, sort=False)

    factors = fields.Dict(None, "Factors", readonly=True)

    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()

        cls._order.insert(0, ('number', 'DESC'))
        cls._transitions |= set((
                ('draft', 'posted'),
                ('draft', 'cancelled'),
                ('posted', 'cancelled'),
                ('cancelled', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': Eval('state') == 'cancelled',
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': Eval('state') != 'cancelled',
                    'depends': ['state'],
                    },
                'post': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_allocation_method(cls):
        return 'shipment'

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, shipment_costs):
        for shipment_cost in shipment_costs:
            if shipment_cost.state == 'posted':
                getattr(shipment_cost, 'unallocate_cost_by_%s' %
                    shipment_cost.allocation_method)()
        cls.write(shipment_costs, {
                'posted_date': None,
                'factors': None,
                'state': 'cancelled',
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipment_costs):
        pass

    @property
    def cost(self):
        pool = Pool()
        Currency = pool.get('currency.currency')

        currency = self.company.currency
        cost = Decimal(0)

        for line in self.invoice_lines:
            with Transaction().set_context(date=line.invoice.currency_date):
                cost += Currency.compute(
                    line.invoice.currency, line.amount, currency, round=False)
        return cost

    @property
    def all_shipments(self):
        return self.shipments + self.shipment_returns

    @property
    def parties(self):
        return {l.invoice.party for l in self.invoice_lines}

    def allocate_cost_by_shipment(self):
        self.factors = self._get_shipment_factors()
        self._allocate_cost(self.factors)

    def unallocate_cost_by_shipment(self):
        factors = self.factors or self._get_shipment_factors()
        self._allocate_cost(factors, sign=-1)

    def _get_shipment_factors(self):
        shipments = self.all_shipments
        length = Decimal(len(shipments))
        factor = 1 / length
        return {str(shipment.id): factor for shipment in shipments}

    def _allocate_cost(self, factors, sign=1):
        "Allocate cost on shipments using factors"
        pool = Pool()
        Shipment = pool.get('stock.shipment.out')
        ShipmentReturn = pool.get('stock.shipment.out.return')
        assert sign in {1, -1}

        cost = self.cost * sign
        for shipments, klass in [
                (list(self.shipments), Shipment),
                (list(self.shipment_returns), ShipmentReturn),
                ]:
            for shipment in shipments:
                if (any(c.state == 'posted' for c in shipment.shipment_costs)
                        and shipment.cost):
                    shipment.cost += round_price(
                        cost * factors[str(shipment.id)])
                else:
                    shipment.cost = round_price(
                        cost * factors[str(shipment.id)])
            klass.save(shipments)
            klass.set_shipment_cost(shipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, shipment_costs):
        pool = Pool()
        Date = pool.get('ir.date')
        Warning = pool.get('res.user.warning')

        for shipment_cost in shipment_costs:
            parties = shipment_cost.parties
            all_shipments = shipment_cost.all_shipments
            if not all_shipments:
                key = Warning.format('post no shipment', [shipment_cost])
                if Warning.check(key):
                    raise NoShipmentWarning(
                        key,
                        gettext('account_stock_shipment_cost'
                            '.msg_shipment_cost_post_no_shipment',
                            shipment_cost=shipment_cost.rec_name))
            for shipment in all_shipments:
                for other in shipment.shipment_costs:
                    if other == shipment_cost:
                        continue
                    if other.parties & parties:
                        key = Warning.format(
                            'post same parties', [shipment_cost])
                        if Warning.check(key):
                            raise SamePartiesWarning(
                                key,
                                gettext('account_stock_shipment_cost'
                                    '.msg_shipment_cost_post_same_parties',
                                    shipment_cost=shipment_cost.rec_name,
                                    shipment=shipment.rec_name,
                                    other=other.rec_name))
                        else:
                            break
            getattr(shipment_cost, 'allocate_cost_by_%s' %
                shipment_cost.allocation_method)()
        for company, c_shipment_costs in groupby(
                shipment_costs, key=lambda s: s.company):
            with Transaction().set_context(company=company.id):
                today = Date.today()
            cls.write(list(c_shipment_costs), {
                    'posted_date': today,
                    'state': 'posted',
                    })

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Config = pool.get('account.configuration')

        vlist = [v.copy() for v in vlist]
        config = Config(1)
        default_company = cls.default_company()
        for values in vlist:
            if values.get('number') is None:
                values['number'] = config.get_multivalue(
                    'shipment_cost_sequence',
                    company=values.get('company', default_company)).get()
        return super().create(vlist)


class ShipmentCost_Shipment(ModelSQL):
    "Shipment Cost - Shipment"
    __name__ = 'account.shipment_cost-stock.shipment.out'
    shipment_cost = fields.Many2One(
        'account.shipment_cost', "Shipment Cost", required=True, select=True,
        ondelete='CASCADE')
    shipment = fields.Many2One(
        'stock.shipment.out', "Shipment", required=True, ondelete='CASCADE')


class ShipmentCost_ShipmentReturn(ModelSQL):
    "Shipment Cost - Shipment Return"
    __name__ = 'account.shipment_cost-stock.shipment.out.return'
    shipment_cost = fields.Many2One(
        'account.shipment_cost', "Shipment Cost",
        required=True, select=True, ondelete='CASCADE')
    shipment = fields.Many2One(
        'stock.shipment.out.return', "Shipment",
        required=True, ondelete='CASCADE')


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'
    shipment_cost = fields.Many2One(
        'account.shipment_cost', "Shipment Cost",
        readonly=True, select=True,
        states={
            'invisible': ~Eval('shipment_cost'),
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._check_modify_exclude.add('shipment_cost')

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('shipment_cost', None)
        return super().copy(lines, default=default)
