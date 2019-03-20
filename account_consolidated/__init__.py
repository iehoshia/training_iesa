# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .account import *
from .template import *

def register():
    Pool.register(
        Company, 
        TypeTemplate,
        Type,
        CreateChartAccount,
        CreateChartProperties,
        CreateChartStart,
        UpdateChartStart,
        UpdateChartSucceed,
        CreateChartAccountTemplate,
        UpdateChartStartTemplate,
        AccountType,
        AccountTypeTemplate,
        ConsolidatedBalanceSheetContext,
        ConsolidatedBalanceSheetComparisionContext,
        ConsolidatedIncomeStatementContext,
        GeneralLedgerAccount,
        CompanyPartyRel,
        PrintGeneralBalanceStart,
        PrintIncomeStatementStart,
        module='account_consolidated', type_='model')
    Pool.register(
        CreateChart,
        UpdateChart,
        PrintGeneralBalance,
        PrintIncomeStatement,
        CreateChartTemplate, 
        UpdateChartTemplate, 
        module='account_consolidated', type_='wizard')
    Pool.register(
        GeneralBalance,
        IncomeStatement,
        module='account_consolidated', type_='report')