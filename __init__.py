# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .fiscalyear import *
from .account import *
from .configuration import *
from .period import *
from .journal import *
from .move import *
from .move_template import *
from .tax import *
from .party import *


def register():
    Pool.register(
        FiscalYear,
        FiscalYearLine,
        BalanceNonDeferralStart,
        TypeTemplate,
        Type,
        AccountTemplate,
        AccountTemplateTaxTemplate,
        Account,
        AccountDeferral,
        AccountTax,
        OpenChartAccountStart,
        GeneralLedgerAccount,
        GeneralLedgerAccountContext,
        GeneralLedgerLine,
        GeneralLedgerLineContext,
        BalanceSheetContext,
        IncomeStatementContext,
        CreateChartStart,
        CreateChartAccount,
        CreateChartProperties,
        UpdateChartStart,
        UpdateChartSucceed,
        AgedBalanceContext,
        AgedBalance,
        Configuration,
        ConfigurationDefaultAccount,
        Period,
        JournalType,
        Journal,
        JournalSequence,
        JournalAccount,
        JournalCashContext,
        JournalPeriod,
        Move,
        Reconciliation,
        ConfigurationTaxRounding,
        Line,
        OpenJournalAsk,
        ReconcileLinesWriteOff,
        ReconcileShow,
        CancelMovesDefault,
        PrintGeneralJournalStart,
        TaxGroup,
        TaxCodeTemplate,
        TaxCode,
        OpenChartTaxCodeStart,
        TaxTemplate,
        Tax,
        TaxLine,
        TaxRuleTemplate,
        TaxRule,
        TaxRuleLineTemplate,
        TaxRuleLine,
        TestTaxView,
        TestTaxViewResult,
        MoveTemplate,
        MoveTemplateKeyword,
        MoveLineTemplate,
        TaxLineTemplate,
        CreateMoveTemplate,
        CreateMoveKeywords,
        Party,
        PartyAccount,
        module='account', type_='model')
    Pool.register(
        OpenType,
        BalanceNonDeferral,
        OpenChartAccount,
        CreateChart,
        UpdateChart,
        OpenJournal,
        OpenAccount,
        ReconcileLines,
        UnreconcileLines,
        Reconcile,
        CancelMoves,
        PrintGeneralJournal,
        CreateMove,
        OpenChartTaxCode,
        OpenTaxCode,
        TestTax,
        PartyReplace,
        module='account', type_='wizard')
    Pool.register(
        GeneralLedger,
        TrialBalance,
        AgedBalanceReport,
        GeneralJournal,
        module='account', type_='report')
