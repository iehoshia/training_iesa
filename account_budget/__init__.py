# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import budget

def register():
    Pool.register(
        budget.Budget,
        budget.BudgetTemplate, 
        budget.BudgetAccount,
        budget.BudgetPeriod,
        budget.CopyBudgetStart,
        budget.DistributePeriodStart,
        budget.PrintBudgetReportStart, 
        budget.CreateBudgetStart,
        budget.CreateBudgetAccount,
        budget.UpdateBudgetStart,
        budget.UpdateBudgetSucceed,
        module='account_budget', type_='model')
    Pool.register(
        budget.CopyBudget,
        budget.DistributePeriod,
        budget.PrintBudgetReport, 
        budget.CreateBudget,
        budget.UpdateBudget,
        module='account_budget', type_='wizard')
    Pool.register(
        budget.BudgetReport,
        module='account_report', type_='report')