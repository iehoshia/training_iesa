# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import account 

def register():
    Pool.register(
        account.Account, 
        account.AccountTemplate,
        account.ContextAnalyticAccount, 
        account.ContextAnalyticAccountConsolidated,
        account.PrintFinancialIndicatorStart, 
        account.PrintConsolidatedFinancialIndicatorStart, 
        account.CreateChartStart,
        account.CreateChartAccount,
        account.UpdateChartStart,
        account.UpdateChartSucceed,
        module='account_financial_indicator', type_='model')
    Pool.register(
        account.OpenChartAccount,
        account.PrintFinancialIndicator, 
        account.PrintConsolidatedFinancialIndicator,
        account.CreateChart,
        account.UpdateChart,
        module='account_financial_indicator', type_='wizard')
    Pool.register(
        account.FinancialIndicator, 
        account.ConsolidatedFinancialIndicator,
        module='account_financial_indicator', type_='report')