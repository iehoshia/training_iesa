# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .expense import *
from .configuration import * 

def register():
    Pool.register(
    	Move, 
        Expense, 
        ExpenseLine, 
        ExpenseContext, 
        ExpenseMoveLine, 
        ExpenseMoveReference,
        Configuration,
        ConfigurationSequence,
        module='account_expense', type_='model')
    Pool.register(
        ExpenseReport,
        module='account_expense', type_='report')