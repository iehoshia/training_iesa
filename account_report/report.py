# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal, ROUND_DOWN

from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import If, Eval, Bool, PYSONEncoder, Date

from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    StateReport, Button
from trytond.report import Report


__all__ = [
    'PrintGeneralBalanceStart',
    'PrintGeneralBalance',
    'GeneralBalance',
    'PrintIncomeStatementStart',
    'PrintIncomeStatement',
    'IncomeStatement',
    ]

__metaclass__ = PoolMeta

class PrintGeneralBalanceStart(ModelView):
    'Print General Balance Start'
    __name__ = 'print.general_balance.start'

    company = fields.Many2One('company.company', "Company", readonly=True,
        required=True, 
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        help="The fiscalyear on which the new created budget will apply.",
        required=True, 
        domain=[
            ('company', '=', Eval('company')),
            ],
        depends=['company'])
    account = fields.Many2One('account.account.type', 'Account Plan',
        help="The account plan for balance.",
        required=True, 
        domain=[
            ('company', '=', Eval('company')),
            ('balance_sheet', '=', True), 
            ],
        depends=['company'])
    omit_zero = fields.Boolean('Omit Zero')

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_omit_zero(cls):
        return True

class PrintGeneralBalance(Wizard):
    'Print General Balance'
    __name__ = 'print.general_balance'

    start = StateView('print.general_balance.start',
        'account_report.print_general_balance_start_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('general_balance.report')

    def do_print_(self, action):
        start_date = self.start.fiscalyear.start_date
        end_date = self.start.fiscalyear.end_date
        fiscalyear = self.start.fiscalyear.id
        start_date = Date(start_date.year, start_date.month, start_date.day)
        end_date = Date(end_date.year, end_date.month, end_date.day)
        data = {
            'company': self.start.company.id,
            'account': self.start.account.id,
            'fiscalyear': self.start.fiscalyear.name,
            'fiscalyear_id': self.start.fiscalyear.id,
            'start_date': self.start.fiscalyear.start_date,
            'end_date': self.start.fiscalyear.end_date,
            'omit_zero': self.start.omit_zero, 
            }
        action['pyson_context'] = PYSONEncoder().encode({
                'company': self.start.company.id,
                'fiscalyear': self.start.fiscalyear.id,
                'start_date': start_date, 
                'end_date': end_date,
                })
        if self.start.fiscalyear:
            action['name'] += ' - %s' % self.start.fiscalyear.rec_name
        return action, data

class GeneralBalance(Report):
    'General Balance Report'
    __name__ = 'general_balance.report'
    
    @classmethod
    def _get_records(cls, ids, model, data):
        Account = Pool().get('account.account.type')
        omit_zero = data['omit_zero']
        with Transaction().set_context(
                #from_date=data['start_date'],
                #to_date=data['end_date'],
                date=data['end_date'],
                company=data['company'],
                fiscalyear=data['fiscalyear_id'],
                cumulate=True,
                posted=True, 
                ): 
            account = Account(data['account'])
            accounts = account._get_childs_by_order()
            accounts_omit_zero = []
            if omit_zero: 
                for account in accounts: 
                    if account.level < 4: 
                        accounts_omit_zero.append(account)
                    elif account.level >=4 and account.amount != 0: 
                        accounts_omit_zero.append(account)
                    #print "ACCOUNT NAME: " + account.name + " ACCOUNT: " + str(account.level)
                return accounts_omit_zero
            return accounts

    @classmethod
    def get_context(cls, records, data):
        report_context = super(GeneralBalance, cls).get_context(records, data)

        Company = Pool().get('company.company')
        company = Company(data['company'])

        report_context['company'] = company
        report_context['digits'] = company.currency.digits
        report_context['fiscalyear'] = data['fiscalyear']
        report_context['start_date'] = data['start_date']
        report_context['end_date'] = data['end_date']

        return report_context

class PrintIncomeStatementStart(ModelView):
    'Income Statement Start'
    __name__ = 'print.income_statement.start'

    company = fields.Many2One('company.company', "Company", readonly=True,
        required=True, 
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        help="The fiscalyear on which the new created budget will apply.",
        required=True, 
        domain=[
            ('company', '=', Eval('company')),
            ],
        depends=['company'])
    account = fields.Many2One('account.account.type', 'Account Plan',
        help="The account plan for balance.",
        required=True, 
        domain=[
            ('company', '=', Eval('company')),
            ('income_statement', '=', True), 
            ],
        depends=['company'])

    omit_zero = fields.Boolean('Omit Zero')

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_omit_zero(cls):
        return True

class PrintIncomeStatement(Wizard):
    'Income Statement Balance'
    __name__ = 'print.income_statement'

    start = StateView('print.income_statement.start',
        'account_report.print_income_statement_start_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('income_statement.report')

    def do_print_(self, action):
        start_date = self.start.fiscalyear.start_date
        end_date = self.start.fiscalyear.end_date
        start_date = Date(start_date.year, start_date.month, start_date.day)
        end_date = Date(end_date.year, end_date.month, end_date.day)
        data = {
            'company': self.start.company.id,
            'account': self.start.account.id,
            'fiscalyear': self.start.fiscalyear.name,
            'start_date': self.start.fiscalyear.start_date,
            'end_date': self.start.fiscalyear.end_date,
            'omit_zero': self.start.omit_zero,
            }
        action['pyson_context'] = PYSONEncoder().encode({
                'company': self.start.company.id,
                'start_date': start_date,
                'end_date': end_date,
                })
        return action, data

class IncomeStatement(GeneralBalance):
    'Income Statement Report'
    __name__ = 'income_statement.report'

    @classmethod
    def _get_records(cls, ids, model, data):
        Account = Pool().get('account.account.type')
        omit_zero = data['omit_zero']
        with Transaction().set_context(
                from_date=data['start_date'],
                to_date=data['end_date'],
                company=data['company'],
                cumulate=True,
                posted=True, 
                ): 
            account = Account(data['account'])
            accounts = account._get_childs_by_order()
            accounts_omit_zero = []
            if omit_zero: 
                for account in accounts: 
                    if account.level < 4: 
                        accounts_omit_zero.append(account)
                    elif account.level >=4 and account.amount != 0: 
                        accounts_omit_zero.append(account)
                    #print "ACCOUNT NAME: " + account.name + " ACCOUNT: " + str(account.level)
                return accounts_omit_zero
            return accounts