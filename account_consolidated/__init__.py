# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .account import *
from .template import *

def register():
    Pool.register(
        TypeTemplate,
        Type,
        CreateChartAccount,
    	CreateChartProperties,
    	CreateChartStart,
    	UpdateChartStart,
        UpdateChartSucceed,
        AccountType,
        AccountTypeTemplate,
        ConsolidatedBalanceSheetContext,
        ConsolidatedBalanceSheetComparisionContext,
        GeneralLedgerAccount, 
        CompanyPartyRel, 
        module='account_consolidated', type_='model')
    Pool.register(
        CreateChart,
        UpdateChart,
        module='account', type_='wizard')