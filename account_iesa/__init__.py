# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .account import *
from .product import * 
from .invoice import * 
from .configuration import * 

def register():
    Pool.register(
        Capital,
        Liquidity,
        Template, 
        Service,
        Move,  
        Account, 
        InvoiceLine,
        Payment, 
        PaymentParty,
        PaymentMoveLine, 
        Configuration, 
        ConfigurationSequence, 
        module='account_iesa', type_='model')
#    Pool.register(
#        CopyBudget,
#        DistributePeriod,
#        module='account_budget', type_='wizard')
    Pool.register(
        AccountMoveReport,
        GeneralLedger,
        module='account_iesa', type_='report')