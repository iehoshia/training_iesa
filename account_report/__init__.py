# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .budget import *

def register():
    Pool.register(
        PrintGeneralBalanceStart,
        module='account_report', type_='model')
    Pool.register(
        PrintGeneralBalance,
        module='account_report', type_='wizard')
    Pool.register(
        GeneralBalance,
        module='account_report', type_='report')