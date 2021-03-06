# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .account import *
from .product import * 
from .invoice import * 
from .configuration import * 

def register():
    Pool.register(
        Template, 
        Service,
        Move,  
        MoveLine, 
        GeneralLedgerAccountContext,
        BalanceSheetContext,
        IncomeStatementContext,
        PrintGeneralJournalStart,
        InvoiceLine,
        PaymentParty,
        Payment, 
        PaymentMoveLine, 
        PaymentMoveReference,
        Configuration, 
        ConfigurationSequence, 
        PaymentLine, 
        PaymentContext, 
        GeneralLedgerLine, 
        PrintPaymentReportStart, 
        CancelPaymentsDefault, 
        module='account_iesa', type_='model')
    Pool.register(
        PrintPaymentReportWizard,
        CancelMoves,
        CancelPayments, 
        module='account_budget', type_='wizard')
    Pool.register(
        AccountMoveReport,
        GeneralLedger,
        PaymentReceipt,
        PrintPaymentReport,
        GeneralJournal,
        module='account_iesa', type_='report')