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

__all__ = [
    'Type',
    'Template',
    ]

class Template(ModelSQL, ModelView):
    'Account Type'
    __name__ = 'account.account.type.template'

    type_display_balance = fields.Selection([('debit','Debit'),
            ('credit','Credit')],
            'Type')

    @staticmethod
    def default_type_display_balance():
        return 'debit'

class Type(ModelSQL, ModelView):
    'Account Type'
    __name__ = 'account.account.type'

    level = fields.Function(fields.Numeric('Level',digits=(2,0)),
        '_get_level')
    custom_amount = fields.Function(fields.Numeric('Custom Amount',
        digits=(2,0)), '_get_custom_amount')
    type_display_balance = fields.Selection([('debit','Debit'),
        ('credit','Credit')],
        'Type')

    def _get_level(self, parent=None): 
        level = 0
        if self.parent:
            level = self.parent.level + 1
        return  level

    def _get_childs_by_order(self, res=None):
        '''Returns the records of all the children computed recursively, and sorted by sequence. Ready for the printing'''
        
        Account = Pool().get('account.account.type')
        
        if res is None: 
            res = []

        childs = Account.search([('parent', '=', self.id)], order=[('sequence','ASC')])
        
        if len(childs)>=1:
            for child in childs:
                res.append(Account(child.id))
                child._get_childs_by_order(res=res)
        return res 

    def _get_custom_amount(self, name):
        amount = 0
        if self.type_display_balance == 'credit':
            amount  = - self.amount
        else:
            amount  = self.amount
        return amount

    @staticmethod
    def default_type_display_balance():
        return 'debit'
