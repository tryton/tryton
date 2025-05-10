# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from sql import Null

from trytond.i18n import gettext
from trytond.model import Index, ModelView, Workflow, fields
from trytond.modules.account.exceptions import FiscalYearNotFoundError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from .exceptions import CounterPartyNotFound, CountryNotFound


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    _states = {
        'required': Eval('intrastat_type') & (Eval('state') == 'done'),
        'invisible': ~Eval('intrastat_type'),
        }
    _states_dispatch = {
        'required': (
            (Eval('intrastat_type') == 'dispatch')
            & (Eval('state') == 'done')),
        'invisible': Eval('intrastat_type') != 'dispatch',
        }

    intrastat_type = fields.Selection([
            (None, ""),
            ('arrival', "Arrival"),
            ('dispatch', "Dispatch"),
            ], "Intrastat Type", sort=False, readonly=True)
    intrastat_warehouse_country = fields.Many2One(
        'country.country', "Intrastat Warehouse Country",
        ondelete='RESTRICT', states=_states)
    intrastat_country = fields.Many2One(
        'country.country', "Intrastat Country",
        ondelete='RESTRICT', states=_states)
    intrastat_subdivision = fields.Many2One(
        'country.subdivision', "Intrastat Subdivision",
        ondelete='RESTRICT',
        domain=[
            ('country', '=', Eval('intrastat_warehouse_country', -1)),
            ('intrastat_code', '!=', None),
            ],
        states=_states)
    intrastat_tariff_code = fields.Many2One(
        'customs.tariff.code', "Intrastat Tariff Code",
        ondelete='RESTRICT', states=_states)
    intrastat_value = fields.Numeric(
        "Intrastat Value", digits=(None, 2), readonly=True, states=_states)
    intrastat_transaction = fields.Many2One(
        'account.stock.eu.intrastat.transaction', "Intrastat Transaction",
        ondelete='RESTRICT', states=_states)
    intrastat_additional_unit = fields.Float(
        "Intrastat Additional Unit", digits=(None, 3),
        states={
            'required': (
                _states['required'] & Eval('intrastat_tariff_code_uom')),
            'invisible': _states['invisible'],
            })
    intrastat_country_of_origin = fields.Many2One(
        'country.country', "Intrastat Country of Origin",
        ondelete='RESTRICT', states=_states_dispatch)
    intrastat_vat = fields.Many2One(
        'party.identifier', "Intrastat VAT",
        ondelete='RESTRICT',
        domain=[
            ('type', '=', 'eu_vat'),
            ],
        states={
            'invisible': _states_dispatch['invisible'],
            })
    intrastat_declaration = fields.Many2One(
        'account.stock.eu.intrastat.declaration', "Intrastat Declaration",
        readonly=True, states=_states, ondelete='RESTRICT',
        domain=[
            ('company', '=', Eval('company', -1)),
            ('country', '=', Eval('intrastat_warehouse_country', -1)),
            ])

    intrastat_tariff_code_uom = fields.Function(
        fields.Many2One('product.uom', "Intrastat Tariff Code Unit"),
        'on_change_with_intrastat_tariff_code_uom')

    del _states, _states_dispatch

    @classmethod
    def __setup__(cls):
        super().__setup__()
        intrastat_required = Eval('intrastat_type') & (Eval('state') == 'done')
        weight_required = cls.internal_weight.states.get('required')
        if weight_required:
            weight_required |= intrastat_required
        else:
            weight_required = intrastat_required
        cls.internal_weight.states['required'] = weight_required

        t = cls.__table__()
        cls._sql_indexes.add(
            Index(
                t,
                (t.intrastat_declaration, Index.Range()),
                (t.company, Index.Range()),
                where=(t.intrastat_type != Null) & (t.state == 'done')))

    @fields.depends(
        'effective_date', 'planned_date',
        'from_location', 'to_location',
        methods=['intrastat_from_country', 'intrastat_to_country'])
    def on_change_with_intrastat_type(self):
        from_country = self.intrastat_from_country
        to_country = self.intrastat_to_country
        if (from_country != to_country
                and from_country and from_country.in_intrastat(
                    date=self.effective_date or self.planned_date)
                and to_country and to_country.in_intrastat(
                    date=self.effective_date or self.planned_date)):
            if self.from_location.type == 'storage' and self.from_warehouse:
                return 'dispatch'
            elif self.to_location.type == 'storage' and self.to_warehouse:
                return 'arrival'

    @fields.depends('intrastat_tariff_code')
    def on_change_with_intrastat_tariff_code_uom(self, name=None):
        if self.intrastat_tariff_code:
            return self.intrastat_tariff_code.intrastat_uom

    @property
    @fields.depends(
        'from_location', 'to_location', 'shipment',
        methods=['intrastat_to_country'])
    def intrastat_from_country(self):
        if self.from_location:
            if self.from_warehouse and self.from_warehouse.address:
                return self.from_warehouse.address.country
            elif (self.from_location.type in {'supplier', 'customer'}
                    and hasattr(self.shipment, 'intrastat_from_country')):
                return self.shipment.intrastat_from_country
            elif self.from_location.type == 'lost_found':
                if (self.to_location
                        and self.to_location.type != 'lost_found'):
                    return self.intrastat_to_country

    @property
    @fields.depends(
        'to_location', 'from_location', 'shipment',
        methods=['intrastat_from_country'])
    def intrastat_to_country(self):
        if self.to_location:
            if self.to_warehouse and self.to_warehouse.address:
                return self.to_warehouse.address.country
            elif (self.to_location.type in {'supplier', 'customer'}
                    and hasattr(self.shipment, 'intrastat_to_country')):
                return self.shipment.intrastat_to_country
            elif self.to_location.type == 'lost_found':
                if (self.from_location
                        and self.from_location.type != 'lost_found'):
                    return self.intrastat_from_country

    @classmethod
    def _reopen_intrastat(cls, moves):
        pool = Pool()
        IntrastatDeclaration = pool.get(
            'account.stock.eu.intrastat.declaration')
        declarations = {
            m.intrastat_declaration for m in moves
            if m.intrastat_declaration}
        if declarations:
            IntrastatDeclaration.open(
                IntrastatDeclaration.browse(declarations))

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//page[@id="intrastat"]', 'states', {
                    'invisible': ~Eval('intrastat_type'),
                    }),
            ]

    def compute_fields(self, field_names=None):
        cls = self.__class__
        values = super().compute_fields(field_names=field_names)
        if (self.state not in {'done', 'cancelled'}
                and (not field_names
                    or (cls.intrastat_type.on_change_with & field_names))):
            intrastat_type = self.on_change_with_intrastat_type()
            if getattr(self, 'intrastat_type', None) != intrastat_type:
                values['intrastat_type'] = intrastat_type
        if (not field_names
                or (cls.intrastat_value.on_change_with & field_names)):
            intrastat_value = self.on_change_with_intrastat_value()
            if getattr(self, 'intrastat_value', None) != intrastat_value:
                values['intrastat_value'] = intrastat_value
        return values

    @classmethod
    def on_write(cls, moves, values):
        callback = super().on_write(moves, values)
        callback.append(lambda: cls._reopen_intrastat(moves))
        if any(f.startswith('intrastat_') for f in values):
            cls._reopen_intrastat(moves)
        return callback

    @classmethod
    def copy(cls, moves, default=None):
        default = default.copy() if default else {}
        default.setdefault('intrastat_type')
        default.setdefault('intrastat_warehouse_country')
        default.setdefault('intrastat_country')
        default.setdefault('intrastat_subdivision')
        default.setdefault('intrastat_tariff_code')
        default.setdefault('intrastat_value')
        default.setdefault('intrastat_transaction')
        default.setdefault('intrastat_additional_unit')
        default.setdefault('intrastat_country_of_origin')
        default.setdefault('intrastat_vat')
        default.setdefault('intrastat_declaration')
        return super().copy(moves, default=default)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, moves):
        pool = Pool()
        IntrastatDeclaration = pool.get(
            'account.stock.eu.intrastat.declaration')
        super().cancel(moves)
        declarations = {
            m.declaration for m in moves if m.intrastat_declaration}
        if declarations:
            IntrastatDeclaration.open(
                IntrastatDeclaration.browse(declarations))

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, moves):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        unknown_country = []
        for move in moves:
            move._set_intrastat()
            if (move.intrastat_type
                    and (not move.intrastat_from_country
                        or not move.intrastat_to_country)):
                unknown_country.append(move)
        if unknown_country:
            warning_name = Warning.format(
                'intrastat_country', unknown_country)
            if Warning.check(warning_name):
                names = ', '.join(m.rec_name for m in unknown_country[:5])
                if len(unknown_country) > 5:
                    names + '...'
                raise CountryNotFound(warning_name,
                    gettext('account_stock_eu.msg_move_country_not_found',
                        moves=names))
        cls.save(moves)
        super().do(moves)

    def _set_intrastat(self):
        pool = Pool()
        IntrastatTransaction = pool.get(
            'account.stock.eu.intrastat.transaction')
        IntrastatDeclaration = pool.get(
            'account.stock.eu.intrastat.declaration')
        Warning = pool.get('res.user.warning')
        if not self.intrastat_type:
            return
        self.set_effective_date()
        self.intrastat_value = self.on_change_with_intrastat_value()
        if self.intrastat_type == 'arrival':
            if not self.intrastat_warehouse_country:
                self.intrastat_warehouse_country = self.intrastat_to_country
            if not self.intrastat_country:
                self.intrastat_country = self.intrastat_from_country
            if not self.intrastat_subdivision:
                if (self.to_warehouse
                        and self.to_warehouse.address
                        and self.to_warehouse.address.subdivision):
                    subdivision = self.to_warehouse.address.subdivision
                    self.intrastat_subdivision = subdivision.get_intrastat()
            if self.intrastat_country_of_origin:
                self.intrastat_country_of_origin = None
            if self.intrastat_vat:
                self.intrastat_vat = None
        elif self.intrastat_type == 'dispatch':
            if not self.intrastat_warehouse_country:
                self.intrastat_warehouse_country = self.intrastat_from_country
            if not self.intrastat_country:
                self.intrastat_country = self.intrastat_to_country
            if not self.intrastat_subdivision:
                if (self.from_warehouse
                        and self.from_warehouse.address
                        and self.from_warehouse.address.subdivision):
                    subdivision = self.from_warehouse.address.subdivision
                    self.intrastat_subdivision = subdivision.get_intrastat()
            if not self.intrastat_country_of_origin:
                self.intrastat_country_of_origin = (
                    self.product.country_of_origin)
            if not self.intrastat_vat:
                counterparty = self._intrastat_counterparty()
                if not counterparty:
                    warning_name = Warning.format(
                        'intrastat_counterparty', [self])
                    if Warning.check(warning_name):
                        raise CounterPartyNotFound(warning_name,
                            gettext('account_stock_eu'
                                '.msg_move_counterparty_not_found',
                                move=self.rec_name))
                else:
                    fallback = None
                    for identifier in counterparty.identifiers:
                        if identifier.type == 'eu_vat':
                            if not fallback:
                                fallback = identifier
                            if (self.intrastat_country
                                    and identifier.code.startswith(
                                        self.intrastat_country.code)):
                                break
                    else:
                        identifier = fallback
                    self.intrastat_vat = identifier
        if self.intrastat_warehouse_country:
            self.intrastat_declaration = IntrastatDeclaration.get(
                self.company,
                self.intrastat_warehouse_country,
                self.effective_date or self.planned_date)
        if not self.intrastat_tariff_code:
            self.intrastat_tariff_code = self.product.get_tariff_code(
                self._intrastat_tariff_code_pattern())
        if not self.intrastat_transaction:
            self.intrastat_transaction = IntrastatTransaction.get(
                self._intrastat_transaction_code())
        if (not self.intrastat_additional_unit
                and self.intrastat_tariff_code
                and self.intrastat_tariff_code.intrastat_uom):
            quantity = self._intrastat_quantity(
                self.intrastat_tariff_code.intrastat_uom)
            if quantity is not None:
                ndigits = self.__class__.intrastat_additional_unit.digits[1]
                self.intrastat_additional_unit = round(quantity, ndigits)

    def _intrastat_tariff_code_pattern(self):
        return {
            'date': self.effective_date,
            'country': (
                self.intrastat_country.id if self.intrastat_country else None),
            }

    def _intrastat_transaction_code(self):
        pool = Pool()
        ShipmentIn = pool.get('stock.shipment.in')
        ShipmentInReturn = pool.get('stock.shipment.in.return')
        ShipmentOut = pool.get('stock.shipment.out')
        ShipmentOutReturn = pool.get('stock.shipment.out.return')
        ShipmentInternal = pool.get('stock.shipment.internal')

        if isinstance(self.shipment, ShipmentInternal):
            return '31'

        try:
            SaleLine = pool.get('sale.line')
        except KeyError:
            pass
        else:
            if isinstance(self.origin, SaleLine):
                sale = self.origin.sale
                party = sale.invoice_party or sale.party
                if self.quantity >= 0:
                    if party.tax_identifier:
                        return '11'
                    else:
                        return '12'
                else:
                    return '21'
        try:
            PurchaseLine = pool.get('purchase.line')
        except KeyError:
            pass
        else:
            if isinstance(self.origin, PurchaseLine):
                purchase = self.origin.purchase
                party = purchase.invoice_party or purchase.party
                if self.quantity >= 0:
                    if party.tax_identifier:
                        return '11'
                    else:
                        return '12'
                else:
                    return '21'

        if isinstance(self.shipment, ShipmentIn):
            if self.shipment.supplier.tax_identifier:
                return '11'
            else:
                return '12'
        elif isinstance(self.shipment, ShipmentInReturn):
            return '21'
        elif isinstance(self.shipment, ShipmentOut):
            if self.shipment.customer.tax_identifier:
                return '11'
            else:
                return '12'
        elif isinstance(self.shipment, ShipmentOutReturn):
            return '21'

    @fields.depends(
        'state', 'unit_price', 'currency', 'quantity', 'effective_date',
        'planned_date', 'company')
    def on_change_with_intrastat_value(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        if self.state == 'done' and self.unit_price is not None:
            ndigits = self.__class__.intrastat_value.digits[1]
            with Transaction().set_context(
                    date=self.effective_date or self.planned_date):
                return round(Currency.compute(
                        self.currency,
                        self.unit_price * Decimal(str(self.quantity)),
                        self.company.intrastat_currency,
                        round=False), ndigits)

    def _intrastat_quantity(self, unit):
        pool = Pool()
        UoM = pool.get('product.uom')
        if self.unit.category == unit.category:
            return UoM.compute_qty(self.unit, self.quantity, unit, round=False)
        elif (getattr(self, 'secondary_unit', None)
                and self.secondary_unit.category == unit.category):
            return UoM.compute_qty(
                self.secondary_unit, self.secondary_quantity, unit,
                round=False)
        if (self.product.volume
                and self.product.volume_uom.category == unit.category):
            return UoM.compute_qty(
                self.product.volume_uom,
                self.internal_quantity * self.product.volume,
                unit, round=False)

    def _intrastat_counterparty(self):
        pool = Pool()
        ShipmentIn = pool.get('stock.shipment.in')
        ShipmentInReturn = pool.get('stock.shipment.in.return')
        ShipmentOut = pool.get('stock.shipment.out')
        ShipmentOutReturn = pool.get('stock.shipment.out.return')
        ShipmentInternal = pool.get('stock.shipment.internal')

        if isinstance(self.shipment, ShipmentInternal):
            return self.company.party

        try:
            SaleLine = pool.get('sale.line')
        except KeyError:
            pass
        else:
            if isinstance(self.origin, SaleLine):
                sale = self.origin.sale
                return sale.invoice_party or sale.party

        try:
            PurchaseLine = pool.get('purchase.line')
        except KeyError:
            pass
        else:
            if isinstance(self.origin, PurchaseLine):
                purchase = self.origin.purchase
                return purchase.invoice_party or purchase.party

        if isinstance(self.shipment, (ShipmentIn, ShipmentInReturn)):
            return self.shipment.supplier
        elif isinstance(self.shipment, (ShipmentOut, ShipmentOutReturn)):
            return self.shipment.customer


class Move_Production(metaclass=PoolMeta):
    __name__ = 'stock.move'

    @property
    @fields.depends('from_location', 'production')
    def intrastat_from_country(self):
        country = super().intrastat_from_country
        if self.from_location:
            if (self.from_location.type == 'production'
                    and self.production and self.production.warehouse.address):
                country = self.production.warehouse.address.country
        return country

    @property
    @fields.depends('to_location', 'production')
    def intrastat_to_country(self):
        country = super().intrastat_to_country
        if self.to_location:
            if (self.to_location.type == 'production'
                    and self.production and self.production.warehouse.address):
                country = self.production.warehouse.address.country
        return country


class Move_Incoterm(metaclass=PoolMeta):
    __name__ = 'stock.move'

    _states = {
        'required': (
            Eval('intrastat_type') & Eval('intrastat_extended')
            & (Eval('state') == 'done')),
        'invisible': ~Eval('intrastat_type') | ~Eval('intrastat_extended'),
        }

    intrastat_transport = fields.Many2One(
        'account.stock.eu.intrastat.transport', "Intrastat Transport",
        ondelete='RESTRICT', states=_states)
    intrastat_incoterm = fields.Many2One(
        'incoterm.incoterm', "Intrastat Incoterm",
        ondelete='RESTRICT', states=_states)

    intrastat_extended = fields.Function(
        fields.Boolean("Intrastat Extended"),
        'on_change_with_intrastat_extended')

    del _states

    @fields.depends('company', 'effective_date', 'planned_date')
    def on_change_with_intrastat_extended(self, name=None):
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        if self.company:
            try:
                fiscalyear = FiscalYear.find(
                    self.company.id,
                    date=self.effective_date or self.planned_date)
            except FiscalYearNotFoundError:
                pass
            else:
                return fiscalyear.intrastat_extended

    def _set_intrastat(self):
        from trytond.modules.incoterm.common import IncotermMixin
        super()._set_intrastat()

        if not self.intrastat_transport:
            carrier = self._intrastat_carrier()
            if carrier:
                self.intrastat_transport = carrier.intrastat_transport

        if not self.intrastat_incoterm:
            if isinstance(self.shipment, IncotermMixin):
                self.intrastat_incoterm = self.shipment.incoterm
            elif isinstance(self.origin, IncotermMixin):
                self.intrastat_incoterm = self.origin.incoterm

    def _intrastat_carrier(self):
        if (hasattr(self.shipment, 'carrier')
                and not getattr(self.shipment, 'carriages', None)):
            return self.shipment.carrier

    @classmethod
    def copy(cls, moves, default=None):
        default = default.copy() if default else {}
        default.setdefault('intrastat_transport')
        default.setdefault('intrastat_incoterm')
        return super().copy(moves, default=default)


class Move_Consignment(metaclass=PoolMeta):
    __name__ = 'stock.move'

    def _intrastat_transaction_code(self):
        code = super()._intrastat_transaction_code()
        if self.is_supplier_consignment or self.is_customer_consignment:
            code = '32'
        return code


class ShipmentMixin:
    __slots__ = ()

    @property
    def intrastat_from_country(self):
        raise NotImplementedError

    @property
    def intrastat_to_country(self):
        raise NotImplementedError


class ShipmentIn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    intrastat_from_country = fields.Many2One(
        'country.country', "From Country")
    intrastat_to_country = fields.Function(
        fields.Many2One('country.country', "To Country"),
        'on_change_with_intrastat_to_country')

    @fields.depends('supplier')
    def on_change_supplier(self):
        if self.supplier:
            address = self.supplier.address_get(type='delivery')
            if address:
                self.intrastat_from_country = address.country

    @fields.depends('warehouse')
    def on_change_with_intrastat_to_country(self, name=None):
        if self.warehouse and self.warehouse.address:
            return self.warehouse.address.country


class ShipmentInReturn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'

    intrastat_from_country = fields.Function(
        fields.Many2One('country.country', "From Country"),
        'on_change_with_intrastat_from_country')
    intrastat_to_country = fields.Function(
        fields.Many2One('country.country', "To Country"),
        'on_change_with_intrastat_to_country')

    @fields.depends('warehouse')
    def on_change_with_intrastat_from_country(self, name=None):
        if self.warehouse and self.warehouse.address:
            return self.warehouse.address.country

    @fields.depends('delivery_address')
    def on_change_with_intrastat_to_country(self, name=None):
        if self.delivery_address:
            return self.delivery_address.country


class ShipmentOut(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    intrastat_from_country = fields.Function(
        fields.Many2One('country.country', "From Country"),
        'on_change_with_intrastat_from_country')
    intrastat_to_country = fields.Function(
        fields.Many2One('country.country', "To Country"),
        'on_change_with_intrastat_to_country')

    @fields.depends('warehouse')
    def on_change_with_intrastat_from_country(self, name=None):
        if self.warehouse and self.warehouse.address:
            return self.warehouse.address.country

    @fields.depends('delivery_address')
    def on_change_with_intrastat_to_country(self, name=None):
        if self.delivery_address:
            return self.delivery_address.country


class ShipmentOutReturn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    intrastat_from_country = fields.Many2One('country.country', "From Country")
    intrastat_to_country = fields.Function(
        fields.Many2One('country.country', "To Country"),
        'on_change_with_intrastat_to_country')

    @fields.depends('customer')
    def on_change_customer(self):
        if self.customer:
            address = self.customer.address_get(type='delivery')
            if address:
                self.intrastat_from_country = address.country

    @fields.depends('warehouse')
    def on_change_with_intrastat_to_country(self, name=None):
        if self.warehouse and self.warehouse.address:
            return self.warehouse.address.country


class ShipmentInternal(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'

    intrastat_from_country = fields.Function(
        fields.Many2One('country.country', "From Country"),
        'on_change_with_intrastat_from_country')
    intrastat_to_country = fields.Function(
        fields.Many2One('country.country', "To Country"),
        'on_change_with_intrastat_to_country')

    @fields.depends('from_location')
    def on_change_with_intrastat_from_country(self, name=None):
        if (self.from_location
                and self.from_location.warehouse
                and self.from_location.warehouse.address):
            return self.from_location.warehouse.address.country

    @fields.depends('to_location')
    def on_change_with_intrastat_to_country(self, name=None):
        if (self.to_location
                and self.to_location.warehouse
                and self.to_location.warehouse.address):
            return self.to_location.warehouse.address.country


class ShipmentDrop(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.drop'

    intrastat_from_country = None
    intrastat_to_country = None
