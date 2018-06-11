# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .account import * 

def register():
    Pool.register(
        AccountTemplate,
        RuleTemplate,
        AnalyticAccountEntryTemplate,
        Account, 
        Rule, 
        AnalyticAccountEntry, 
        CreateChartAccount,
        module='account_financial_indicator', type_='model')
    Pool.register(
        CreateChart,
        UpdateChart,
        module='account_financial_indicator', type_='wizard')