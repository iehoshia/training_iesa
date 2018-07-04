# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .budget import *

def register():
    Pool.register(
        Budget,
        BudgetAccount,
        BudgetPeriod,
        CopyBudgetStart,
        DistributePeriodStart,
        PrintBudgetReportStart, 
        module='account_budget', type_='model')
    Pool.register(
        CopyBudget,
        DistributePeriod,
        PrintBudgetReport, 
        module='account_budget', type_='wizard')
    Pool.register(
        BudgetReport,
        module='account_report', type_='report')