# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import csv
import zipfile
from io import BytesIO, TextIOWrapper
from itertools import groupby

from sql import Null
from sql.aggregate import Min, Sum
from sql.functions import Extract, Round

from trytond.cache import Cache
from trytond.model import (
    Check, DeactivableMixin, Index, ModelSQL, ModelView, Unique, Workflow,
    fields)
from trytond.modules.account.exceptions import FiscalYearNotFoundError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.tools import grouped_slice
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard


class IntrastatTransaction(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'account.stock.eu.intrastat.transaction'
    _rec_name = 'code'

    code = fields.Char("Code", size=2, required=True)
    parent = fields.Many2One(
        'account.stock.eu.intrastat.transaction', "Parent")
    description = fields.Char("Name", translate=True, required=True)

    _code_cache = Cache(
        'account.stock.eu.intrastat.transaction.code', context=False)

    @classmethod
    def get(cls, code, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        if date is None:
            date = Date.today()
        if date.year < 2022:
            code = code[:1]
        transaction_id = cls._code_cache.get(code, -1)
        if transaction_id == -1:
            transactions = cls.search([
                    ('code', '=', code)
                    ], limit=1)
            if transactions:
                transaction, = transactions
                cls._code_cache.set(code, transaction.id)
            else:
                transaction = None
                cls._code_cache.set(code, None)
        elif transaction_id is not None:
            transaction = cls(transaction_id)
        else:
            transaction = None
        return transaction

    @classmethod
    def on_modification(cls, mode, transactions, field_names=None):
        super().on_modification(mode, transactions, field_names=field_names)
        cls._code_cache.clear()


class IntrastatTransport(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'account.stock.eu.intrastat.transport'

    name = fields.Char("Name", translate=True, required=True)
    code = fields.Char("Code", size=2, required=True)


class IntrastatDeclaration(Workflow, ModelSQL, ModelView):
    __name__ = 'account.stock.eu.intrastat.declaration'

    _states = {
        'readonly': Eval('id', -1) >= 0,
        }

    company = fields.Many2One(
        'company.company', "Company", required=True,
        states=_states)
    country = fields.Many2One(
        'country.country', "Country", required=True,
        states=_states)
    month = fields.Date(
        "Month", required=True,
        states=_states)
    state = fields.Selection([
            ('opened', "Opened"),
            ('closed', "Closed"),
            ], "State", readonly=True, required=True, sort=False)

    extended = fields.Function(
        fields.Boolean("Extended"),
        'on_change_with_extended')

    del _states

    _get_cache = Cache(
        'account.stock.eu.intrastat.declaration.get', context=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('company_country_month_unique',
                Unique(t, t.company, t.country, t.month),
                'account_stock_eu'
                '.msg_intrastat_declaration_company_country_month_unique'),
            ('month_first_day', Check(t, Extract('DAY', t.month) == 1),
                'account_stock_eu'
                '.msg_intrastat_declaration_month_first_day'),
            ]
        cls._sql_indexes.add(
            Index(
                t,
                (t.state, Index.Equality(cardinality='low')),
                where=t.state == 'opened'))
        cls._order = [
            ('month', 'DESC'),
            ('company.id', 'DESC'),
            ('country.id', 'DESC'),
            ('id', 'DESC'),
            ]
        cls._transitions |= {
            ('opened', 'closed'),
            ('closed', 'opened'),
            }
        cls._buttons.update({
                'export': {},
                })

    @classmethod
    def default_state(cls):
        return 'opened'

    @fields.depends('company', 'month')
    def on_change_with_extended(self, name=None):
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        if self.company and self.month:
            try:
                fiscalyear = FiscalYear.find(
                    self.company.id,
                    date=self.month)
            except FiscalYearNotFoundError:
                pass
            else:
                return fiscalyear.intrastat_extended

    def get_rec_name(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        return '-'.join([
                self.country.rec_name,
                self.company.rec_name,
                lang.strftime(self.month, '%m/%Y')])

    @classmethod
    def get(cls, company, country, date):
        month = date.replace(day=1)
        key = (company.id, country.id, date)
        declaration = cls._get_cache.get(key)
        if declaration is None:
            declarations = cls.search([
                    ('company', '=', company.id),
                    ('country', '=', country.id),
                    ('month', '=', month),
                    ], limit=1)
            if declarations:
                declaration, = declarations
            else:
                declaration = cls(
                    company=company, country=country, month=month)
                declaration.save()
            cls._get_cache.set(key, declaration.id)
        else:
            declaration = cls(declaration)
        cls.open([declaration])
        return declaration

    @classmethod
    @Workflow.transition('opened')
    def open(cls, declarations):
        pass

    @classmethod
    @Workflow.transition('closed')
    def close(cls, declarations):
        pass

    @classmethod
    @ModelView.button_action(
        'account_stock_eu.wizard_intrastat_declaration_export')
    def export(cls, declarations):
        cls.close(declarations)

    @classmethod
    def on_modification(cls, mode, declarations, field_names=None):
        super().on_modification(mode, declarations, field_names=field_names)
        cls._get_cache.clear()


class IntrastatDeclarationContext(ModelView):
    __name__ = 'account.stock.eu.intrastat.declaration.context'

    company = fields.Many2One('company.company', "Company", required=True)
    declaration = fields.Many2One(
        'account.stock.eu.intrastat.declaration', "Declaration", required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ])

    @classmethod
    def default_company(cls):
        pool = Pool()
        Declaration = pool.get('account.stock.eu.intrastat.declaration')
        declaration = cls.default_declaration()
        if declaration is not None:
            declaration = Declaration(declaration)
            return declaration.company.id
        return Transaction().context.get('company')

    @fields.depends('company', 'declaration')
    def on_change_company(self):
        if not self.company:
            self.declaration = None
        else:
            if self.declaration.company != self.company:
                self.declaration = None

    @classmethod
    def default_declaration(cls):
        return Transaction().context.get('declaration')


class IntrastatDeclarationLine(ModelSQL, ModelView):
    __name__ = 'account.stock.eu.intrastat.declaration.line'

    type = fields.Selection([
            ('arrival', "Arrival"),
            ('dispatch', "Dispatch"),
            ], "Type", sort=False)
    country = fields.Many2One('country.country', "Country")
    subdivision = fields.Many2One('country.subdivision', "Subdivision")
    tariff_code = fields.Many2One('customs.tariff.code', "Tariff Code")
    weight = fields.Float("Weight", digits=(None, 3))
    value = fields.Numeric("Value", digits=(None, 2))
    transaction = fields.Many2One(
        'account.stock.eu.intrastat.transaction', "Transaction")
    additional_unit = fields.Float("Additional Unit", digits=(None, 3))
    country_of_origin = fields.Many2One('country.country', "Country of Origin")
    vat = fields.Many2One(
        'party.identifier', "VAT",
        states={
            'invisible': Eval('type') != 'dispatch',
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ('type', 'ASC'),
            ('country', 'ASC'),
            ('tariff_code', 'ASC'),
            ('transaction', 'ASC'),
            ('country_of_origin', 'ASC'),
            ('vat', 'ASC'),
            ]

    @classmethod
    def view_attributes(cls):
        pool = Pool()
        Declaration = pool.get('account.stock.eu.intrastat.declaration')
        context = Transaction().context
        attributes = super().view_attributes()
        if context.get('declaration') is not None:
            declaration = Declaration(context['declaration'])
            if not declaration.extended:
                attributes.append(
                    ('//field[@name="transport"]|//field[@name="incoterm"]',
                        'tree_invisible', True))
        return attributes

    @classmethod
    def table_query(cls):
        pool = Pool()
        Move = pool.get('stock.move')
        context = Transaction().context

        move = Move.__table__()

        where = move.intrastat_type != Null
        where &= move.state == 'done'
        where &= move.company == context.get('company')
        where &= move.intrastat_declaration == context.get('declaration')

        return (move
            .select(
                Min(move.id).as_('id'),
                *cls._columns(move),
                where=where,
                group_by=cls._group_by(move),
                ))

    @classmethod
    def _columns(cls, move):
        weight_factor = 10 ** cls.weight.digits[1]
        value_precision = cls.value.digits[1]
        additional_unit_factor = 10 ** cls.additional_unit.digits[1]
        return [
            move.intrastat_type.as_('type'),
            move.intrastat_country.as_('country'),
            move.intrastat_subdivision.as_('subdivision'),
            move.intrastat_tariff_code.as_('tariff_code'),
            (Round(Sum(move.internal_weight) * weight_factor)
                / weight_factor).as_('weight'),
            Round(Sum(move.intrastat_value), value_precision).as_('value'),
            move.intrastat_transaction.as_('transaction'),
            (Round(
                    Sum(move.intrastat_additional_unit)
                    * additional_unit_factor)
                / additional_unit_factor).as_('additional_unit'),
            move.intrastat_country_of_origin.as_('country_of_origin'),
            move.intrastat_vat.as_('vat'),
            ]

    @classmethod
    def _group_by(cls, move):
        return [
            move.intrastat_type,
            move.intrastat_country,
            move.intrastat_subdivision,
            move.intrastat_tariff_code,
            move.intrastat_transaction,
            move.intrastat_country_of_origin,
            move.intrastat_vat,
            ]


class IntrastatDeclarationLine_Incoterm(metaclass=PoolMeta):
    __name__ = 'account.stock.eu.intrastat.declaration.line'

    transport = fields.Many2One(
        'account.stock.eu.intrastat.transport', "Transport")
    incoterm = fields.Many2One('incoterm.incoterm', "Incoterm")

    @classmethod
    def _columns(cls, move):
        return super()._columns(move) + [
            move.intrastat_transport.as_('transport'),
            move.intrastat_incoterm.as_('incoterm'),
            ]

    @classmethod
    def _group_by(cls, move):
        return super()._group_by(move) + [
            move.intrastat_transport,
            move.intrastat_incoterm,
            ]


class IntrastatDeclarationExport(Wizard):
    __name__ = 'account.stock.eu.intrastat.declaration.export'
    start_state = 'generate'

    generate = StateTransition()
    result = StateView(
        'account.stock.eu.intrastat.declaration.export.result',
        'account_stock_eu.intrastat_declaration_export_result_view_form', [
            Button("Close", 'end', 'tryton-close'),
            ])

    def transition_generate(self):
        pool = Pool()
        Line = pool.get('account.stock.eu.intrastat.declaration.line')
        declaration = self.record
        with Transaction().set_context(
                company=declaration.company.id,
                declaration=declaration.id):
            lines = Line.search([], order=[('type', 'ASC')])

        content, extension = self.export(lines)
        self.result.file = self.result.__class__.file.cast(content)
        self.result.filename = f'{declaration.rec_name}.{extension}'
        return 'result'

    def export(self, lines):
        country = self.record.country
        method = getattr(
            self, 'export_%s' % country.code.lower(), self.export_fallback)
        return method(lines)

    def export_fallback(self, lines):
        data = BytesIO()
        writer = csv.writer(
            TextIOWrapper(data, encoding='utf-8', write_through=True))
        for line in lines:
            writer.writerow(self.export_fallback_row(line))
        return data.getvalue(), 'csv'

    def export_fallback_row(self, line):
        dispatch = line.type == 'dispatch'
        return [
            line.type,
            line.country.code,
            line.subdivision.intrastat_code,
            line.tariff_code.code,
            round(line.weight, 3),
            round(line.value, 2),
            line.transaction.code,
            line.additional_unit if line.additional_unit is not None else '',
            line.country_of_origin.code
            if dispatch and line.country_of_origin else '',
            line.vat.code if dispatch and line.vat else '',
            ]

    def default_result(self, fields):
        file = self.result.file
        self.result.file = None  # No need to store in session
        return {
            'file': file,
            'filename': self.result.filename,
            }


class IntrastatDeclarationExport_Incoterm(metaclass=PoolMeta):
    __name__ = 'account.stock.eu.intrastat.declaration.export'

    def export_fallback_row(self, line):
        row = super().export_fallback_row(line)
        if self.record.extended:
            row.append(line.transport.code if line.transport else '')
            row.append(line.incoterm.code if line.incoterm else '')
        return row


class IntrastatDeclarationExportResult(ModelView):
    __name__ = 'account.stock.eu.intrastat.declaration.export.result'

    file = fields.Binary("File", readonly=True, filename='filename')
    filename = fields.Char("File Name", readonly=True)


class IntrastatDeclarationExport_BE(metaclass=PoolMeta):
    __name__ = 'account.stock.eu.intrastat.declaration.export'

    def export_be(self, lines):
        data = BytesIO()
        writer = csv.writer(
            TextIOWrapper(data, encoding='utf-8', write_through=True),
            delimiter=';')
        for line in lines:
            writer.writerow(self.export_be_row(line))
        return data.getvalue(), 'csv'

    def export_be_row(self, line):
        dispatch = line.type == 'dispatch'
        type = {
            'arrival': '19',
            'dispatch': '29',
            }[line.type]
        return [
            type,
            line.country.code,
            line.transaction.code,
            line.subdivision.intrastat_code,
            line.tariff_code.code,
            round(line.weight, 2),
            round(line.additional_unit, 2)
            if line.additional_unit is not None else '',
            round(line.value, 2),
            line.country_of_origin.code
            if dispatch and line.country_of_origin else '',
            line.vat.code if dispatch and line.vat else '',
            ]


class IntrastatDeclarationExport_BE_Incoterm(metaclass=PoolMeta):
    __name__ = 'account.stock.eu.intrastat.declaration.export'

    def export_be_row(self, line):
        row = super().export_be_row(line)
        if self.record.extended:
            row.insert(8, line.transport.code if line.transport else '')
            row.insert(9, line.incoterm.code if line.incoterm else '')
        return row


class IntrastatDeclarationExport_ES(metaclass=PoolMeta):
    __name__ = 'account.stock.eu.intrastat.declaration.export'

    def export_es(self, lines):
        data = BytesIO()
        with zipfile.ZipFile(data, 'w') as zip:
            for type, lines in groupby(lines, key=lambda l: l.type):
                for i, lines in enumerate(grouped_slice(lines, 999)):
                    content, extension = self._export_es(lines)
                    filename = f'{type}-{i}.{extension}'
                    zip.writestr(filename, content)
        return data.getvalue(), 'zip'

    def _export_es(self, lines):
        data = BytesIO()
        writer = csv.writer(
            TextIOWrapper(data, encoding='utf-8', write_through=True),
            delimiter=';')
        for line in lines:
            writer.writerow(self.export_es_row(line))
        return data.getvalue(), 'csv'

    def export_es_row(self, line):
        dispatch = line.type == 'dispatch'
        return [
            line.country.code,
            line.subdivision.intrastat_code,
            '',  # incoterm
            line.transaction.code,
            '',  # transport
            '',
            line.tariff_code.code,
            line.country_of_origin.code
            if dispatch and line.country_of_origin else '',
            '',
            round(line.weight, 3),
            round(line.additional_unit, 3)
            if line.additional_unit is not None else '',
            round(line.value, 2),
            round(line.value, 2),
            line.vat.code if dispatch and line.vat else '',
            ]


class IntrastatDeclarationExport_ES_Incoterm(metaclass=PoolMeta):
    __name__ = 'account.stock.eu.intrastat.declaration.export'

    def export_es_row(self, line):
        row = super().export_es_row(line)
        if self.record.extended:
            row[2] = line.incoterm.code if line.incoterm else ''
            row[4] = line.transport.code if line.transport else ''
        return row
