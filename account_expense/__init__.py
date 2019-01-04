# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .expense import *
from .configuration import * 
from .party import * 

def register():
    Pool.register(
    	Move, 
        Party, 
        Expense, 
        ExpenseLine, 
        ExpenseContext, 
        ExpenseMoveLine, 
        ExpenseMoveReference,
        Configuration,
        ConfigurationSequence,
        CancelExpensesDefault, 
        module='account_expense', type_='model')
    Pool.register(
        ExpenseReport,
        module='account_expense', type_='report')
    Pool.register(
        CancelExpenses,
        module='account_expense', type_='wizard')