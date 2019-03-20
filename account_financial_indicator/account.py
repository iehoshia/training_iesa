# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime
from datetime import datetime
import operator
from functools import wraps
from collections import defaultdict

from dateutil.relativedelta import relativedelta
from sql import Column, Null, Window, Literal
from sql.aggregate import Sum, Max
from sql.conditionals import Coalesce, Case

from trytond.model import (
    ModelSingleton, ModelView, ModelSQL, DeactivableMixin, fields, Unique, sequence_ordered, tree)
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    Button, StateReport
from trytond.report import Report
from trytond.tools import reduce_ids, grouped_slice
from trytond.pyson import Eval, If, PYSONEncoder, Bool, Date
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond import backend
 
__all__ = [
        'AccountTemplate',
        'Account', 
        'ContextAnalyticAccount',
        'ContextAnalyticAccountConsolidated',
        'OpenChartAccount',
        'PrintFinancialIndicatorStart',
        'PrintFinancialIndicator',
        'FinancialIndicator',
        'PrintConsolidatedFinancialIndicatorStart',
        'PrintConsolidatedFinancialIndicator',
        'ConsolidatedFinancialIndicator',
        'CreateChartStart',
        'CreateChartAccount',
        'CreateChart',
        'UpdateChartStart',
        'UpdateChartSucceed',
        'UpdateChart'       
    ]  

def inactive_records(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with Transaction().set_context(active_test=False):
            return func(*args, **kwargs)
    return wrapper

class OpenChartAccount(Wizard):
    'Open Chart of Accounts'
    __name__ = 'financial_indicator.open_chart'

    start = StateView('analytic_account.open_chart.start',
        'analytic_account.open_chart_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction('account_financial_indicator.act_account_tree2')

    def do_open_(self, action):
        action['pyson_context'] = PYSONEncoder().encode({
                'start_date': self.start.start_date,
                'end_date': self.start.end_date,
                }) 
        return action, {}

    def transition_open_(self):
        return 'end'

class Account(DeactivableMixin, ModelSQL, ModelView, tree(separator='\\')):
    'Analytic Account'
    __name__ = 'analytic_account.account'

    template = fields.Many2One('analytic_account.account.template', 'Template')
    is_consolidated = fields.Boolean('Consolidated Indicator')
    is_current_capital = fields.Boolean('Current Capital')
    is_current_asset = fields.Boolean('Current Asset')
    is_recommended_capital = fields.Boolean('Recommended Capital')
    is_cash = fields.Boolean('Cash and Banks')
    is_current_liability = fields.Boolean('Current Liability')
    is_revenue = fields.Boolean('Revenue')
    is_expense = fields.Boolean('Expense')
    financial_indicator = fields.Function(
        fields.Numeric('Financial Indicator',
            digits=(16, Eval('currency_digits', 2))
        ),
        'get_financial_indicator')
    custom_balance = fields.Function(fields.Numeric('Custom Balance',
        digits=(16, Eval('currency_digits', 1)), depends=['currency_digits']),
        'get_custom_balance')

    @classmethod 
    def __setup__(cls): 
        super(Account, cls).__setup__() 
        cls.name.translate=False

    def get_current_capital(self):
        pool = Pool()
        Date = pool.get('ir.date')
        AccountType = pool.get('account.account.type')

        today = Date.today()
        company = Transaction().context.get('company')
        current_capital = current_liability = Decimal('0.0') 

        current_capitals = AccountType.search([('company','=',company),
            ('name','=','1) ACTIVOS CORRIENTES')])
        if len(current_capitals)==1: 
            current_capital = current_capitals[0].amount * Decimal('1.0')

        current_liabilities = AccountType.search([('company','=',company),
            ('name','=','3) PASIVOS CORRIENTES')])
        if len(current_liabilities)==1: 
            current_liability = current_liabilities[0].amount * Decimal('1.0')

        balance = (current_capital - current_liability) * Decimal('1.0')
        return balance

    def get_cash(self):
        pool = Pool()
        Date = pool.get('ir.date')
        AccountType = pool.get('account.account.type')

        today = Date.today()
        company = Transaction().context.get('company')
        balance = Decimal('0.0') 
        transaction = Transaction()
        context = Transaction().context
        total_cash = Decimal('0.0')

        if self.is_consolidated: 
            companies = context.get('companies',[])
            for company in context.get('companies', []):
                with transaction.set_context(company=company['id']):
                    cash = Decimal('0.0')
                    accounts = AccountType.search([('company','=',company['id']),
                        ('name','=','10. Efectivo y Equivalencias de Efectivo')
                        ])
                    if len(accounts)==1: 
                        cash = accounts[0].amount * Decimal('1.0')
                total_cash += cash
            return total_cash
        else: 
            accounts = AccountType.search([('company','=',company),
                ('name','=','10. Efectivo y Equivalencias de Efectivo')])
            if len(accounts)==1: 
                balance = accounts[0].amount * Decimal('1.0')
        return balance

    def get_current_asset(self):
        pool = Pool()
        Date = pool.get('ir.date')
        AccountType = pool.get('account.account.type')

        today = Date.today()
        company = Transaction().context.get('company')

        transaction = Transaction()
        context = Transaction().context
        total_current_asset = current_asset = Decimal('0.0')

        today = Date.today()
        company = Transaction().context.get('company')
        to_date = Transaction().context.get('to_date')

        if self.is_consolidated: 
            companies = context.get('companies',[])
            date = today if to_date is None else to_date
            for company in context.get('companies', []):
                with transaction.set_context(company=company['id'],
                        posted=True, 
                        cumulate=True, 
                        date=date, 
                        to_date=date, 
                        from_date=None):
                    current_asset = Decimal('0.0')
                    current_assets = AccountType.search([('company','=',company['id']),
                        ('name','=','1) ACTIVOS CORRIENTES')
                        ])
                    if len(current_assets)==1: 
                        current_asset = current_assets[0].amount * Decimal('1.0')
                total_current_asset += current_asset
            return total_current_asset
        else: 
            date = today if to_date is None else to_date
            with transaction.set_context(
                    posted=True, 
                    cumulate=True, 
                    date=date, 
                    to_date=date, 
                    from_date=None, 
                    ):
                current_assets = AccountType.search([('company','=',company),
                    ('name','=','1) ACTIVOS CORRIENTES')])
                if len(current_assets)==1: 
                    current_asset = current_assets[0].amount * Decimal('1.0')            
        return current_asset

    def get_current_liability(self):
        pool = Pool()
        Date = pool.get('ir.date')
        AccountType = pool.get('account.account.type')
        today = Date.today()
        liability = Decimal('0.0')
        transaction = Transaction()
        context = Transaction().context
        total_liability = liability = Decimal('0.0')

        company = Transaction().context.get('company')
        to_date = Transaction().context.get('to_date')

        if self.is_consolidated: 
            companies = context.get('companies',[])
            date = today if to_date is None else to_date
            for company in context.get('companies', []):
                with transaction.set_context(company=company['id'],
                        posted=True, 
                        cumulate=True, 
                        date=date, 
                        to_date=date, 
                        from_date=None,
                    ):
                    liability = Decimal('0.0')
                    liabilities = AccountType.search([('company','=',company['id']),
                        ('name','=','3) PASIVOS CORRIENTES')
                        ])
                    if len(liabilities)==1: 
                        liability = liabilities[0].amount * Decimal('1.0')
                total_liability += liability
            return total_liability
        else:
            current_liability = Decimal('0.0') 
            date = today if to_date is None else to_date
            with transaction.set_context(
                    posted=True, 
                    cumulate=True, 
                    date=date, 
                    to_date=date, 
                    from_date=None, 
                    ):
                current_liabilities = AccountType.search([('company','=',company),
                    ('name','=','3) PASIVOS CORRIENTES')])
                if len(current_liabilities)==1: 
                    current_liability = current_liabilities[0].amount * Decimal('1.0')
            
        return current_liability

    def get_revenues(self):
        pool = Pool()
        Date = pool.get('ir.date')
        AccountType = pool.get('account.account.type')
        today = Date.today()
        revenue = Decimal('0.0')
        transaction = Transaction()
        context = Transaction().context
        total_revenue = revenue = Decimal('0.0')

        if self.is_consolidated: 
            companies = context.get('companies',[])
            for company in context.get('companies', []):
                with transaction.set_context(company=company['id']):
                    revenue = Decimal('0.0')
                    revenues = AccountType.search([('company','=',company['id']),
                        ('name','=','INGRESOS FINANCIEROS')
                        ])
                    if len(revenues)==1: 
                        revenue = revenues[0].amount * Decimal('1.0')
                total_revenue += revenue
            return total_revenue
        else: 
            revenue = Decimal('0.0')
            company = Transaction().context.get('company')
            revenues = AccountType.search([('company','=',company),
                ('name','=','INGRESOS FINANCIEROS')])
            if len(revenues)==1: 
                revenue = revenues[0].amount * Decimal('1.0')
        return revenue

    def get_expenses(self):
        pool = Pool()
        Date = pool.get('ir.date')
        AccountType = pool.get('account.account.type')    
        today = Date.today()
        transaction = Transaction()
        context = Transaction().context
        total_expense = expense = Decimal('0.0')

        if self.is_consolidated: 
            companies = context.get('companies',[])
            for company in context.get('companies', []):
                with transaction.set_context(company=company['id']):
                    expense = Decimal('0.0')
                    expenses = AccountType.search([('company','=',company['id']),
                        ('name','=','GASTOS FINANCIEROS')
                        ])
                    if len(expenses)==1: 
                        expense = expenses[0].amount * Decimal('1.0')
                total_expense += expense
            return total_expense
        else:
            company = Transaction().context.get('company')
            expense = Decimal('0.0') 
            expenses = AccountType.search([('company','=',company),
                ('name','=','GASTOS FINANCIEROS')])
            
            if len(expenses)==1: 
                expense = expenses[0].amount * Decimal('1.0')
            
        return expense

    def get_recommended_capital(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Fiscalyear = pool.get('account.fiscalyear')
        Budget = pool.get('account.budget')

        today = Date.today()        

        transaction = Transaction()
        context = Transaction().context
        company = context.get('company')
        balance = Decimal('0.0')

        if self.is_consolidated:
            companies = context.get('companies',[])
            for company in context.get('companies', []):
                total_amount = Decimal('0.0')
                with transaction.set_context(company=company['id']):
                    fiscalyears = Fiscalyear.search([('company','=',company['id']),
                        ('start_date','<=',today),
                        ('end_date','>=',today)])
                    fiscalyear = None 
                    if len(fiscalyears)==1: 
                        fiscalyear = fiscalyears[0].id

                    budgets = Budget.search([('fiscalyear','=',fiscalyear),
                        ('company','=',company['id']),
                        ('parent','=',None)])
                    if len(budgets)==1: 
                        budget = Budget(budgets[0].id)
                        balance += budget.children[1].amount * Decimal('0.15') 
            #balance *= -1
        else:
            fiscalyear = Transaction().context.get('fiscalyear')
            if fiscalyear is not None: 
                fiscalyears = Fiscalyear.search([('company','=',company),
                    ('id','=',fiscalyear) ])
            else:
                fiscalyears = Fiscalyear.search([('company','=',company),
                    ('start_date','<=',today),
                    ('end_date','>=',today)])
                if len(fiscalyears)==1: 
                    fiscalyear = fiscalyears[0].id

            budgets = Budget.search([('fiscalyear','=',fiscalyear),
                ('company','=',company),
                ('parent','=',None)])



            if len(budgets)==1: 
                budget = Budget(budgets[0].id)
                print("BUDGET: ", str(budget))
                balance = budget.children[0].amount * Decimal('0.15') 
                print("BALANCE: ", str(balance))
                #balance *= -1

        return balance

    def get_difference_between_childs(self):
        balance = first_child = second_child = 0 
        if self.childs[0] is not None and self.childs[1] is not None: 
            first_child = self.childs[0].custom_balance  
            second_child = self.childs[1].custom_balance
            balance = first_child - second_child 
        return balance 

    @classmethod
    def get_custom_balance(cls, accounts, name):
        
        balances = {}
        for account in accounts:
            balance = Decimal()
            if account.is_current_capital == True:
                balance = account.get_difference_between_childs()
            elif account.is_recommended_capital == True: 
                balance = account.get_recommended_capital()
            elif account.is_cash == True: 
                balance = account.get_cash()
            elif account.is_current_liability == True: 
                balance = account.get_current_liability()
            elif account.is_current_asset == True: 
                balance = account.get_current_asset()
            elif account.is_revenue == True: 
                balance = account.get_revenues()
            elif account.is_expense == True: 
                balance = account.get_expenses()
            elif account.type == 'root':
                balance = account.get_difference_between_childs()
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
                result[name][account_id] += value
        for account in accounts:
            for name in names:
                exp = Decimal(str(10.0 ** -account.currency_digits))
                result[name][account.id] = (
                    result[name][account.id].quantize(exp))
        return result
    
    def get_financial_indicator(self, name):
        if self.type == 'root':
            first_child = second_child = quotient = 0 
            if self.childs is not None: 
                first_child = Decimal(str(self.childs[0].custom_balance))
                second_child = Decimal(str(self.childs[1].custom_balance))
            if second_child != 0:
                quotient = first_child / second_child * 100
                return quotient
        credit = self.credit if self.credit else 0
        debit = self.debit if self.debit else 0 
        if debit is not 0: 
            return credit / debit 
        return 0

    @staticmethod
    def default_is_consolidated(): 
        return False

    def update_analytic_account(self, template2account=None):
        '''
        Update recursively types based on template.
        template2type is a dictionary with template id as key and type id as
        value, used to convert template id into type. The dictionary is filled
        with new types
        '''
        if template2account is None:
            template2account = {}

        values = []
        childs = [self]
        while childs:
            for child in childs:
                if child.template:
                    vals = child.template._get_account_value()
                    if vals:
                        values.append([child])
                        values.append(vals)
                    template2account[child.template.id] = child.id
            childs = sum((c.childs for c in childs), ())
        if values:
            self.write(*values)

class AccountTemplate(ModelSQL, ModelView):
    'Analytic Account Template'
    __name__ = 'analytic_account.account.template'

    name = fields.Char('Name', required=True, translate=True, select=True)
    code = fields.Char('Code', select=True)
    type = fields.Selection([
        ('root', 'Root'),
        ('view', 'View'),
        ('normal', 'Normal'),
        ('distribution', 'Distribution'),
        ], 'Type', required=True)
    root = fields.Many2One('analytic_account.account.template', 'Root', select=True,
        domain=[
            ('parent', '=', None),
            ('type', '=', 'root'),
            ],
        states={
            'invisible': Eval('type') == 'root',
            'required': Eval('type') != 'root',
            },
        depends=['type'])
    parent = fields.Many2One('analytic_account.account.template', 'Parent', select=True,
        domain=['OR',
            ('root', '=', Eval('root', -1)),
            ('parent', '=', None),
            ],
        states={
            'invisible': Eval('type') == 'root',
            'required': Eval('type') != 'root',
            },
        depends=['root', 'type'])
    childs = fields.One2Many('analytic_account.account.template', 'parent',
        'Children')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('opened', 'Opened'),
        ('closed', 'Closed'),
        ], 'State', required=True)
    display_balance = fields.Selection([
        ('debit-credit', 'Debit - Credit'),
        ('credit-debit', 'Credit - Debit'),
        ], 'Display Balance', required=True)
    mandatory = fields.Boolean('Mandatory', states={
            'invisible': Eval('type') != 'root',
            },
        depends=['type'],
        help="Make this account mandatory when filling documents")
    is_current_capital = fields.Boolean('Current Capital')
    is_current_asset = fields.Boolean('Current Asset')
    is_recommended_capital = fields.Boolean('Recommended Capital')
    is_cash = fields.Boolean('Cash and Banks')
    is_current_liability = fields.Boolean('Current Liability')
    is_revenue = fields.Boolean('Revenue')
    is_expense = fields.Boolean('Expense')

    @classmethod
    def __setup__(cls):
        super(AccountTemplate, cls).__setup__()
        cls._order.insert(0, ('code', 'ASC'))
        cls._order.insert(1, ('name', 'ASC'))

    @staticmethod
    def default_type():
        return 'root'

    @staticmethod
    def default_state():
        return 'draft'

    @fields.depends('parent', 'type',
        '_parent_parent.root', '_parent_parent.type')
    def on_change_parent(self):
        if self.parent and self.type != 'root':
            if self.parent.type == 'root':
                self.root = self.parent
            else:
                self.root = self.parent.root
        else:
            self.root = None

    def _get_account_value(self, account=None):
        '''
        Set the values for account creation.
        '''
        res = {}
        if not account or account.name != self.name:
            res['name'] = self.name
        if not account or account.code != self.code:
            res['code'] = self.code
        if not account or account.type != self.type:
            res['type'] = self.type
        if not account or account.display_balance != self.display_balance:
            res['display_balance'] = self.display_balance
        if not account or account.is_current_capital != self.is_current_capital:
            res['is_current_capital'] = self.is_current_capital
        if not account or account.is_recommended_capital != self.is_recommended_capital:
            res['is_recommended_capital'] = self.is_recommended_capital
        if not account or account.is_current_liability != self.is_current_liability:
            res['is_current_liability'] = self.is_current_liability
        if not account or account.is_current_asset != self.is_current_asset:
            res['is_current_asset'] = self.is_current_asset
        if not account or account.is_cash != self.is_cash:
            res['is_cash'] = self.is_cash
        if not account or account.is_revenue != self.is_revenue:
            res['is_revenue'] = self.is_revenue
        if not account or account.is_expense != self.is_expense:
            res['is_expense'] = self.is_expense


        if not account or account.template != self:
            res['template'] = self.id
        return res

    def create_analytic_account(self, company_id, template2account=None):
        '''
        Create recursively accounts based on template.
        template2account is a dictionary with template id as key and account id
        as value, used to convert template id into account. The dictionary is
        filled with new accounts
        template2type is a dictionary with type template id as key and type id
        as value, used to convert type template id into type.
        '''
        pool = Pool()
        Account = pool.get('analytic_account.account')
        assert self.parent is None

        if template2account is None:
            template2account = {}

        def create(templates):
            values = []
            created = []
            for template in templates:
                if template.id not in template2account:
                    vals = template._get_account_value()
                    vals['company'] = company_id
                    if template.parent:
                        vals['parent'] = template2account[template.parent.id]
                    else:
                        vals['parent'] = None
                    if template.root:
                        vals['root'] = template2account[template.root.id]
                    else:
                        vals['root'] = None                    
                    values.append(vals)
                    created.append(template)
            
            accounts = Account.create(values)
            #print ("ACCOUNTS: ", str(accounts) )
            for template, account in zip(created, accounts):
                #print("TEMPLATE: ", str(template), " ACCOUNT: ", str(account))
                template2account[template.id] = account.id


        childs = [self]
        #print ("CHILDS: ", str(childs))
        while childs:
            create(childs)
            childs = sum((c.childs for c in childs), ())

class ContextAnalyticAccountConsolidated(ModelView):
    'Context Analytic Account Consolidated'
    __name__ = 'analytic_account.consolidated_account.context'

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
    company = fields.Many2One('company.company', "Company", readonly=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    companies = fields.One2Many('company.company','parent','Companies',
        domain=([
            ('parent','child_of',Eval('company')),
            ('type','=','normal')
            ]),
        depends=['company']
        )

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_from_date(cls):
        return datetime.today().replace(day=1,month=1)

    @classmethod
    def default_to_date(cls):
        Date = Pool().get('ir.date')
        return Date.today()

class ContextAnalyticAccount(ModelView):
    'Context Analytic Account'
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
    company = fields.Many2One('company.company', "Company", readonly=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    fiscalyear = fields.Many2One('account.fiscalyear','Fiscal Year',
        domain=[
            ('company', '=', Eval('context', {}).get('company', -1)),
            ],
        )

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_from_date(cls):
        return datetime.today().replace(day=1,month=1)

    @classmethod
    def default_to_date(cls):
        Date = Pool().get('ir.date')
        return Date.today()

    @fields.depends('from_date','to_date','fiscalyear')
    def on_change_fiscalyear(self):
        if self.fiscalyear: 
            self.from_date = self.fiscalyear.start_date
            self.to_date = self.fiscalyear.end_date

class PrintFinancialIndicatorStart(ModelView):
    'Financial Indicator Start'
    __name__ = 'print.financial_indicator.start'

    company = fields.Many2One('company.company', "Company", readonly=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        help="The fiscalyear on which the new created budget will apply.",
        required=False, 
        domain=[
            ('company', '=', Eval('company')),
            ],
        depends=['company'])
    from_date = fields.Date("From Date",
        required=False,
        domain=[
            If(Eval('to_date') & Eval('from_date'),
                ('from_date', '<=', Eval('to_date')),
                ()),
            ],
        depends=['to_date'])
    to_date = fields.Date("To Date",
        required=True,
        domain=[
            If(Eval('from_date') & Eval('to_date'),
                ('to_date', '>=', Eval('from_date')),
                ()),
            ],
        depends=['from_date'])

    @classmethod
    def default_from_date(cls):
        return datetime.today().replace(day=1,month=1)

    @classmethod
    def default_to_date(cls):
        Date = Pool().get('ir.date')
        return Date.today()

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

class PrintFinancialIndicator(Wizard):
    'Financial Indicator Balance'
    __name__ = 'print.financial_indicator'

    start = StateView('print.financial_indicator.start',
        'account_financial_indicator.print_financial_indicator_start_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('financial_indicator.report')

    def do_print_(self, action):
        start_date = self.start.from_date
        end_date = self.start.to_date
        start_date = Date(start_date.year, start_date.month, start_date.day)
        end_date = Date(end_date.year, end_date.month, end_date.day)
        data = {
            'company': self.start.company.id,
            #'fiscalyear': self.start.fiscalyear.name,
            #'fiscalyear_id': self.start.fiscalyear.id,
            'start_date': self.start.from_date,
            'end_date': self.start.to_date,
            }
        action['pyson_context'] = PYSONEncoder().encode({
                #'company': self.start.company.id,
                'start_date': start_date,
                'end_date': end_date,
                })
        return action, data

class FinancialIndicator(Report):
    'Financial Indicator Report'
    __name__ = 'financial_indicator.report'

    @classmethod
    def get_context(cls, records, data):
        report_context = super(FinancialIndicator, cls).get_context(records, data)

        pool = Pool()
        Company = pool.get('company.company')
        Account = pool.get('analytic_account.account')
        company = Company(data['company'])
        capital_operativo = liquidez = sosten_propio = 0 

        with Transaction().set_context(
                company=data['company'],
                date=data['end_date'],
                cumulate=True,
                posted=True, 
                ): 
            accounts = Account.search([('type','=','root'),
                ('company','=',company)])

            if len(accounts)==3: 
                capital_operativo = Account(accounts[0].id)
                liquidez = Account(accounts[1].id)
                sosten_propio = Account(accounts[2].id)

            capital_actual = Account(capital_operativo.childs[0].id)
            capital_recomendado = Account(capital_operativo.childs[1].id)
            
            caja_y_bancos = Account(liquidez.childs[0].id)
            pasivo_corriente = Account(liquidez.childs[1].id)

            activo_corriente = Account(capital_actual.childs[0].id)

            report_context['company'] = company
            report_context['digits'] = company.currency.digits
            #report_context['fiscalyear'] = data['fiscalyear']
            report_context['start_date'] = data['start_date']
            report_context['end_date'] = data['end_date']
            
            report_context['capital_operativo'] = capital_operativo
            report_context['liquidez'] = liquidez
            report_context['sosten_propio'] = sosten_propio

            report_context['capital_actual'] = capital_actual
            report_context['capital_recomendado'] = capital_recomendado

            report_context['caja_y_bancos'] = caja_y_bancos
            report_context['pasivo_corriente'] = pasivo_corriente
            report_context['activo_corriente'] = activo_corriente

            report_context['indice_capital_operativo'] = round(capital_operativo.financial_indicator,2)
            report_context['indice_liquidez'] = round(liquidez.financial_indicator,2)

        with Transaction().set_context(
                company=data['company'],                
                start_date=data['start_date'],
                end_date=data['end_date'],
                cumulate=True,
                posted=True, 
                ): 
            accounts = Account.search([('type','=','root'),
                ('company','=',company)])
            if len(accounts)==3: 
                sosten_propio = Account(accounts[2].id)
            ingresos = Account(sosten_propio.childs[0].id)
            gastos = Account(sosten_propio.childs[1].id)
            report_context['ingresos'] = ingresos
            report_context['gastos'] = gastos
            report_context['indice_sosten_propio'] = round(sosten_propio.financial_indicator,2)
        
        return report_context

class PrintConsolidatedFinancialIndicatorStart(ModelView):
    'Consolidated Financial Indicator Start'
    __name__ = 'print.consolidated_financial_indicator.start'

    company = fields.Many2One('company.company', "Company", readonly=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    companies = fields.One2Many('company.company','parent','Companies',
        domain=([
            ('parent','child_of',Eval('company')),
            ('type','=','normal')
            ]),
        required=True, 
        depends=['company']
        )
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        help="The fiscalyear on which the new created budget will apply.",
        required=False, 
        domain=[
            ('company', '=', Eval('company')),
            ],
        depends=['company'])
    from_date = fields.Date("From Date",
        required=False,
        domain=[
            If(Eval('to_date') & Eval('from_date'),
                ('from_date', '<=', Eval('to_date')),
                ()),
            ],
        depends=['to_date'])
    to_date = fields.Date("To Date",
        required=True,
        domain=[
            If(Eval('from_date') & Eval('to_date'),
                ('to_date', '>=', Eval('from_date')),
                ()),
            ],
        depends=['from_date'])

    @classmethod
    def default_from_date(cls):
        return datetime.today().replace(day=1,month=1)

    @classmethod
    def default_to_date(cls):
        Date = Pool().get('ir.date')
        return Date.today()

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

class PrintConsolidatedFinancialIndicator(Wizard):
    'Consolidated Financial Indicator'
    __name__ = 'print.consolidated_financial_indicator'

    start = StateView('print.consolidated_financial_indicator.start',
        'account_financial_indicator.print_consolidated_financial_indicator_start_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('consolidated_financial_indicator.report')

    def do_print_(self, action):
        start_date = self.start.from_date
        end_date = self.start.to_date
        start_date = Date(start_date.year, start_date.month, start_date.day)
        end_date = Date(end_date.year, end_date.month, end_date.day)
        data = {
            'company': self.start.company.id,
            'companies': [{'id': x.id} for x in self.start.companies],
            #'fiscalyear': self.start.fiscalyear.name,
            #'fiscalyear_id': self.start.fiscalyear.id,
            'start_date': self.start.from_date,
            'end_date': self.start.to_date,
            }
        action['pyson_context'] = PYSONEncoder().encode({
                #'company': self.start.company.id,
                'start_date': start_date,
                'end_date': end_date,
                })
        return action, data

class ConsolidatedFinancialIndicator(Report):
    'Consolidated Financial Indicator Report'
    __name__ = 'consolidated_financial_indicator.report'

    @classmethod
    def get_context(cls, records, data):
        report_context = super(ConsolidatedFinancialIndicator, cls).get_context(records, data)

        pool = Pool()
        Company = pool.get('company.company')
        Account = pool.get('analytic_account.account')
        company = Company(data['company'])
        capital_operativo = liquidez = sosten_propio = 0 

        with Transaction().set_context(
                #company=data['company'],
                date=data['end_date'],
                companies=data['companies'],
                cumulate=True,
                posted=True, 
                ): 
            accounts = Account.search([
                ('type','=','root'),
                #('company','=',company)
                ])

            if len(accounts)==3: 
                capital_operativo = Account(accounts[0].id)
                liquidez = Account(accounts[1].id)
                sosten_propio = Account(accounts[2].id)

            capital_actual = Account(capital_operativo.childs[0].id)
            capital_recomendado = Account(capital_operativo.childs[1].id)
            
            caja_y_bancos = Account(liquidez.childs[0].id)
            pasivo_corriente = Account(liquidez.childs[1].id)

            activo_corriente = Account(capital_actual.childs[0].id)

            report_context['company'] = company
            report_context['digits'] = company.currency.digits
            #report_context['fiscalyear'] = data['fiscalyear']
            report_context['start_date'] = data['start_date']
            report_context['end_date'] = data['end_date']
            
            report_context['capital_operativo'] = capital_operativo
            report_context['liquidez'] = liquidez
            report_context['sosten_propio'] = sosten_propio

            report_context['capital_actual'] = capital_actual
            report_context['capital_recomendado'] = capital_recomendado

            report_context['caja_y_bancos'] = caja_y_bancos
            report_context['pasivo_corriente'] = pasivo_corriente
            report_context['activo_corriente'] = activo_corriente

            report_context['indice_capital_operativo'] = round(capital_operativo.financial_indicator,2)
            report_context['indice_liquidez'] = round(liquidez.financial_indicator,2)

        with Transaction().set_context(
                #company=data['company'],                
                start_date=data['start_date'],
                end_date=data['end_date'],
                cumulate=True,
                posted=True, 
                companies=data['companies'],
                ): 
            accounts = Account.search([
                ('type','=','root'),
                #('company','=',company)
                ])
            if len(accounts)==3: 
                sosten_propio = Account(accounts[2].id)
            ingresos = Account(sosten_propio.childs[0].id)
            gastos = Account(sosten_propio.childs[1].id)
            report_context['ingresos'] = ingresos
            report_context['gastos'] = gastos
            report_context['indice_sosten_propio'] = round(sosten_propio.financial_indicator,2)
        
        return report_context

class CreateChartStart(ModelView):
    'Create Chart'
    __name__ = 'analytic_account.create_chart.start'

class CreateChartAccount(ModelView):
    'Create Chart'
    __name__ = 'analytic_account.create_chart.account'
    company = fields.Many2One('company.company', 'Company', required=True)

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

class CreateChart(Wizard):
    'Create Chart'
    __name__ = 'analytic_account.create_chart'
    start = StateView('analytic_account.create_chart.start',
        'account_financial_indicator.create_chart_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'account', 'tryton-ok', default=True),
            ])
    account = StateView('analytic_account.create_chart.account',
        'account_financial_indicator.create_chart_account_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_account', 'tryton-ok', default=True),
            ])
    create_account = StateTransition()

    @classmethod
    def __setup__(cls):
        super(CreateChart, cls).__setup__()
        cls._error_messages.update({
                'account_chart_exists': ('A chart of accounts already exists '
                    'for the company "%(company)s".')
                })

    def transition_create_account(self):
        pool = Pool()
        AnalyticAccountTemplate = \
            pool.get('analytic_account.account.template')
        Config = pool.get('ir.configuration')
        Account = pool.get('analytic_account.account')
        
        transaction = Transaction()
        company = self.account.company

        # Skip access rule
        with transaction.set_user(0):
            accounts = Account.search([('company', '=', company.id),
                ('type','=','root'),
                ('parent','=',None),
                ('root','=',None)])

        if len(accounts)>=3:
            self.raise_user_warning('duplicated_chart.%d' % company,
                'account_chart_exists', {
                    'company': company.rec_name,
                    })

        with transaction.set_context(language=Config.get_language(),
                company=company.id):

            # Create analytic plan
            analytic_templates = AnalyticAccountTemplate.search([
                ('type','=','root'),
                ('parent','=',None),
                ('root','=',None)
                ])

            for template in analytic_templates: 
                template2account = {}
                #print ("TEMPLATE: ", str(template))
                template.create_analytic_account(
                    company.id,
                    template2account=template2account, 
                    )
        return 'end'

class UpdateChartStart(ModelView):
    'Update Chart'
    __name__ = 'analytic_account.update_chart.start'
    company = fields.Many2One('company.company', 'Company',
            required=True)

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

class UpdateChartSucceed(ModelView):
    'Update Chart'
    __name__ = 'analytic_account.update_chart.succeed'

class UpdateChart(Wizard):
    'Update Chart'
    __name__ = 'analytic_account.update_chart'
    start = StateView('analytic_account.update_chart.start',
        'account_financial_indicator.update_chart_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Update', 'update', 'tryton-ok', default=True),
            ])
    update = StateTransition()
    succeed = StateView('analytic_account.update_chart.succeed',
        'account_financial_indicator.update_chart_succeed_view_form', [
            Button('OK', 'end', 'tryton-ok', default=True),
            ])

    @inactive_records
    def transition_update(self):
        pool = Pool()
        AnalyticAccount = \
            pool.get('analytic_account.account')
        company = self.start.company

        # Update analytic accounts
        template2analytic_account = {}
        
        analytic_accounts = AnalyticAccount.search([
            ('type','=','root'),
            ('company','=',company.id)])

        #print ("ANALYTIC ACCOUNTS: ", str(analytic_accounts))

        for analytic_account in analytic_accounts:
            analytic_account.update_analytic_account(template2account=template2analytic_account)

            # Create missing accounts
            if analytic_account.template:
                analytic_account.template.create_analytic_account(
                    company.id,
                    template2account=template2analytic_account)

        return 'succeed'