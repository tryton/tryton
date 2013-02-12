# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
import datetime
import calendar
from decimal import Decimal
from dateutil import relativedelta
from dateutil import rrule

from trytond.model import Workflow, ModelSQL, ModelView, fields
from trytond.pyson import Eval, Bool
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button

__all__ = ['Asset', 'AssetLine', 'AssetUpdateMove',
    'CreateMovesStart', 'CreateMoves',
    'UpdateAssetStart', 'UpdateAssetShowDepreciation', 'UpdateAsset']


def date2datetime(date):
    return datetime.datetime.combine(date, datetime.time())


class Asset(Workflow, ModelSQL, ModelView):
    'Asset'
    __name__ = 'account.asset'
    _rec_name = 'reference'
    reference = fields.Char('Reference', readonly=True, select=True)
    product = fields.Many2One('product.product', 'Product', required=True,
        states={
            'readonly': (Eval('lines', [0]) | (Eval('state') != 'draft')),
            },
        depends=['state'],
        domain=[
            ('type', '=', 'assets'),
            ('depreciable', '=', True),
            ])
    supplier_invoice_line = fields.Many2One('account.invoice.line',
        'Supplier Invoice Line',
        domain=[
            ('product', '=', Eval('product', -1)),
            ('invoice.type', '=', 'in_invoice'),
            ],
        states={
            'readonly': (Eval('lines', [0]) | (Eval('state') != 'draft')),
            },
        on_change=['supplier_invoice_line', 'unit'],
        depends=['product', 'state'])
    customer_invoice_line = fields.Function(fields.Many2One(
            'account.invoice.line', 'Customer Invoice Line'),
        'get_customer_invoice_line')
    account_journal = fields.Many2One('account.journal', 'Journal',
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'],
        domain=[('type', '=', 'asset')],
        required=True)
    company = fields.Many2One('company.company', 'Company',
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'],
        required=True)
    currency_digits = fields.Function(fields.Integer('Currency Digits',
            on_change_with=['company']), 'on_change_with_currency_digits')
    quantity = fields.Float('Quantity',
        digits=(16, Eval('unit_digits', 2)),
        states={
            'readonly': (Bool(Eval('supplier_invoice_line', 1))
                | Eval('lines', [0])
                | (Eval('state') != 'draft')),
            },
        depends=['state', 'unit_digits'])
    unit = fields.Many2One('product.uom', 'Unit',
        on_change_with=['product'],
        states={
            'readonly': (Bool(Eval('product'))
                | (Eval('state') != 'draft')),
            },
        depends=['state'])
    unit_digits = fields.Function(fields.Integer('Unit Digits',
            on_change_with=['unit']), 'on_change_with_unit_digits')
    value = fields.Numeric('Value',
        digits=(16, Eval('currency_digits', 2)),
        states={
            'readonly': (Eval('lines', [0]) | (Eval('state') != 'draft')),
            },
        depends=['currency_digits', 'state'],
        required=True)
    residual_value = fields.Numeric('Residual Value',
        states={
            'readonly': (Eval('lines', [0]) | (Eval('state') != 'draft')),
            },
        depends=['currency_digits', 'state'],
        required=True,
        digits=(16, Eval('currency_digits', 2)))
    purchase_date = fields.Date('Purchase Date', states={
            'readonly': (Bool(Eval('supplier_invoice_line', 1))
                | Eval('lines', [0])
                | (Eval('state') != 'draft')),
            },
        required=True,
        depends=['state'])
    start_date = fields.Date('Start Date', states={
            'readonly': (Eval('lines', [0]) | (Eval('state') != 'draft')),
            },
        required=True,
        depends=['state'])
    end_date = fields.Date('End Date',
        on_change_with=['end_date', 'product', 'start_date'],
        states={
            'readonly': (Eval('lines', [0]) | (Eval('state') != 'draft')),
            },
        required=True,
        depends=['state'])
    depreciation_method = fields.Selection([
            ('linear', 'Linear'),
            ], 'Depreciation Method',
        states={
            'readonly': (Eval('lines', [0]) | (Eval('state') != 'draft')),
            },
        required=True,
        depends=['state'])
    frequency = fields.Selection([
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly'),
            ], 'Frequency',
        required=True,
        states={
            'readonly': (Eval('lines', [0]) | (Eval('state') != 'draft')),
            },
        depends=['state'])
    state = fields.Selection([
            ('draft', 'Draft'),
            ('running', 'Running'),
            ('closed', 'Closed'),
            ], 'State', readonly=True)
    lines = fields.One2Many('account.asset.line', 'asset', 'Lines',
        readonly=True)
    move = fields.Many2One('account.move', 'Account Move', readonly=True)
    update_moves = fields.Many2Many('account.asset-update-account.move',
        'asset', 'move', 'Update Moves', readonly=True,
        states={
            'invisible': ~Eval('update_moves'),
            })
    comment = fields.Text('Comment')

    @classmethod
    def __setup__(cls):
        super(Asset, cls).__setup__()
        cls._sql_constraints = [
            ('invoice_line_uniq', 'UNIQUE(supplier_invoice_line)',
                'Supplier Invoice Line can be used only once on asset!'),
            ]
        cls._error_messages.update({
                'delete_draft': 'Asset "%s" must be in draft to be deleted!',
                })
        cls._transitions |= set((
                ('draft', 'running'),
                ('running', 'closed'),
                ))
        cls._buttons.update({
                'run': {
                    'invisible': Eval('state') != 'draft',
                    },
                'close': {
                    'invisible': Eval('state') != 'running',
                    },
                'create_lines': {
                    'invisible': (Eval('lines', [])
                        | (Eval('state') != 'draft')),
                    },
                'clear_lines': {
                    'invisible': (~Eval('lines', [0])
                        | (Eval('state') != 'draft')),
                    },
                'update': {
                    'invisible': Eval('state') != 'running',
                    },
                })

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_frequency():
        return 'monthly'

    @staticmethod
    def default_depreciation_method():
        return 'linear'

    @staticmethod
    def default_start_date():
        return Pool().get('ir.date').today()

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_account_journal():
        Journal = Pool().get('account.journal')
        journals = Journal.search([
                ('type', '=', 'asset'),
                ])
        if len(journals) == 1:
            return journals[0].id
        return None

    def on_change_with_currency_digits(self, name=None):
        if self.company:
            return self.company.currency.digits
        return 2

    def on_change_supplier_invoice_line(self):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Unit = Pool().get('product.uom')

        new_values = {}
        if not self.supplier_invoice_line:
            new_values['quantity'] = None
            new_values['value'] = None
            new_values['start_date'] = self.default_start_date()
            return new_values

        invoice_line = self.supplier_invoice_line
        invoice = invoice_line.invoice
        if invoice.company.currency != invoice.currency:
            with Transaction().set_context(date=invoice.currency_date):
                new_values['value'] = Currency.compute(
                    invoice.company.currency, invoice_line.amount,
                    invoice.currency)
        else:
            new_values['value'] = invoice_line.amount
        new_values['purchase_date'] = invoice.invoice_date
        new_values['start_date'] = invoice.invoice_date
        if invoice_line.product.depreciation_duration:
            duration = relativedelta.relativedelta(
                months=int(invoice_line.product.depreciation_duration),
                days=-1)
            new_values['end_date'] = new_values['start_date'] + duration

        if not self.unit:
            new_values['quantity'] = invoice_line.quantity
            return new_values

        new_values['quantity'] = Unit.compute_qty(invoice_line.unit,
            invoice_line.quantity, self.unit)

        return new_values

    def on_change_with_unit(self):
        if not self.product:
            return None
        return self.product.default_uom.id

    def on_change_with_unit_digits(self, name=None):
        if not self.unit:
            return 2
        return self.unit.digits

    def on_change_with_end_date(self):
        if all(getattr(self, k, None) for k in ('product', 'start_date')):
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
        lines = [line.accumulated_depreciation for line in self.lines
            if line.move and line.move.state == 'posted']
        return max(lines) if lines else 0

    def compute_move_dates(self):
        """
        Returns all the remaining dates at which asset depreciation movement
        will be issued.
        """
        start_date = max([self.start_date] + [l.date for l in self.lines])
        delta = relativedelta.relativedelta(self.end_date, start_date)
        # dateutil >= 2.0 has replace __nonzero__ by __bool__ which doesn't
        # work in Python < 3
        if delta == relativedelta.relativedelta():
            return []
        if self.frequency == 'monthly':
            rule = rrule.rrule(rrule.MONTHLY, dtstart=self.start_date,
                bymonthday=-1)
        elif self.frequency == 'yearly':
            rule = rrule.rrule(rrule.YEARLY, dtstart=self.start_date,
                bymonth=12, bymonthday=-1)
        dates = [d.date()
            for d in rule.between(date2datetime(start_date),
                date2datetime(self.end_date))]
        dates.append(self.end_date)
        return dates

    def compute_depreciation(self, date, dates):
        """
        Returns the depreciation amount for an asset on a certain date.
        """
        amount = (self.value - self.get_depreciated_amount()
            - self.residual_value)
        if self.depreciation_method == 'linear':
            start_date = max([self.start_date
                    - relativedelta.relativedelta(days=1)]
                + [l.date for l in self.lines])
            first_delta = dates[0] - start_date
            last_delta = dates[-1] - dates[-2]
            if self.frequency == 'monthly':
                _, first_ndays = calendar.monthrange(
                    dates[0].year, dates[0].month)
                _, last_ndays = calendar.monthrange(
                    dates[-1].year, dates[-1].month)
            elif self.frequency == 'yearly':
                first_ndays = 365 + calendar.isleap(dates[0].year)
                last_ndays = 365 + calendar.isleap(dates[-1].year)
            first_ratio = Decimal(first_delta.days) / Decimal(first_ndays)
            last_ratio = Decimal(last_delta.days) / Decimal(last_ndays)
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
        amount = (self.value - self.get_depreciated_amount()
            - self.residual_value)
        if amount <= 0:
            return amounts
        residual_value, acc_depreciation = amount, Decimal(0)
        asset_line = None
        for date in dates:
            depreciation = self.compute_depreciation(date, dates)
            with Transaction().set_user(0, set_context=True):
                amounts[date] = asset_line = Line(
                    acquired_value=self.value,
                    depreciable_basis=amount,
                    )
            if depreciation > residual_value:
                asset_line.depreciation = residual_value
                asset_line.accumulated_depreciation = (
                    self.get_depreciated_amount()
                    + acc_depreciation + residual_value)
                break
            else:
                residual_value -= depreciation
                acc_depreciation += depreciation
                asset_line.depreciation = depreciation
                asset_line.accumulated_depreciation = (
                    self.get_depreciated_amount() + acc_depreciation)
        else:
            if residual_value > 0 and asset_line is not None:
                asset_line.depreciation += residual_value
                asset_line.accumulated_depreciation += residual_value
        for asset_line in amounts.itervalues():
            asset_line.actual_value = (self.value -
                asset_line.accumulated_depreciation)
        return amounts

    @classmethod
    @ModelView.button
    def create_lines(cls, assets):
        cls.clear_lines(assets)

        for asset in assets:
            for date, line in asset.depreciate().iteritems():
                line.asset = asset.id
                line.date = date
                line.save()

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
        with Transaction().set_user(0, set_context=True):
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
        cursor = Transaction().cursor

        moves = []
        lines = []
        for i in range(0, len(assets), cursor.IN_MAX):
            asset_ids = [a.id for a in assets[i:i + cursor.IN_MAX]]
            lines += Line.search([
                    ('asset', 'in', asset_ids),
                    ('date', '<=', date),
                    ('move', '=', None),
                    ])
        for line in lines:
            move = line.asset.get_move(line)
            move.save()
            moves.append(move)
            Line.write([line], {
                    'move': move.id,
                    })
        with Transaction().set_user(0, set_context=True):
            Move.post(moves)

    def get_closing_move(self, account):
        """
        Returns closing move values.
        """
        pool = Pool()
        Period = pool.get('account.period')
        Date = pool.get('ir.date')
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')

        date = Date.today()
        period_id = Period.find(self.company.id, date)
        if self.supplier_invoice_line:
            account_asset = self.supplier_invoice_line.account
        else:
            account_asset = self.product.account_asset_used

        with Transaction().set_user(0, set_context=True):
            asset_line = MoveLine(
                debit=0,
                credit=self.value,
                account=account_asset,
                )
            depreciation_line = MoveLine(
                debit=self.get_depreciated_amount(),
                credit=0,
                account=self.product.account_depreciation_used,
                )
        lines = [asset_line, depreciation_line]
        square_amount = asset_line.credit - depreciation_line.debit
        if square_amount:
            if not account:
                account = self.product.account_revenue_used
            with Transaction().set_user(0, set_context=True):
                counter_part_line = MoveLine(
                    debit=square_amount if square_amount > 0 else 0,
                    credit=-square_amount if square_amount < 0 else 0,
                    account=account,
                    )
            lines.append(counter_part_line)
        with Transaction().set_user(0, set_context=True):
            return Move(
                origin=self,
                period=period_id,
                journal=self.account_journal,
                date=date,
                lines=lines,
                )

    @classmethod
    def set_reference(cls, assets):
        '''
        Fill the reference field with asset sequence.
        '''
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('account.configuration')

        config = Config(1)
        for asset in assets:
            if asset.reference:
                continue
            reference = Sequence.get_id(config.asset_sequence.id)
            cls.write([asset], {
                    'reference': reference,
                    })

    @classmethod
    @ModelView.button
    @Workflow.transition('running')
    def run(cls, assets):
        cls.set_reference(assets)
        cls.create_lines(assets)

    @classmethod
    @ModelView.button
    @Workflow.transition('closed')
    def close(cls, assets, account=None):
        """
        Close the assets.
        If account is provided, it will be used instead of the expense account.
        """
        Move = Pool().get('account.move')

        cls.clear_lines(assets)
        moves = []
        for asset in assets:
            move = asset.get_closing_move(account)
            move.save()
            moves.append(move)
            cls.write([asset], {
                    'move': move.id,
                    })
        with Transaction().set_user(0, set_context=True):
            Move.post(moves)

    def get_rec_name(self, name):
        return '%s - %s' % (self.reference, self.product.rec_name)

    @classmethod
    def search_rec_name(cls, name, clause):
        names = clause[2].split(' - ', 1)
        res = [('reference', clause[1], names[0])]
        if len(names) != 1 and names[1]:
            res.append(('product', clause[1], names[1]))
        return res

    @classmethod
    def copy(cls, assets, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default.setdefault('lines', [])
        default.setdefault('state', 'draft')
        default.setdefault('reference', None)
        default.setdefault('supplier_invoice_line', None)
        return super(Asset, cls).copy(assets, default=default)

    @classmethod
    def delete(cls, assets):
        for asset in assets:
            if asset.state != 'draft':
                cls.raise_user_error('delete_draft', asset.rec_name)
        return super(Asset, cls).delete(assets)


class AssetLine(ModelSQL, ModelView):
    'Asset Line'
    __name__ = 'account.asset.line'
    asset = fields.Many2One('account.asset', 'Asset', required=True,
        ondelete='CASCADE')
    date = fields.Date('Date')
    depreciation = fields.Numeric('Depreciation',
        digits=(16, Eval('_parent_asset', {}).get('currency_digits', 2)),
        required=True)
    acquired_value = fields.Numeric('Acquired Value')
    depreciable_basis = fields.Numeric('Depreciable Basis')
    actual_value = fields.Numeric('Actual Value')
    accumulated_depreciation = fields.Numeric('Accumulated Depreciation')
    move = fields.Many2One('account.move', 'Account Move', readonly=True)

    @classmethod
    def __setup__(cls):
        super(AssetLine, cls).__setup__()
        cls._order.insert(0, ('date', 'ASC'))


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
        assets = Asset.search([
                ('state', '=', 'running'),
                ])
        Asset.create_moves(assets, self.start.date)
        return 'end'


class UpdateAssetStart(ModelView):
    'Update Asset Start'
    __name__ = 'account.asset.update.start'
    value = fields.Numeric('Asset Value', required=True)
    residual_value = fields.Numeric('Residual Value', required=True)
    end_date = fields.Date('End Date', required=True)


class UpdateAssetShowDepreciation(ModelView):
    'Update Asset Show Depreciation'
    __name__ = 'account.asset.update.show_depreciation'
    amount = fields.Numeric('Amount', readonly=True)
    date = fields.Date('Date', required=True)
    depreciation_account = fields.Many2One('account.account',
        'Depreciation Account', readonly=True)
    counterpart_account = fields.Many2One('account.account',
        'Counterpart Account')


class UpdateAsset(Wizard):
    'Update Asset'
    __name__ = 'account.asset.update'
    start = StateView('account.asset.update.start',
        'account_asset.asset_update_start_view_form', [
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
        Asset = Pool().get('account.asset')
        asset = Asset(Transaction().context['active_id'])
        return {
            'value': asset.value,
            'residual_value': asset.residual_value,
            'end_date': asset.end_date,
            }

    def transition_update_asset(self):
        Asset = Pool().get('account.asset')
        asset = Asset(Transaction().context['active_id'])
        if self.start.value != asset.value:
            return 'show_move'
        return 'create_lines'

    def default_show_move(self, fields):
        Asset = Pool().get('account.asset')
        asset = Asset(Transaction().context['active_id'])
        return {
            'amount': self.start.value - asset.value,
            'date': datetime.date.today(),
            'depreciation_account': asset.product.account_depreciation_used.id,
            'counterpart_account': asset.product.account_expense_used.id,
            }

    def get_move(self, asset):
        pool = Pool()
        Period = pool.get('account.period')
        Move = pool.get('account.move')
        period_id = Period.find(asset.company.id, self.show_move.date)
        return Move(
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
        Asset = pool.get('account.asset')

        asset = Asset(Transaction().context['active_id'])
        move = self.get_move(asset)
        move.lines = self.get_move_lines(asset)
        move.save()
        Asset.write([asset], {
                'update_moves': [('add', [move.id])],
                })
        Move.post([move])
        return 'create_lines'

    def transition_create_lines(self):
        Asset = Pool().get('account.asset')

        asset = Asset(Transaction().context['active_id'])
        Asset.write([asset], {
                'value': self.start.value,
                'residual_value': self.start.residual_value,
                'end_date': self.start.end_date,
                })
        Asset.create_lines([asset])
        return 'end'
