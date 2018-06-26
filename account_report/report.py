# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal, ROUND_DOWN

from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import If, Eval, Bool
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    Button

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
        domain=[
            ('company', '=', Eval('company')),
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
    print_ = StateReport('account.move.general_journal')

    def do_print_(self, action):
        data = {
            'company': self.start.company.id,
            'from_date': self.start.fiscalyear.start_date,
            'to_date': self.start.fiscalyear.end_date,
            }
        action['pyson_context'] = PYSONEncoder().encode({
                'company': self.start.company.id,
                'start_date': self.start.fiscalyear.start_date,
                'end_date': self.start.fiscalyear.end_date,
                })
        return action, data

class GeneralBalance(Report):
    'General Balance Report'
    __name__ = 'print.general_balance.report'

    '''
    @classmethod
    def _get_records(cls, ids, model, data):
        Move = Pool().get('account.account.type')

        clause = [
            ('date', '>=', data['from_date']),
            ('date', '<=', data['to_date']),
            ('period.fiscalyear.company', '=', data['company']),
            ]
        if data['posted']:
            clause.append(('state', '=', 'posted'))
        return Move.search(clause,
                order=[('date', 'ASC'), ('id', 'ASC')])
    '''

    @classmethod
    def get_context(cls, records, data):
        report_context = super(GeneralBalance, cls).get_context(records, data)

        Company = Pool().get('company.company')

        company = Company(data['company'])

        report_context['company'] = company
        report_context['digits'] = company.currency.digits
        report_context['start_date'] = data['start_date']
        report_context['end_date'] = data['end_date']

        return report_context
    '''
