# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime
from datetime import date

import operator
from functools import wraps
from collections import defaultdict

from dateutil.relativedelta import relativedelta
from sql import Column, Null, Window, Literal
from sql.aggregate import Sum, Max
from sql.conditionals import Coalesce, Case

#from trytond.model import (
#    ModelSingleton, ModelView, ModelSQL, DeactivableMixin, fields, Unique,
#    sequence_ordered, tree)
from trytond.model import (ModelSingleton, DeactivableMixin, 
    ModelView, ModelSQL, DeactivableMixin, fields,
    Unique, Workflow, sequence_ordered) 
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    Button
from trytond.report import Report
from trytond.tools import reduce_ids, grouped_slice
from trytond.pyson import Eval, If, PYSONEncoder, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.report import Report


from trytond import backend

from numero_letras import numero_a_moneda

__all__ = ['Capital',
    'Liquidity',
    'Move',
    'Account',
    'AccountMoveReport',
    'Payment',
    'PaymentParty',
    'PaymentMoveLine',
    'GeneralLedger',
    ]  
#__metaclass__ = PoolMeta

_MOVE_STATES = {
    'readonly': Eval('state') == 'posted',
    }
_MOVE_DEPENDS = ['state']

_STATES = {
    'readonly': Eval('state') != 'draft',
}
_DEPENDS = ['state']

_TYPE = [
    ('out', 'Customer'),
    ('in', 'Supplier'),
]

_TYPE2JOURNAL = {
    'out': 'revenue',
    'in': 'expense',
}

_ZERO = Decimal('0.0')

STATES = [
    ('draft', 'Draft'),
    ('posted', 'Posted'),
    ('quotation', 'Quotation'),
    ('cancel', 'Canceled'),
    ]

class Capital(ModelView):
    'Operating Capital'
    __name__ = 'account.operating.capital'

    company = fields.Many2One('company.company','Company')
    current_asset = fields.Many2One('account.account','Current Asset')
    current_asset_amount = fields.Numeric('Amount')
    current_liability = fields.Many2One('account.account','Current Liability')
    current_liability_amount = fields.Numeric('Amount')
    current_capital =fields.Numeric('Current Capital')
    annual_budget = fields.Numeric('Annual Budget')
    recommended_capital = fields.Numeric('Recommended Capital')
    difference = fields.Numeric('Surplus (Deficit)')
    percentage = fields.Char('Percentage')
    fiscalyear = fields.Many2One('account.fiscalyear','Fiscal Year')

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_fiscalyear(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        Fiscalyear = pool.get('account.fiscalyear')
        company = Transaction().context.get('company')
        fiscalyears = Fiscalyear.search([('company','=',company),
            ('start_date','<=',today),
            ('end_date','>=',today)])
        fiscalyear = None 
        if len(fiscalyears)==1: 
            return fiscalyears[0].id

    @classmethod
    def default_annual_budget(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        Fiscalyear = pool.get('account.fiscalyear')
        Budget = pool.get('account.budget')
        company = Transaction().context.get('company')
        fiscalyears = Fiscalyear.search([('company','=',company),
            ('start_date','<=',today),
            ('end_date','>=',today)])
        fiscalyear = None 
        if len(fiscalyears)==1: 
            fiscalyear = fiscalyears[0].id
        budgets = Budget.search([('fiscalyear','=',fiscalyear),
            ('company','=',company)])
        if budgets:
            return Decimal(budgets[0].amount)

    @classmethod
    def default_current_asset(cls):
        Account = Pool().get('account.account')
        company = Transaction().context.get('company')
        accounts = Account.search([('code','=','1'),
            ('company','=',company)])
        if len(accounts) == 1:
            return accounts[0].id

    @classmethod
    def default_current_liability(cls):
        Account = Pool().get('account.account')
        company = Transaction().context.get('company')
        accounts = Account.search([('code','=','3'),
            ('company','=',company)]) 
        if len(accounts) == 1:
            return accounts[0].id

    #@fields.depends('current_asset')
    #def on_change_current_asset(self):
    #    if self.current_asset:
    #        current_asset_amount = Decimal(self.current_asset.balance)
    #        self.current_asset_amount = current_asset_amount
            #if self.current_liability: 
            #    current_liability_amount = Decimal(self.current_liability.balance)
            #    self.difference = current_asset_amount - current_liability_amount

    #@fields.depends('current_liability')
    #def on_change_current_liability(self):
    #    if self.current_liability:
    #        current_liability_amount = Decimal(self.current_liability.balance)
    #        self.current_liability_amount = current_liability_amount
            #self.update_index()
            
            #if self.current_asset: 
            #    current_asset_amount = Decimal(self.current_asset.balance)
            #    self.difference = current_asset_amount + current_liability_amount

    @fields.depends('current_asset','current_liability','annual_budget')
    def on_change_annual_budget(self):

        current_asset_amount = Decimal(self.current_asset.balance or 0 )
        current_liability_amount = Decimal(self.current_liability.balance or 0)
        annual_budget = Decimal(self.annual_budget or 0 )

        current_capital = current_asset_amount + current_liability_amount
        recommended_capital = annual_budget * Decimal('0.15')
        difference = current_capital - recommended_capital
        percentage = 0 
        if recommended_capital != 0:
            percentage = current_capital / recommended_capital  * Decimal('100')

        self.current_asset_amount = current_asset_amount
        self.current_liability_amount = current_liability_amount
        self.current_capital = current_capital
        self.recommended_capital = recommended_capital
        self.difference = difference
        self.percentage = str(percentage) + '%'

class Liquidity(ModelView):
    'Liquidity'
    __name__ = 'account.liquidity'

    company = fields.Many2One('company.company','Company')
    fiscalyear = fields.Many2One('account.fiscalyear','Fiscal Year')
    cash_bank = fields.Numeric('Cash - Bank')
    current_liability = fields.Numeric('Current Liability')
    difference = fields.Numeric('Surplus (Deficit)')
    percentage = fields.Char('Percentage')

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_fiscalyear(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        Fiscalyear = pool.get('account.fiscalyear')
        company = Transaction().context.get('company')
        fiscalyears = Fiscalyear.search([('company','=',company),
            ('start_date','<=',today),
            ('end_date','>=',today)])
        fiscalyear = None 
        if len(fiscalyears)==1: 
            return fiscalyears[0].id

    @classmethod
    def default_cash_bank(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        Fiscalyear = pool.get('account.fiscalyear')
        Account = Pool().get('account.account')
        AccountType = Pool().get('account.account.type')
        
        company = Transaction().context.get('company')
        
        amount = Decimal('0')

        accounts_type_parent = AccountType.search([('parent','=',17),
            ('company','=',company)])

        #print "ACCOUNTS TYPE PARENT: " + str(accounts_type_parent)

        accounts_type = []
        for account in accounts_type_parent: 
            accounts = AccountType.search([
                ('parent','=',account.id),
                ('company','=',company)
                ])
            accounts_type += accounts

        #print "ACCOUNTS TYPE: " + str(accounts_type)

        accounts_account = []
        for account_type in accounts_type:
            #print "ACCOUNTS ACCOUNT: " + str(account_type.sequence)
            accounts = Account.search([
                ('code','=',str(account_type.sequence)),
                ('company','=',company),
                ])
            accounts_account += accounts

        #print "ACCOUNTS ACCOUNT: " + str(accounts_account)

        for account in accounts_account:
            #print "ACCOUNTS CODE: " + str(account.code)
            #print "ACCOUNTS BALANCE: " + str(account.balance)
            amount += Decimal(account.balance)

        return amount 

    @classmethod
    def default_current_liability(cls):
        Account = Pool().get('account.account')
        company = Transaction().context.get('company')
        accounts = Account.search([('code','=','3'),
            ('company','=',company)]) 
        current_liability = None
        if len(accounts) == 1:
            current_liability = Decimal(accounts[0].balance)
            return current_liability

    @fields.depends('cash_bank','current_liability')
    def on_change_cash_bank(self):

        cash_bank = Decimal(self.cash_bank or 0 )
        current_liability = Decimal(self.current_liability or 0)

        difference = cash_bank + current_liability
        
        percentage = 0 
        if current_liability != 0:
            percentage = cash_bank / current_liability * Decimal('100')

        self.cash_bank = cash_bank
        self.current_liability = current_liability
        self.difference = difference
        self.percentage = str(percentage) + '%'

    @fields.depends('current_asset_amount','current_liability_amount', 
        'annual_budget')
    def update_index(self):
        current_asset_amount = Decimal(self.current_asset_amount or 0)
        current_liability_amount = Decimal(self.current_liability_amount or 0)
        annual_budget = Decimal(self.annual_budget or 0)

        current_capital = current_asset_amount - current_liability_amount
        recommended_capital = annual_budget * Decimal('0.15')
        difference = current_capital - recommended_capital
        percentage = 0 
        #if recommended_capital is not 0:
        #    percentage = current_capital / recommended_capital  

        self.current_capital = current_capital
        self.recommended_capital = recommended_capital
        self.difference = difference
        self.percentage = percentage

class Move(ModelSQL, ModelView):
    'Account Move'
    __metaclass__ = PoolMeta
    __name__ = 'account.move'

    is_third_party = fields.Boolean('Party',
        states=_MOVE_STATES, depends=_MOVE_DEPENDS)
    third_party = fields.Char('Party',
        states={
                'readonly': Eval('state') == 'posted',
                'required': Eval('is_third_party', True),
                'invisible': ~Eval('is_third_party', True),
                }, depends=_MOVE_DEPENDS,
        )
    amount = fields.Function(fields.Numeric('Amount',
            digits=(16, 2)),'get_amount')
    amount_in_letters = fields.Function(fields.Numeric('Amount in Letters'),
        'get_amount_in_letters')

    @classmethod
    def _get_origin(cls):
        origins = super(Move, cls)._get_origin()
        origins.append('account.iesa.payment')
        return origins

    def get_amount(self, name):
        amount = Decimal('0.0')
        if self.lines: 
            for line in self.lines: 
                amount += line.debit 
            amount = abs(amount)
            return amount 
        return amount 

    def get_amount_in_letters(self, name):
        amount_in_letters = numero_a_moneda(self.amount)
        return amount_in_letters

    '''class AccountMoveReport(Report):
    __name__ = 'account.move'

    @classmethod
    def __setup__(cls):
        super(InvoiceReport, cls).__setup__()
        cls.__rpc__['execute'] = RPC(False)

    

    @classmethod
    def get_context(cls, records, data):
        context = super(InvoiceReport, cls).get_context(records, data)
        context['invoice'] = context['record']
        return context
    '''

class AnalyticAccountContext(ModelSQL, ModelView):
    'Analytic Account Context'
    __name__ = 'analytic_account.account.context'

    from_date = fields.Date("From Date",
        domain=[
            If(Eval('to_date') & Eval('from_date'),
                ('from_date', '<=', Eval('to_date')),
                ()),
            ],
        depends=['to_date'])
    to_date = fields.Date("To Date",
        domain=[
            If(Eval('from_date') & Eval('to_date'),
                ('to_date', '>=', Eval('from_date')),
                ()),
            ],
        depends=['from_date'])

    @classmethod
    def default_from_date(cls):
        return Transaction().context.get('from_date')

    @classmethod
    def default_to_date(cls):
        return Transaction().context.get('to_date')

class Account(DeactivableMixin, ModelSQL, ModelView):
    'Analytic Account'
    __name__ = 'analytic_account.account'

    is_recommended_capital = fields.Boolean('Recommended Capital')

    financial_indicator = fields.Function(
        fields.Numeric('Financial Indicator',
            digits=(16, Eval('currency_digits', 2))
        ),
        'get_financial_indicator')

    def get_recommended_capital(self):
        #print "LLEGA BUDGETS: " 
        balances = {}
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        Fiscalyear = pool.get('account.fiscalyear')
        Budget = pool.get('account.budget')
        company = Transaction().context.get('company')
        fiscalyears = Fiscalyear.search([('company','=',company),
            ('start_date','<=',today),
            ('end_date','>=',today)])
        fiscalyear = None 
        if len(fiscalyears)==1: 
            fiscalyear = fiscalyears[0].id
        budgets = Budget.search([('fiscalyear','=',fiscalyear),
            ('company','=',company)])
        if budgets:
            balance = budgets[0].amount * Decimal('0.15') / Decimal('12.0')
            return balance
        return 0 

    @classmethod
    def get_balance(cls, accounts, name):
        #print "NO LLEGA BUDGETS: "
        pool = Pool()
        Line = pool.get('analytic_account.line')
        MoveLine = pool.get('account.move.line')
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        line = Line.__table__()
        move_line = MoveLine.__table__()

        ids = [a.id for a in accounts]
        #print "IDS: " + str(ids)
        childs = cls.search([('parent', 'child_of', ids)])
        all_ids = {}.fromkeys(ids + [c.id for c in childs]).keys()

        id2account = {}
        all_accounts = cls.browse(all_ids)
        for account in all_accounts:
            id2account[account.id] = account

        line_query = Line.query_get(line)
        cursor.execute(*table.join(line, 'LEFT',
                condition=table.id == line.account
                ).join(move_line, 'LEFT',
                condition=move_line.id == line.move_line
                ).select(table.id,
                Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0)),
                where=(table.type != 'view')
                & table.id.in_(all_ids)
                & (table.active == True) & line_query,
                group_by=table.id))
        account_sum = defaultdict(Decimal)
        for account_id, value in cursor.fetchall():
            account_sum.setdefault(account_id, Decimal('0.0'))
            # SQLite uses float for SUM
            if not isinstance(value, Decimal):
                value = Decimal(str(value))
            account_sum[account_id] += value

        balances = {}
        for account in accounts:
            balance = Decimal()
            childs = cls.search([
                    ('parent', 'child_of', [account.id]),
                    ])
            for child in childs:
                balance += account_sum[child.id]
            if account.is_recommended_capital == True: 
                balance = account.get_recommended_capital()
            if account.type == 'root':
                first_child = second_child = 0 
                if account.childs is not None: 
                    first_child = account.childs[0].balance  
                    second_child = account.childs[1].balance
                    balance = first_child - second_child 
            if account.display_balance == 'credit-debit' and balance:
                balance *= -1
            exp = Decimal(str(10.0 ** -account.currency_digits))
            balances[account.id] = balance.quantize(exp)
        return balances

    @classmethod
    def get_credit_debit(cls, accounts, names):
        pool = Pool()
        Line = pool.get('analytic_account.line')
        MoveLine = pool.get('account.move.line')
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        line = Line.__table__()
        move_line = MoveLine.__table__()

        result = {}
        ids = [a.id for a in accounts]
        for name in names:
            if name not in ('credit', 'debit'):
                raise Exception('Bad argument')
            result[name] = {}.fromkeys(ids, Decimal('0.0'))

        id2account = {}
        for account in accounts:
            id2account[account.id] = account

        line_query = Line.query_get(line)
        columns = [table.id]
        for name in names:
            columns.append(Sum(Coalesce(Column(line, name), 0)))
        cursor.execute(*table.join(line, 'LEFT',
                condition=table.id == line.account
                ).join(move_line, 'LEFT',
                condition=move_line.id == line.move_line
                ).select(*columns,
                where=(table.type != 'view')
                & table.id.in_(ids)
                & (table.active == True) & line_query,
                group_by=table.id))

        for row in cursor.fetchall():
            account_id = row[0]
            for i, name in enumerate(names, 1):
                value = row[i]
                # SQLite uses float for SUM
                if not isinstance(value, Decimal):
                    value = Decimal(str(value))
                #print "ROW: " + str(row)+ " VALUE: " + str(value)
                result[name][account_id] += value
        for account in accounts:
            for name in names:
                exp = Decimal(str(10.0 ** -account.currency_digits))
                result[name][account.id] = (
                    result[name][account.id].quantize(exp))
        return result
    
    def get_financial_indicator(self, name):
        if self.type == 'root':
            first_child = second_child = 0 
            if self.childs is not None: 
                first_child = self.childs[0].balance  
                #print "FIRSTCHILD: " + str(first_child)
                second_child = self.childs[1].balance
                #print "SECONDCHILD: " + str(second_child)
            if second_child != 0:
                quotient = first_child / second_child * Decimal('100.0')
                #print "QUOTIENT: " + str(quotient) 
                return quotient
        credit = self.credit if self.credit else 0
        debit = self.debit if self.debit else 0 
        if debit is not 0: 
            return credit / debit 
        return 0

class AccountMoveReport(Report):
    __name__ = 'account.move.report'

    @classmethod
    def get_context(cls, records, data):
        pool = Pool()
        Company = pool.get('company.company')
        context = Transaction().context

        report_context = super(AccountMoveReport, cls).get_context(records, data)

        report_context['company'] = Company(context['company'])
        
        report_context['from_date'] = context.get('from_date')
        report_context['to_date'] = context.get('to_date')

        return report_context

class Payment(Workflow, ModelView, ModelSQL):
    'IESA Payment'
    __name__ = 'account.iesa.payment'

    company = fields.Many2One('company.company', 'Company', required=True,
        states=_STATES, select=True, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=_DEPENDS)
    company_party = fields.Function(
        fields.Many2One('party.party', "Company Party"),
        'on_change_with_company_party')
    number = fields.Char('Number', size=None, readonly=False, select=True, 
        required=False)
    reference = fields.Char('Reference', size=None, states=_STATES,
        depends=_DEPENDS)
    description = fields.Char('Description', size=None, states=_STATES,
        depends=_DEPENDS)
    state = fields.Selection(STATES, 'State', readonly=True)
    invoice_date = fields.Date('Payment Date',
        states={
            'readonly': Eval('state').in_(['posted', 'canceled']),
            'required': Eval('state').in_(['draft','posted'],),
            },
        depends=['state'])
    accounting_date = fields.Date('Accounting Date', states=_STATES,
        depends=_DEPENDS)
    party = fields.Many2One('party.party', 'Party',
        required=True, states=_STATES, depends=_DEPENDS,
        domain=['AND', 
                [('is_student', '=', True)],
                [('company', '=', Eval('context', {}).get('company', -1))],
            ]
        )
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
        required=False, states=_STATES, depends=['state', 'party'],
        domain=[('party', '=', Eval('party'))])
    party_lang = fields.Function(fields.Char('Party Language'),
        'on_change_with_party_lang')
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states=_STATES, depends=_DEPENDS)
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    currency_date = fields.Function(fields.Date('Currency Date'),
        'on_change_with_currency_date')
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        states=_STATES, depends=_DEPENDS,
        domain=[('type', '=', 'cash')])
    '''journal_writeoff = fields.Many2One('account.journal', 'Write-Off Journal',
        domain=[
            ('type', '=', 'write-off'),
            ],
        states={
            'invisible': Eval('type') != 'writeoff',
            'required': Eval('type') == 'writeoff',
            }, depends=['type'])'''
    move = fields.Many2One('account.move', 'Move', readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    account = fields.Many2One('account.account', 'Account', required=False,
        states=_STATES, depends=_DEPENDS + ['type', 'company'],
        domain=[
            ('company', '=', Eval('company', -1)),
            ('kind', '=', 'receivable'),
            ])
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', states=_STATES, depends=_DEPENDS)
    #invoices = fields.One2Many('account.invoice', 'party', 'Invoices',
    #    domain=[
    #        ('company', '=', Eval('company', -1)),
    #        ('party', '=', Eval('party', -1)),
    #        ],
    #    states={
    #        'readonly': True,
    #        },
    #    depends=['state', 'company','party'])
    invoices = fields.Many2Many('account.iesa.payment-party.party', 'party', 'invoice',
            'Invoices', help='Invoices registered for users',
            domain=[
                ('company', '=', Eval('company', -1)),
                ('party', '=', Eval('party', -1)),
            ],
            depends=['company','party'],
            readonly=True, 
            )
    amount = fields.Numeric('Amount', digits=(16,
                Eval('currency_digits', 2)), 
                depends=['currency_digits'],
                required=True, 
                states=_STATES, 
                )
    amount_receivable = fields.Numeric('Receivable',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits','party'],
            readonly=False, )
    comment = fields.Text('Comment', states=_STATES, depends=_DEPENDS)
    ticket = fields.Char('Ticket',  states=_STATES, 
        required=True)
    receipt = fields.Char('Receipt')
    third_party = fields.Char('Third Party', 
        required=True, 
        states=_STATES, )
    payment_lines = fields.Many2Many('account.iesa.payment-account.move.line',
        'party', 'line', string='Payment Lines',
        help='Payment Lines for Party',
        domain=[
            ('party', '=', Eval('party', -1)),
            ],
        depends=['company','party'],
        readonly=True, 
        )

    @classmethod
    def __setup__(cls):
        super(Payment, cls).__setup__()
        cls._order = [
            ('number', 'DESC'),
            ('id', 'DESC'),
            ]
        cls._error_messages.update({
                'missing_account_receivable': ('Missing Account Revenue.'),
                'amount_can_not_be_zero': ('Amount to Pay can not be zero.'),
                })
        cls._transitions |= set((
                ('draft', 'canceled'),
                ('draft', 'quotation'),
                ('quotation', 'posted'),
                ('canceled', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'quotation']),
                    'icon': 'tryton-cancel',
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': Eval('state').in_(['draft','posted','canceled']),
                    'icon': If(Eval('state') == 'canceled',
                        'tryton-clear', 'tryton-go-previous'),
                    'depends': ['state'],
                    },
                'quote': {
                    'invisible': Eval('state') != 'draft',
                    'icon': 'tryton-go-next',
                    'depends': ['state'],
                    },
                'post': {
                    'invisible': Eval('state') != 'quotation',
                    'icon': 'tryton-ok',
                    'depends': ['state'],
                    },
                })

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.id

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.digits
        return 2

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def default_payment_term(cls):
        PaymentTerm = Pool().get('account.invoice.payment_term')
        payment_terms = PaymentTerm.search(cls.payment_term.domain)
        if len(payment_terms) == 1:
            return payment_terms[0].id

    @classmethod
    def default_invoice_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    def __get_account_payment_term(self):
        '''
        Return default account and payment term
        '''
        self.account = None
        if self.party:
            if self.type == 'out':
                self.account = self.party.account_receivable_used
                if self.party.customer_payment_term:
                    self.payment_term = self.party.customer_payment_term
            elif self.type == 'in':
                self.account = self.party.account_payable_used
                if self.party.supplier_payment_term:
                    self.payment_term = self.party.supplier_payment_term

    @fields.depends('party', 'payment_term', 'type', 'company','amount_receivable','invoices')
    def on_change_party(self):

        self.invoice_address = None
        self.invoices = None 
        self.amount_receivable = None 
        self.lines = None
        if self.party:
            pool = Pool()
            Invoice = pool.get('account.invoice')
            Line = pool.get('account.move.line')
            start_date = date(date.today().year, 1, 1)
            end_date =  date(date.today().year, 12, 31)

            invoices = Invoice.search([
                    ('party', '=', self.party.id),
                    ('state', '=', 'posted'),
                    ('invoice_date','>=',start_date),
                    ('invoice_date','<=',end_date),
                    ])
            if invoices:
                self.invoices = invoices

            lines = Line.search([
                ('party','=',self.party.id),
                ('state','=','valid'),
                ])
            if lines: 
                self.payment_lines = lines 

            self.invoice_address = self.party.address_get(type='invoice')

            self.amount_receivable =  self.party.receivable
            if self.party.supplier_payment_term:
                self.payment_term = self.party.supplier_payment_term

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @fields.depends('invoice_date')
    def on_change_with_currency_date(self, name=None):
        Date = Pool().get('ir.date')
        return self.invoice_date or Date.today()

    @fields.depends('party')
    def on_change_with_party_lang(self, name=None):
        Config = Pool().get('ir.configuration')
        if self.party:
            if self.party.lang:
                return self.party.lang.code
        return Config.get_language()

    @fields.depends('company')
    def on_change_with_company_party(self, name=None):
        if self.company:
            return self.company.party.id

    @classmethod
    def set_number(cls, payments):
        '''
        Fill the number field with the payment sequence
        '''
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('sale.configuration')

        config = Config(1)
        for payment in payments:
            if payment.number:
                continue
            payment.number = Sequence.get_id(
                config.iesa_payment_sequence.id)
        cls.save(payments)

    @fields.depends('invoice_date')
    def on_change_with_currency_date(self, name=None):
        Date = Pool().get('ir.date')
        return self.invoice_date or Date.today()

    def _pay_invoice_wizard(self, invoice, amount_to_pay):
        PayWizard = Pool().get('account.invoice.pay', type='wizard')
        pool = Pool()
        start = pool.get('account.invoice.pay.start')
        ask = pool.get('account.invoice.pay.ask')
        
        with Transaction().set_context(current_invoice=invoice):
            session_id, _, _ = PayWizard.create()
            pay_wizard = PayWizard(session_id)
            start.journal = self.journal
            start.currency = self.currency 
            start.amount = amount_to_pay
            start.date = self.invoice_date 
            start.description = self.description
            start.third_party = self.description
            start.ticket = self.description
            start.receipt = self.description
            ask.type = 'partial'
            ask.amount = amount_to_pay
            pay_wizard.start = start 
            pay_wizard.ask=ask 
            pay_wizard.transition_choice()
            pay_wizard.transition_pay()
            pay_wizard.do_print_()
            print "PAY: " + str(pay_wizard) 

    def get_move(self, amount):

        pool = Pool()
        Move = pool.get('account.move')    
        Period = pool.get('account.period')
        MoveLine = pool.get('account.move.line')
        AccountConfiguration = pool.get('account.configuration')
        
        journal = self.journal 
        date = self.invoice_date
        party = self.party

        account_config = AccountConfiguration(1)
        default_account_receivable = account_config.get_multivalue('default_account_receivable')
        
        line1 = MoveLine(description=self.description, account=default_account_receivable, party=party)
        line2 = MoveLine(description=self.description)
        lines = [line1, line2]

        #print "LINES: " + str(lines)

        if amount >= 0:
            line1.debit, line1.credit = 0, amount
        else:
            line1.debit, line1.credit = -amount, 0

        line2.debit, line2.credit = line1.credit, line1.debit
        if line2.debit:
            account_journal = 'debit_account'
        else:
            account_journal = 'credit_account'
        line2.account = getattr(journal, account_journal)
        
        if not line2.account:
            self.raise_user_error('missing_%s' % account_journal,
                (journal.rec_name,))

        #print "LINES UPDATED: " + str(lines)
        #for line in lines:

        #    if line.account.party_required:
        #        line.party = self.party

        #print "LINES SECOND UPDATED: " + str(lines)

        period_id = Period.find(self.company.id, date=date)

        move = Move(journal=journal, period=period_id, date=date,
            company=self.company, lines=lines, origin=self)
        move.save()
        Move.post([move])

        return move

    @classmethod
    @ModelView.button
    @Workflow.transition('canceled')
    def cancel(cls, payments):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, payments):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    def quote(cls, payments):
        cls.set_number(payments)

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, payments):
        
        '''
        Adds a payment of amount to an invoice using the journal, date and
        description.
        Returns the payment line.
        '''

        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')
        Invoice = pool.get('account.invoice')
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        for payment in payments: 
            amount = payment.amount
            move = payment.get_move(amount)

            '''receivable = payment.party.receivable
            accumulated_amount = 0
            if receivable <= 0: 
                #print "RECEIVABLE: " + str(receivable)
                move = payment.get_move(amount)
            else:
                if amount >= receivable:
                    difference = 0 
                    for invoice in payment.invoices:
                        current_amount = invoice.amount_to_pay 
                        accumulated_amount += current_amount
                        difference = amount - accumulated_amount
                        move = payment._pay_invoice_wizard(invoice, invoice.amount_to_pay)
                    if difference > 0: 
                        move = payment.get_move(difference)
                else: 
                    accumulated_amount = 0
                    for invoice in payment.invoices: 
                        current_amount = invoice.amount_to_pay
                        accumulated_amount += current_amount
                        difference = amount - current_amount
                        possitive_difference = current_amount - amount 
                        if amount > current_amount:
                            payment._pay_invoice_wizard(invoice, current_amount)
                        else: 
                            payment._pay_invoice_wizard(invoice, amount)
                            break
                        amount -= current_amount
                        difference = amount - accumulated_amount
                        if difference > 0: 
                            move = payment.get_move(difference)'''
            payment.accounting_date = Date.today()
            payment.move = move 
            payment.state = 'posted'
            payment.save()
        
class PaymentParty(ModelSQL):
    'Payment - Party'
    __name__ = 'account.iesa.payment-party.party'
    _table = 'invoice_party_rel'

    invoice = fields.Many2One('account.invoice', 'Invoice', ondelete='CASCADE',
            required=True, select=True)
    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
            required=True, select=True)

class PaymentMoveLine(ModelSQL):
    'Payment - Move Line'
    __name__ = 'account.iesa.payment-account.move.line'
    _table = 'payment_move_line_rel'

    line = fields.Many2One('account.move.line', 'Line', ondelete='CASCADE',
            required=True, select=True)
    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
            required=True, select=True)

class GeneralLedger(Report):
    __name__ = 'account.iesa.report_general_ledger'

    @classmethod
    def get_context(cls, records, data):
        pool = Pool()
        Company = pool.get('company.company')
        Fiscalyear = pool.get('account.fiscalyear')
        Period = pool.get('account.period')
        context = Transaction().context

        report_context = super(GeneralLedger, cls).get_context(records, data)

        report_context['company'] = Company(context['company'])
        report_context['fiscalyear'] = Fiscalyear(context['fiscalyear'])

        for period in ['start_period', 'end_period']:
            if context.get(period):
                report_context[period] = Period(context[period])
            else:
                report_context[period] = None
        report_context['from_date'] = context.get('from_date')
        report_context['to_date'] = context.get('to_date')

        report_context['accounts'] = records

        print "REPORT CONTEXT: " + str(report_context)

        return report_context