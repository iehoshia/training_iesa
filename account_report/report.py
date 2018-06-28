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
    ]

__metaclass__ = PoolMeta

class PrintGeneralBalanceStart(ModelView):
    'Print General Balance Start'
    __name__ = 'print.general_balance.start'

    company = fields.Many2One('company.company', "Company", readonly=True,
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
            #('company', '=', Eval('company')),
            #('parent', '=', None),
            ('balance_sheet', '=', True), 
            ],
        depends=['company'])

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')


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
        start_date = Date(start_date.year, start_date.month, start_date.day)
        end_date = Date(end_date.year, end_date.month, end_date.day)
        data = {
            'company': self.start.company.id,
            'account': self.start.account.id,
            'fiscalyear': self.start.fiscalyear.name,
            'start_date': self.start.fiscalyear.start_date,
            'end_date': self.start.fiscalyear.end_date,
            }
        action['pyson_context'] = PYSONEncoder().encode({
                #'company': self.start.company.id,
                'start_date': start_date,
                'end_date': end_date,
                })
        return action, data

class GeneralBalance(Report):
    'General Balance Report'
    __name__ = 'general_balance.report'

    
    @classmethod
    def _get_records(cls, ids, model, data):
        Account = Pool().get('account.account.type')

        account = Account(data['account'])
        accounts = account._get_childs_by_order()

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