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
