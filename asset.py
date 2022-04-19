# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
import calendar
import datetime
from decimal import Decimal
from itertools import groupby

from dateutil import relativedelta, rrule

from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, Unique, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.modules.company import CompanyReport
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, If
from trytond.tools import cached_property, grouped_slice
from trytond.transaction import Transaction
from trytond.wizard import (
    Button, StateReport, StateTransition, StateView, Wizard)

from .exceptions import PrintDepreciationTableError


def date2datetime(date):
    return datetime.datetime.combine(date, datetime.time())


February = 2


def normalized_delta(start, end):
    "Returns timedelta using fixed 365 days per year"
    assert start <= end
    delta = end - start
    correction = 0
    if start.year == end.year:
        if calendar.isleap(start.year) and start.month <= 2 and end.month > 2:
            correction -= 1
    else:
        if calendar.isleap(start.year) and start.month <= February:
            correction -= 1
        if calendar.isleap(end.year) and end.month > February:
            correction -= 1
        correction -= calendar.leapdays(start.year + 1, end.year)
    return delta + datetime.timedelta(days=correction)


class Asset(Workflow, ModelSQL, ModelView):
    'Asset'
    __name__ = 'account.asset'
    _rec_name = 'number'
    number = fields.Char('Number', readonly=True, select=True)
    product = fields.Many2One('product.product', 'Product', required=True,
        states={
            'readonly': (Eval('lines', [0]) | (Eval('state') != 'draft')),
            },
        context={
            'company': Eval('company', None),
            },
        depends={'company'},
        domain=[
            ('type', '=', 'assets'),
            ('depreciable', '=', True),
            ])
    supplier_invoice_line = fields.Many2One('account.invoice.line',
        'Supplier Invoice Line',
        domain=[
            If(~Eval('product', None),
                ('product', '=', -1),
                ('product', '=', Eval('product', -1)),
                ),
            ('invoice.type', '=', 'in'),
            ['OR',
                ('company', '=', Eval('company', -1)),
                ('invoice.company', '=', Eval('company', -1)),
                ],
            ],
        states={
            'readonly': (Eval('lines', [0]) | (Eval('state') != 'draft')),
            })
    customer_invoice_line = fields.Function(fields.Many2One(
            'account.invoice.line', 'Customer Invoice Line'),
        'get_customer_invoice_line')
    account_journal = fields.Many2One('account.journal', 'Journal',
        states={
            'readonly': Eval('state') != 'draft',
            },
        domain=[('type', '=', 'asset')],
        required=True)
    company = fields.Many2One('company.company', 'Company',
        states={
            'readonly': Eval('state') != 'draft',
            },
        required=True)
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'on_change_with_currency')
    quantity = fields.Float(
        "Quantity", digits='unit',
        states={
            'readonly': (Bool(Eval('supplier_invoice_line', 1))
                | Eval('lines', [0])
                | (Eval('state') != 'draft')),
            })
    unit = fields.Many2One('product.uom', 'Unit',
        states={
            'readonly': (Bool(Eval('product'))
                | (Eval('state') != 'draft')),
            })
    value = Monetary(
        "Value", currency='currency', digits='currency',
        states={
            'readonly': (Eval('lines', [0]) | (Eval('state') != 'draft')),
            },
        required=True,
        help="The value of the asset when purchased.")
    depreciated_amount = Monetary(
        "Depreciated Amount", currency='currency', digits='currency',
        domain=[
            ('depreciated_amount', '<=', Eval('value')),
            ],
        states={
            'readonly': (Eval('lines', [0]) | (Eval('state') != 'draft')),
            },
        required=True,
        help="The amount already depreciated at the start date.")
    depreciating_value = fields.Function(Monetary(
            "Depreciating Value", currency='currency', digits='currency',
            help="The value of the asset at the start date."),
        'on_change_with_depreciating_value')
    residual_value = Monetary(
        "Residual Value", currency='currency', digits='currency',
        required=True,
        domain=[
            ('residual_value', '<=', Eval('depreciating_value')),
            ],
        states={
            'readonly': (Eval('lines', [0]) | (Eval('state') != 'draft')),
            })
    purchase_date = fields.Date('Purchase Date', states={
            'readonly': (Bool(Eval('supplier_invoice_line', 1))
                | Eval('lines', [0])
                | (Eval('state') != 'draft')),
            },
        required=True)
    start_date = fields.Date('Start Date', states={
            'readonly': (Eval('lines', [0]) | (Eval('state') != 'draft')),
            },
        required=True,
        domain=[('start_date', '<=', Eval('end_date', None))])
    end_date = fields.Date('End Date',
        states={
            'readonly': (Eval('lines', [0]) | (Eval('state') != 'draft')),
            },
        required=True,
        domain=[('end_date', '>=', Eval('start_date', None))])
    depreciation_method = fields.Selection([
            ('linear', 'Linear'),
            ], 'Depreciation Method',
        states={
            'readonly': (Eval('lines', [0]) | (Eval('state') != 'draft')),
            },
        required=True)
    frequency = fields.Selection([
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly'),
            ], 'Frequency',
        required=True,
        states={
            'readonly': (Eval('lines', [0]) | (Eval('state') != 'draft')),
            })
    state = fields.Selection([
            ('draft', 'Draft'),
            ('running', 'Running'),
            ('closed', 'Closed'),
            ], "State", readonly=True, sort=False)
    lines = fields.One2Many('account.asset.line', 'asset', 'Lines',
        readonly=True)
    move = fields.Many2One('account.move', 'Account Move', readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    update_moves = fields.Many2Many('account.asset-update-account.move',
        'asset', 'move', 'Update Moves', readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'invisible': ~Eval('update_moves'),
            })
    comment = fields.Text('Comment')
    revisions = fields.One2Many(
        'account.asset.revision', 'asset', "Revisions", readonly=True)

    @classmethod
    def __setup__(cls):
        super(Asset, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints = [
            ('invoice_line_uniq', Unique(table, table.supplier_invoice_line),
                'account_asset.msg_asset_invoice_line_unique'),
            ]
        cls._transitions |= set((
                ('draft', 'running'),
                ('running', 'closed'),
                ('running', 'draft'),
                ))
        cls._buttons.update({
                'draft': {
                    'invisible': (Eval('lines', [])
                        | (Eval('state') != 'running')),
                    'depends': ['state'],
                    },
                'run': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'close': {
                    'invisible': Eval('state') != 'running',
                    'depends': ['state'],
                    },
                'create_lines': {
                    'invisible': ~Eval('state').in_(['draft', 'running']),
                    'depends': ['state'],
                    },
                'clear_lines': {
                    'invisible': (~Eval('lines', [0])
                        | ~Eval('state').in_(['draft', 'running'])),
                    'depends': ['state'],
                    },
                'update': {
                    'invisible': Eval('state') != 'running',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        table_h = cls.__table_handler__(module_name)

        # Migration from 3.8: rename reference into number
        if table_h.column_exist('reference'):
            table_h.column_rename('reference', 'number')
        super(Asset, cls).__register__(module_name)

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def default_frequency(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        return Configuration(1).get_multivalue('asset_frequency', **pattern)

    @staticmethod
    def default_depreciation_method():
        return 'linear'

    @classmethod
    def default_depreciated_amount(cls):
        return Decimal(0)

    @classmethod
    def default_residual_value(cls):
        return Decimal(0)

    @staticmethod
    def default_start_date():
        return Pool().get('ir.date').today()

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('company')
    def on_change_company(self):
        self.frequency = self.default_frequency(
            company=self.company.id if self.company else None)

    @staticmethod
    def default_account_journal():
        Journal = Pool().get('account.journal')
        journals = Journal.search([
                ('type', '=', 'asset'),
                ])
        if len(journals) == 1:
            return journals[0].id
        return None

    @fields.depends('value', 'depreciated_amount')
    def on_change_with_depreciating_value(self, name=None):
        if self.value is not None and self.depreciated_amount is not None:
            return self.value - self.depreciated_amount
        else:
            return Decimal(0)

    @fields.depends('company')
    def on_change_with_currency(self, name=None):
        if self.company:
            return self.company.currency.id

    @fields.depends('supplier_invoice_line', 'unit')
    def on_change_supplier_invoice_line(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Unit = Pool().get('product.uom')

        if not self.supplier_invoice_line:
            self.quantity = None
            self.value = None
            self.start_date = self.default_start_date()
            return

        invoice_line = self.supplier_invoice_line
        invoice = invoice_line.invoice
        if invoice.company.currency != invoice.currency:
            with Transaction().set_context(date=invoice.currency_date):
                self.value = Currency.compute(
                    invoice.currency, invoice_line.amount,
                    invoice.company.currency)
        else:
            self.value = invoice_line.amount
        if invoice.invoice_date:
            self.purchase_date = invoice.invoice_date
            self.start_date = invoice.invoice_date
            if invoice_line.product.depreciation_duration:
                duration = relativedelta.relativedelta(
                    months=invoice_line.product.depreciation_duration,
                    days=-1)
                self.end_date = self.start_date + duration

        if not self.unit:
            self.quantity = invoice_line.quantity
        else:
            self.quantity = Unit.compute_qty(invoice_line.unit,
                invoice_line.quantity, self.unit)

    @fields.depends('product')
    def on_change_with_unit(self):
        if not self.product:
            return None
        return self.product.default_uom.id

    @fields.depends('end_date', 'product', 'start_date')
    def on_change_with_end_date(self):
        if (all(getattr(self, k, None) for k in ('product', 'start_date'))
                and not self.end_date):
            if self.product.depreciation_duration:
                duration = relativedelta.relativedelta(
                    months=int(self.product.depreciation_duration), days=-1)
                return self.start_date + duration
        return self.end_date

    @classmethod
    def get_customer_invoice_line(cls, assets, name):
        InvoiceLine = Pool().get('account.invoice.line')
        invoice_lines = InvoiceLine.search([
                ('asset', 'in', [a.id for a in assets]),
                ])
        result = dict((a.id, None) for a in assets)
        result.update(dict((l.asset.id, l.id) for l in invoice_lines))
        return result

    def get_depreciated_amount(self):
        lines = [line.depreciation for line in self.lines
            if line.move and line.move.state == 'posted']
        return sum(lines, Decimal(0))

    def compute_move_dates(self):
        """
        Returns all the remaining dates at which asset depreciation movement
        will be issued.
        """
        pool = Pool()
        Config = pool.get('account.configuration')
        config = Config(1)

        start_date = max([self.start_date] + [l.date for l in self.lines])
        delta = relativedelta.relativedelta(self.end_date, start_date)
        # dateutil >= 2.0 has replace __nonzero__ by __bool__ which doesn't
        # work in Python < 3
        if delta == relativedelta.relativedelta():
            if not self.lines:
                return [self.end_date]
            else:
                return []
        if self.frequency == 'monthly':
            rule = rrule.rrule(rrule.MONTHLY, dtstart=self.start_date,
                bymonthday=int(config.get_multivalue(
                        'asset_bymonthday', company=self.company.id)))
        elif self.frequency == 'yearly':
            rule = rrule.rrule(rrule.YEARLY, dtstart=self.start_date,
                bymonth=int(config.get_multivalue(
                            'asset_bymonth', company=self.company.id)),
                bymonthday=int(config.get_multivalue(
                            'asset_bymonthday', company=self.company.id)))
        dates = [d.date()
            for d in rule.between(date2datetime(start_date),
                date2datetime(self.end_date))]
        dates.append(self.end_date)
        return dates

    def compute_depreciation(self, amount, date, dates):
        """
        Returns the depreciation amount for an asset on a certain date.
        """
        if self.depreciation_method == 'linear':
            start_date = max([self.start_date
                    - relativedelta.relativedelta(days=1)]
                + [l.date for l in self.lines])
            first_delta = normalized_delta(start_date, dates[0])
            if len(dates) > 1:
                last_delta = normalized_delta(dates[-2], dates[-1])
            else:
                last_delta = first_delta
            if self.frequency == 'monthly':
                _, first_ndays = calendar.monthrange(
                    dates[0].year, dates[0].month)
                if (calendar.isleap(dates[0].year)
                        and dates[0].month == February):
                    first_ndays -= 1
                _, last_ndays = calendar.monthrange(
                    dates[-1].year, dates[-1].month)
                if (calendar.isleap(dates[-1].year)
                        and dates[-1].month == February):
                    last_ndays -= 1
            elif self.frequency == 'yearly':
                first_ndays = last_ndays = 365
            first_ratio = (
                Decimal(min(first_delta.days, first_ndays))
                / Decimal(first_ndays))
            last_ratio = (
                Decimal(min(last_delta.days, last_ndays))
                / Decimal(last_ndays))
            depreciation = amount / (
                len(dates) - 2 + first_ratio + last_ratio)
            if date == dates[0]:
                depreciation *= first_ratio
            elif date == dates[-1]:
                depreciation *= last_ratio
            return self.company.currency.round(depreciation)

    def depreciate(self):
        """
        Returns all the depreciation amounts still to be accounted.
        """
        Line = Pool().get('account.asset.line')
        amounts = {}
        dates = self.compute_move_dates()
        depreciated_amount = self.get_depreciated_amount()
        amount = (self.depreciating_value
            - depreciated_amount
            - self.residual_value)
        if amount <= 0:
            return amounts
        residual_value, acc_depreciation = (
            amount, depreciated_amount + self.depreciated_amount)
        asset_line = None
        for date in dates:
            depreciation = self.compute_depreciation(amount, date, dates)
            amounts[date] = asset_line = Line(
                acquired_value=self.value,
                depreciable_basis=amount,
                )
            if depreciation > residual_value:
                asset_line.depreciation = residual_value
                asset_line.accumulated_depreciation = (
                    acc_depreciation + residual_value)
                break
            else:
                residual_value -= depreciation
                acc_depreciation += depreciation
                asset_line.depreciation = depreciation
                asset_line.accumulated_depreciation = acc_depreciation
        else:
            if residual_value > 0 and asset_line is not None:
                asset_line.depreciation += residual_value
                asset_line.accumulated_depreciation += residual_value
        for asset_line in amounts.values():
            asset_line.actual_value = (self.value
                - asset_line.accumulated_depreciation)
        return amounts

    @classmethod
    @ModelView.button
    def create_lines(cls, assets):
        pool = Pool()
        Line = pool.get('account.asset.line')

        lines = []
        for asset in assets:
            for date, line in asset.depreciate().items():
                line.asset = asset.id
                line.date = date
                lines.append(line)
        Line.save(lines)

    @classmethod
    @ModelView.button
    def clear_lines(cls, assets):
        Line = Pool().get('account.asset.line')

        lines_to_delete = []
        for asset in assets:
            for line in asset.lines:
                if not line.move or line.move.state != 'posted':
                    lines_to_delete.append(line)
        Line.delete(lines_to_delete)

    @classmethod
    @ModelView.button_action('account_asset.wizard_update')
    def update(cls, assets):
        pass

    def get_move(self, line):
        """
        Return the account.move generated by an asset line.
        """
        pool = Pool()
        Period = pool.get('account.period')
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')

        period_id = Period.find(self.company.id, line.date)
        with Transaction().set_context(date=line.date):
            expense_line = MoveLine(
                credit=0,
                debit=line.depreciation,
                account=self.product.account_expense_used,
                )
            depreciation_line = MoveLine(
                debit=0,
                credit=line.depreciation,
                account=self.product.account_depreciation_used,
                )

        return Move(
            company=self.company,
            origin=line,
            period=period_id,
            journal=self.account_journal,
            date=line.date,
            lines=[expense_line, depreciation_line],
            )

    @classmethod
    def create_moves(cls, assets, date):
        """
        Creates all account move on assets before a date.
        """
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.asset.line')

        cls.create_lines(assets)

        moves = []
        lines = []
        for asset_ids in grouped_slice(assets):
            lines += Line.search([
                    ('asset', 'in', list(asset_ids)),
                    ('date', '<=', date),
                    ('move', '=', None),
                    ])
        for line in lines:
            moves.append(line.asset.get_move(line))
        Move.save(moves)
        for move, line in zip(moves, lines):
            line.move = move
        Line.save(lines)
        Move.post(moves)

    def get_closing_move(self, account, date=None):
        """
        Returns closing move values.
        """
        pool = Pool()
        Period = pool.get('account.period')
        Date = pool.get('ir.date')
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')

        if date is None:
            with Transaction().set_context(company=self.company.id):
                date = Date.today()
        period_id = Period.find(self.company.id, date)
        if self.supplier_invoice_line:
            account_asset = self.supplier_invoice_line.account.current()
        else:
            account_asset = self.product.account_asset_used

        asset_line = MoveLine(
            debit=0,
            credit=self.value,
            account=account_asset,
            )
        depreciation_line = MoveLine(
            debit=self.get_depreciated_amount() + self.depreciated_amount,
            credit=0,
            account=self.product.account_depreciation_used,
            )
        lines = [asset_line, depreciation_line]
        square_amount = asset_line.credit - depreciation_line.debit
        if square_amount:
            if not account:
                account = self.product.account_revenue_used
            counter_part_line = MoveLine(
                debit=square_amount if square_amount > 0 else 0,
                credit=-square_amount if square_amount < 0 else 0,
                account=account,
                )
            lines.append(counter_part_line)
        return Move(
            company=self.company,
            origin=self,
            period=period_id,
            journal=self.account_journal,
            date=date,
            lines=lines,
            )

    @classmethod
    def set_number(cls, assets):
        '''
        Fill the number field with asset sequence.
        '''
        pool = Pool()
        Config = pool.get('account.configuration')

        config = Config(1)
        for asset in assets:
            if asset.number:
                continue
            asset.number = config.get_multivalue(
                'asset_sequence', company=asset.company.id).get()
        cls.save(assets)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, assets):
        for asset in assets:
            if asset.lines:
                raise AccessError(
                    gettext('account_asset.msg_draft_lines',
                        asset=asset.rec_name))

    @classmethod
    @ModelView.button
    @Workflow.transition('running')
    def run(cls, assets):
        cls.set_number(assets)
        cls.create_lines(assets)

    @classmethod
    @ModelView.button
    @Workflow.transition('closed')
    def close(cls, assets, account=None, date=None):
        """
        Close the assets.
        If account is provided, it will be used instead of the expense account.
        """
        Move = Pool().get('account.move')

        cls.clear_lines(assets)
        moves = []
        for asset in assets:
            moves.append(asset.get_closing_move(account, date=date))
        Move.save(moves)
        for move, asset in zip(moves, assets):
            asset.move = move
        cls.save(assets)
        Move.post(moves)

    def get_rec_name(self, name):
        return '%s - %s' % (self.number, self.product.rec_name)

    @classmethod
    def search_rec_name(cls, name, clause):
        names = clause[2].split(' - ', 1)
        res = [('number', clause[1], names[0])]
        if len(names) != 1 and names[1]:
            res.append(('product', clause[1], names[1]))
        return res

    @classmethod
    def copy(cls, assets, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('lines', [])
        default.setdefault('update_moves', [])
        default.setdefault('number', None)
        default.setdefault('supplier_invoice_line', None)
        default.setdefault('move')
        default.setdefault('revisions', [])
        return super(Asset, cls).copy(assets, default=default)

    @classmethod
    def delete(cls, assets):
        for asset in assets:
            if asset.state != 'draft':
                raise AccessError(
                    gettext('account_asset.msg_delete_draft',
                        asset=asset.rec_name))
        return super(Asset, cls).delete(assets)


class AssetLine(ModelSQL, ModelView):
    'Asset Line'
    __name__ = 'account.asset.line'
    asset = fields.Many2One('account.asset', 'Asset', required=True,
        ondelete='CASCADE', readonly=True)
    date = fields.Date('Date', readonly=True)
    depreciation = Monetary(
        "Depreciation", currency='currency', digits='currency',
        required=True, readonly=True)
    acquired_value = Monetary(
        "Acquired Value", currency='currency', digits='currency',
        readonly=True)
    depreciable_basis = Monetary(
        "Depreciable Basis", currency='currency', digits='currency',
        readonly=True)
    actual_value = Monetary(
        "Actual Value", currency='currency', digits='currency', readonly=True)
    accumulated_depreciation = Monetary(
        "Accumulated Depreciation", currency='currency', digits='currency',
        readonly=True)
    move = fields.Many2One('account.move', 'Account Move', readonly=True)
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'on_change_with_currency')

    @classmethod
    def __setup__(cls):
        super(AssetLine, cls).__setup__()
        cls.__access__.add('asset')
        cls._order.insert(0, ('date', 'ASC'))

    @fields.depends('asset', '_parent_asset.currency')
    def on_change_with_currency(self, name=None):
        if self.asset:
            return self.asset.currency.id


class AssetUpdateMove(ModelSQL):
    'Asset - Update - Move'
    __name__ = 'account.asset-update-account.move'
    asset = fields.Many2One('account.asset', 'Asset', ondelete='CASCADE',
        select=True, required=True)
    move = fields.Many2One('account.move', 'Move', required=True)


class CreateMovesStart(ModelView):
    'Create Moves Start'
    __name__ = 'account.asset.create_moves.start'
    date = fields.Date('Date')

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()


class CreateMoves(Wizard):
    'Create Moves'
    __name__ = 'account.asset.create_moves'
    start = StateView('account.asset.create_moves.start',
        'account_asset.asset_create_moves_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'create_moves', 'tryton-ok', True),
            ])
    create_moves = StateTransition()

    def transition_create_moves(self):
        Asset = Pool().get('account.asset')
        with Transaction().set_context(_check_access=True):
            assets = Asset.search([
                    ('state', '=', 'running'),
                    ])
        assets = Asset.browse(assets)
        Asset.create_moves(assets, self.start.date)
        return 'end'


class UpdateAssetShowDepreciation(ModelView):
    'Update Asset Show Depreciation'
    __name__ = 'account.asset.update.show_depreciation'
    amount = fields.Numeric('Amount', readonly=True)
    date = fields.Date('Date', required=True,
        domain=[
            ('date', '>=', Eval('latest_move_date')),
            ('date', '<=', Eval('next_depreciation_date')),
            ],
        help=('The date must be between the last update/depreciation date '
            'and the next depreciation date.'))
    latest_move_date = fields.Date('Latest Move Date', readonly=True)
    next_depreciation_date = fields.Date('Next Depreciation Date',
        readonly=True)
    depreciation_account = fields.Many2One('account.account',
        'Depreciation Account', readonly=True)
    counterpart_account = fields.Many2One('account.account',
        'Counterpart Account')


class UpdateAsset(Wizard):
    'Update Asset'
    __name__ = 'account.asset.update'
    start = StateView('account.asset.revision',
        'account_asset.asset_revision_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'update_asset', 'tryton-ok', True),
            ])
    update_asset = StateTransition()
    show_move = StateView('account.asset.update.show_depreciation',
        'account_asset.asset_update_show_depreciation_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'create_move', 'tryton-ok', True),
            ])
    create_move = StateTransition()
    create_lines = StateTransition()

    def default_start(self, fields):
        return {
            'value': self.record.value,
            'residual_value': self.record.residual_value,
            'end_date': self.record.end_date,
            'asset': self.record.id,
            }

    def transition_update_asset(self):
        if self.start.value != self.record.value:
            return 'show_move'
        return 'create_lines'

    def get_latest_move_date(self, asset):
        previous_dates = [datetime.date.min]
        previous_dates += [m.date for m in asset.update_moves
            if m.state == 'posted']
        previous_dates += [l.date for l in asset.lines
                if l.move and l.move.state == 'posted']
        return max(previous_dates)

    def get_next_depreciation_date(self, asset):
        next_dates = [datetime.date.max]
        next_dates += [l.date for l in asset.lines
            if not l.move or l.move.state != 'posted']

        return min(next_dates)

    def default_show_move(self, fields):
        return {
            'amount': self.start.value - self.record.value,
            'date': datetime.date.today(),
            'depreciation_account': (
                self.record.product.account_depreciation_used.id),
            'counterpart_account': self.record.product.account_expense_used.id,
            'latest_move_date': self.get_latest_move_date(self.record),
            'next_depreciation_date': self.get_next_depreciation_date(
                self.record),
            }

    def get_move(self, asset):
        pool = Pool()
        Period = pool.get('account.period')
        Move = pool.get('account.move')
        period_id = Period.find(asset.company.id, self.show_move.date)
        return Move(
            company=asset.company,
            origin=asset,
            journal=asset.account_journal.id,
            period=period_id,
            date=self.show_move.date,
            )

    def get_move_lines(self, asset):
        MoveLine = Pool().get('account.move.line')
        expense_line = MoveLine(
            account=self.show_move.counterpart_account,
            credit=self.show_move.amount if self.show_move.amount > 0 else 0,
            debit=-self.show_move.amount if self.show_move.amount < 0 else 0,
            )
        depreciation_line = MoveLine(
            account=self.show_move.depreciation_account,
            credit=expense_line.debit,
            debit=expense_line.credit,
            )
        return [expense_line, depreciation_line]

    def transition_create_move(self):
        pool = Pool()
        Move = pool.get('account.move')

        latest_move_date = self.show_move.latest_move_date
        next_date = self.show_move.next_depreciation_date
        if not (latest_move_date <= self.show_move.date <= next_date):
            raise ValueError('The update move date is invalid')
        move = self.get_move(self.record)
        move.lines = self.get_move_lines(self.record)
        move.save()
        self.model.write([self.record], {
                'update_moves': [('add', [move.id])],
                })
        Move.post([move])
        return 'create_lines'

    def transition_create_lines(self):
        self.model.write([self.record], {
                'value': self.start.value,
                'residual_value': self.start.residual_value,
                'end_date': self.start.end_date,
                })
        self.model.clear_lines([self.record])
        self.model.create_lines([self.record])
        self.start.asset = self.record
        self.start.save()
        return 'end'


class AssetRevision(ModelSQL, ModelView):
    "Asset Revision"
    __name__ = 'account.asset.revision'
    currency = fields.Function(
        fields.Many2One('currency.currency', "Currency"),
        'on_change_with_currency')
    value = Monetary(
        "Asset Value", currency='currency', digits='currency',
        required=True)
    residual_value = Monetary(
        "Residual Value", currency='currency', digits='currency',
        required=True)
    end_date = fields.Date("End Date", required=True)
    origin = fields.Reference("Origin", selection='get_origins', select=True)
    description = fields.Char("Description")
    asset = fields.Many2One(
        'account.asset', "Asset", select=True, required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('asset')

    @fields.depends('asset', '_parent_asset.currency')
    def on_change_with_currency(self, name=None):
        if self.asset and self.asset.currency:
            return self.asset.currency.id

    @fields.depends('origin', 'value', 'asset', '_parent_asset.value')
    def on_change_origin(self, name=None):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        if isinstance(self.origin, InvoiceLine) and self.origin.id >= 0:
            self.value = self.asset.value + self.origin.amount

    @staticmethod
    def _get_origin():
        "Return list of Model names for origin Reference"
        return ['account.invoice.line']

    @classmethod
    def get_origins(cls):
        pool = Pool()
        IrModel = pool.get('ir.model')

        get_name = IrModel.get_name
        models = cls._get_origin()
        return [(None, '')] + [(m, get_name(m)) for m in models]


class AssetDepreciationTable(CompanyReport):
    'Asset Depreciation Table'
    __name__ = 'account.asset.depreciation_table'

    @classmethod
    def get_context(cls, records, header, data):
        context = super().get_context(records, header, data)

        AssetDepreciation = cls.get_asset_depreciation()
        AssetDepreciation.start_date = data['start_date']
        AssetDepreciation.end_date = data['end_date']
        Grouper = cls.get_grouper()
        grouped_assets = groupby(sorted(records, key=cls.group_assets),
            cls.group_assets)
        context['grouped_depreciations'] = grouped_depreciations = []
        for g_key, assets in grouped_assets:
            depreciations = [AssetDepreciation(a) for a in assets]
            grouped_depreciations.append(Grouper(g_key, depreciations))

        return context

    @staticmethod
    def group_assets(asset):
        return asset.product

    @classmethod
    def get_grouper(cls):

        class Grouper(object):
            def __init__(self, key, depreciations):
                self.product = key
                self.depreciations = depreciations

        def adder(attr_name):
            def _sum(self):
                return sum(getattr(d, attr_name)
                    for d in self.depreciations if getattr(d, attr_name))
            return _sum

        grouped_attributes = {
            'start_fixed_value',
            'value_increase',
            'value_decrease',
            'end_fixed_value',
            'start_value',
            'amortization_increase',
            'amortization_decrease',
            'end_value',
            'actual_value',
            'closing_value',
            }
        for attr_name in grouped_attributes:
            descr = cached_property(adder(attr_name))
            setattr(Grouper, attr_name, descr)
            if hasattr(descr, '__set_name__'):
                descr.__set_name__(Grouper, attr_name)

        return Grouper

    @classmethod
    def get_asset_depreciation(cls):

        class AssetDepreciation(object):
            def __init__(self, asset):
                self.asset = asset

            @cached_property
            def asset_lines(self):
                return [l for l in self.asset.lines
                    if self.start_date < l.date <= self.end_date]

            @cached_property
            def update_lines(self):
                def filter_(l):
                    return (l.account.type.expense
                        and self.start_date < l.move.date <= self.end_date)
                return list(filter(filter_,
                    (l for m in self.asset.update_moves for l in m.lines)))

            @cached_property
            def start_fixed_value(self):
                if self.asset.end_date < self.start_date:
                    return self.asset.value
                elif (self.start_date < self.asset.start_date
                        or not self.asset_lines):
                    return 0
                value = self.asset_lines[0].acquired_value
                date = self.asset_lines[0].date
                for line in self.update_lines:
                    if line.move.date < date:
                        value += line.debit - line.credit
                return value

            @cached_property
            def value_increase(self):
                value = sum(l.debit - l.credit for l in self.update_lines
                    if l.debit > l.credit)
                if (self.asset_lines
                        and self.start_date < self.asset.start_date):
                    value += self.asset_lines[0].acquired_value
                return value

            @cached_property
            def value_decrease(self):
                return sum(l.credit - l.debit for l in self.update_lines
                    if l.credit > l.debit)

            @cached_property
            def end_fixed_value(self):
                if not self.asset_lines:
                    return self.start_fixed_value
                value = self.asset_lines[-1].acquired_value
                date = self.asset_lines[-1].date
                for line in self.update_lines:
                    if line.move.date > date:
                        value += line.debit - line.credit
                return value

            @cached_property
            def start_value(self):
                if not self.asset_lines:
                    if self.asset.start_date > self.end_date:
                        return self.asset.value
                    else:
                        return 0
                return (self.asset_lines[0].actual_value
                    + self.asset_lines[0].depreciation)

            @cached_property
            def amortization_increase(self):
                return sum(l.depreciation for l in self.asset_lines
                    if l.depreciation > 0)

            @cached_property
            def amortization_decrease(self):
                return sum(l.depreciation for l in self.asset_lines
                    if l.depreciation < 0)

            @cached_property
            def end_value(self):
                if not self.asset_lines:
                    return self.start_value
                return self.asset_lines[-1].actual_value

            @cached_property
            def actual_value(self):
                value = self.end_value
                if self.asset_lines:
                    date = self.asset_lines[-1].date
                    value += sum(l.debit - l.credit for l in self.update_lines
                        if l.move.date > date)
                return value

            @cached_property
            def closing_value(self):
                if not self.asset.move:
                    return None
                revenue_lines = [l for l in self.asset.move.lines
                    if l.account == self.asset.product.account_revenue_used]
                return sum(l.debit - l.credit for l in revenue_lines)

        return AssetDepreciation


class PrintDepreciationTableStart(ModelView):
    'Asset Depreciation Table Start'
    __name__ = 'account.asset.print_depreciation_table.start'

    start_date = fields.Date('Start Date', required=True,
        domain=[('start_date', '<', Eval('end_date'))])
    end_date = fields.Date('End Date', required=True,
        domain=[('end_date', '>', Eval('start_date'))])

    @staticmethod
    def default_start_date():
        return datetime.date.today() - relativedelta.relativedelta(years=1)

    @staticmethod
    def default_end_date():
        return datetime.date.today()


class PrintDepreciationTable(Wizard):
    'Asset Depreciation Table'
    __name__ = 'account.asset.print_depreciation_table'
    start = StateView('account.asset.print_depreciation_table.start',
        'account_asset.print_depreciation_table_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('account.asset.depreciation_table')

    def do_print_(self, action):
        pool = Pool()
        Asset = pool.get('account.asset')
        with Transaction().set_context(_check_access=True):
            assets = Asset.search([
                    ['OR',
                        ('purchase_date', '<=', self.start.end_date),
                        ('start_date', '<=', self.start.end_date),
                        ],
                    ['OR',
                        ('move', '=', None),
                        ('move.date', '>=', self.start.start_date),
                        ],
                    ('state', '!=', 'draft'),
                    ])
        if not assets:
            raise PrintDepreciationTableError(
                gettext('account_asset.msg_no_assets'))
        return action, {
            'ids': [a.id for a in assets],
            'start_date': self.start.start_date,
            'end_date': self.start.end_date,
            }
