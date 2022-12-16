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
        BalanceNonDeferralStart,
        CloseFiscalYearStart,
        TypeTemplate,
        Type,
        AccountTemplate,
        Account,
        AccountDeferral,
        OpenChartAccountStart,
        PrintGeneralLedgerStart,
        PrintTrialBalanceStart,
        OpenBalanceSheetStart,
        OpenIncomeStatementStart,
        CreateChartStart,
        CreateChartAccount,
        CreateChartProperties,
        UpdateChartStart,
        UpdateChartSucceed,
        OpenThirdPartyBalanceStart,
        OpenAgedBalanceStart,
        Configuration,
        Period,
        JournalType,
        JournalView,
        JournalViewColumn,
        Journal,
        JournalPeriod,
        Move,
        Reconciliation,
        Line,
        OpenJournalAsk,
        ReconcileLinesWriteOff,
        ReconcileShow,
        CancelMovesDefault,
        FiscalYearLine,
        FiscalYear2,
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
        AccountTemplateTaxTemplate,
        AccountTemplate2,
        AccountTax,
        Account2,
        MoveTemplate,
        MoveTemplateKeyword,
        MoveLineTemplate,
        TaxLineTemplate,
        CreateMoveTemplate,
        CreateMoveKeywords,
        Party,
        module='account', type_='model')
    Pool.register(
        OpenType,
        BalanceNonDeferral,
        CloseFiscalYear,
        OpenChartAccount,
        PrintGeneralLedger,
        PrintTrialBalance,
        OpenBalanceSheet,
        OpenIncomeStatement,
        CreateChart,
        UpdateChart,
        OpenThirdPartyBalance,
        OpenAgedBalance,
        ClosePeriod,
        ReOpenPeriod,
        CloseJournalPeriod,
        ReOpenJournalPeriod,
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
        module='account', type_='wizard')
    Pool.register(
        GeneralLedger,
        TrialBalance,
        ThirdPartyBalance,
        AgedBalance,
        GeneralJournal,
        module='account', type_='report')
