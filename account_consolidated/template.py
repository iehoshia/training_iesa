# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime
import operator
from functools import wraps

from dateutil.relativedelta import relativedelta
from sql import Column, Null, Window, Literal
from sql.aggregate import Sum, Max
from sql.conditionals import Coalesce, Case

from trytond.model import (
    ModelView, ModelSQL, DeactivableMixin, fields, Unique, sequence_ordered)
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    Button
from trytond.report import Report
from trytond.tools import reduce_ids, grouped_slice
from trytond.pyson import Eval, If, PYSONEncoder, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond import backend

'''__all__ = ['TypeTemplate', 'Type', 'OpenType',
    'AccountTemplate', 'AccountTemplateTaxTemplate',
    'Account', 'AccountDeferral', 'AccountTax',
    'OpenChartAccountStart', 'OpenChartAccount',
    'GeneralLedgerAccount', 'GeneralLedgerAccountContext',
    'GeneralLedgerLine', 'GeneralLedgerLineContext',
    'GeneralLedger', 'TrialBalance',
    'BalanceSheetContext', 'BalanceSheetComparisionContext',
    'IncomeStatementContext',
    'AgedBalanceContext', 'AgedBalance', 'AgedBalanceReport',
    'CreateChartStart', 'CreateChartAccount', 'CreateChartProperties',
    'CreateChart', 'UpdateChartStart', 'UpdateChartSucceed', 'UpdateChart']'''

__all__ = [
            'AccountTypeTemplate',
            'AccountType',
			]

class AccountTypeTemplate(sequence_ordered(), ModelSQL, ModelView):
    'Account Type'
    __name__ = 'account.account.type.template'

    meta_type = fields.Many2One('account.account.meta.type.template','Meta Type Template',
        ondelete="RESTRICT",
        )

    def _get_type_value(self, type=None):
        '''
        Set the values for account creation.
        '''
        res = {}
        if not type or type.name != self.name:
            res['name'] = self.name
        if not type or type.sequence != self.sequence:
            res['sequence'] = self.sequence
        if not type or type.balance_sheet != self.balance_sheet:
            res['balance_sheet'] = self.balance_sheet
        if not type or type.income_statement != self.income_statement:
            res['income_statement'] = self.income_statement
        if not type or type.display_balance != self.display_balance:
            res['display_balance'] = self.display_balance
        if not type or type.meta_type != self.meta_type:
            res['meta_type'] = self.meta_type
        if not type or type.template != self:
            res['template'] = self.id
        return res


class AccountType(ModelSQL, ModelView):
    'Account Type'
    __name__ = 'account.account.type'

    meta_type = fields.Many2One('account.account.meta.type','Meta Type')

    @classmethod
    def get_amount(cls, types, name):
        pool = Pool()
        Account = pool.get('account.account')
        GeneralLedger = pool.get('account.general_ledger.account')

        res = {}
        for type_ in types:
            res[type_.id] = Decimal('0.0')

        childs = cls.search([
                ('parent', 'child_of', [t.id for t in types]),
                ])
        type_sum = {}
        for type_ in childs:
            type_sum[type_.id] = Decimal('0.0')

        start_period_ids = GeneralLedger.get_period_ids('start_%s' % name)
        end_period_ids = GeneralLedger.get_period_ids('end_%s' % name)
        period_ids = list(
            set(end_period_ids).difference(set(start_period_ids)))

        with Transaction().set_context(periods=period_ids):
            accounts = Account.search([
                    ('type', 'in', [t.id for t in childs]),
                    ('kind', '!=', 'view'),
                    ])
        for account in accounts:
            type_sum[account.type.id] += (account.debit - account.credit)

        for type_ in types:
            childs = cls.search([
                    ('parent', 'child_of', [type_.id]),
                    ])
            for child in childs:
                res[type_.id] += type_sum[child.id]
            exp = Decimal(str(10.0 ** -type_.currency_digits))
            res[type_.id] = res[type_.id].quantize(exp)
            if type_.display_balance == 'credit-debit':
                res[type_.id] = - res[type_.id]
        return res
