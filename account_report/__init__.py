# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .report import *
from .account import * 

def register():
    Pool.register(
        PrintGeneralBalanceStart,
        PrintIncomeStatementStart,
        Type, 
        Template,
        module='account_report', type_='model')
    Pool.register(
        PrintGeneralBalance,
        PrintIncomeStatement,
        module='account_report', type_='wizard')
    Pool.register(
        GeneralBalance,
        IncomeStatement, 
        module='account_report', type_='report')