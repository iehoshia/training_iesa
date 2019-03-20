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

__all__ = [
    'CreateAssetStart',
    'CreateAssetForm',
    'CreateAssetEnd',
    'CreateAsset',

    ]  
__metaclass__ = PoolMeta

class CreateAssetStart(ModelSQL, ModelView):
    'Create Asset Start'
    __name__ = 'create.asset.start'

class CreateAssetForm(ModelSQL, ModelView):
    'Create Asset Start'
    __name__ = 'create.asset.form'

    company = fields.Many2One('company.company', 'Company', required=True,
        select=True, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
            readonly=True, )
    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    unit = fields.Many2One('product.uom', 'Unit', ondelete='RESTRICT',
        required=True
        )
    product_account = fields.Many2One('product.category', "Product Category",
        required=True,
        domain=[('company','=',Eval('company')),
            ('is_asset_category','=',True), 
        ],
        depends=[('company')]
        )
 
    accummulated_depreciation_account = fields.Many2One(
        'account.account', "Accumulated Depreciation Account",
        required=False, 
        domain=[
            ('kind', '=', 'other'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    depreciation_account = fields.Many2One(
        'account.account', " Depreciation Account",
        required=False, 
        domain=[
            ('kind', '=', 'expense'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    asset_account  = fields.Many2One(
        'account.account', " Asset Account",
        required=True, 
        domain=[
            ('kind', '=', 'other'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    value = fields.Numeric('Value', digits=(16,2), 
            required=True, 
        )
    residual_value = fields.Numeric('Residual Value', digits=(16,2), 
            required=True, 
        )
    purchase_date = fields.Date('Purchase Date',
        required=True)
    start_date = fields.Date('Start Date', 
        required=True,
        domain=[('start_date', '<=', Eval('end_date', None))],
        depends=['end_date'])
    end_date = fields.Date('End Date',
        required=True,
        domain=[('end_date', '>=', Eval('start_date', None))],
        depends=['start_date'])
    account_journal = fields.Many2One('account.journal', 'Journal',
        domain=[('type', '=', 'asset')],
        required=True)
    created_asset = fields.Many2One('account.asset','Asset',
        domain=[('company','=',Eval('company',-1))]
        )
    created_expense = fields.Many2One('account.iesa.expense', 'Expense',
        domain=[('company','=',Eval('company',-1))]
        )
    cash_journal = fields.Many2One('account.invoice.payment.method', 'Cash Journal',
        domain=[
            ('company', '=', Eval('company')),
            ],
        required=True)
    ticket = fields.Char('Ticket', required=True)
    receipt = fields.Char('Receipt', required=True)
    description = fields.Char('Description', required=True)
    purchase_account = fields.Many2One(
        'account.account', "Purchase Account",
        required=True, 
        domain=[
            ('kind', '=', 'other'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    party = fields.Many2One('party.party','Party',
        required=True, 
        domain=['AND',
            [('company', '=', Eval('context', {}).get('company', -1))],
            [('is_provider','=',True)],
        ],
        help='The party that generate the expense',
    )

    @staticmethod
    def default_purchase_date():
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_unit():
        ProductUom = Pool().get('product.uom')
        units = ProductUom.search([('name', '=', 'Unidad')])
        if len(units) ==1: 
            return units[0].id

    @staticmethod
    def default_account_journal():
        Journal = Pool().get('account.journal')
        journals = Journal.search([
                ('type', '=', 'asset'),
                ])
        if len(journals) == 1:
            return journals[0].id
        return None

    @fields.depends('cash_journal', 'purchase_account',)
    def on_change_cash_journal(self, name=None):
        self.purchase_account = None
        if self.cash_journal: 
            self.purchase_account = self.cash_journal.debit_account.id

    @classmethod
    @ModelView.button_action(
        'account_iesa_asset.act_created_asset')
    def correct(cls, assets):
        pass

class CreateAssetEnd(ModelSQL, ModelView):
    'Create Asset End'
    __name__ = 'create.asset.end'
    company = fields.Many2One('company.company', 'Company', required=True)
    created_asset = fields.Many2One('account.asset','Asset',
        domain=[('company','=',Eval('company',-1))]
        )
    created_expense = fields.Many2One('account.iesa.expense','Expense',
        domain=[('company','=',Eval('company',-1))]
        )
    move = fields.Many2One('account.move','Move',
        domain=[('company','=',Eval('company',-1))]
        )

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

class CreateAsset(Wizard):
    'Create Asset'
    __metaclass__ = PoolMeta
    __name__ = 'create.asset'

    start = StateView('create.asset.start',
        'account_iesa_asset.create_asset_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'asset', 'tryton-ok', default=True),
            ])
    asset = StateView('create.asset.form',
        'account_iesa_asset.create_asset_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'create_asset', 'tryton-ok', default=True),
            ])
    create_asset = StateTransition()
    created = StateView('create.asset.end',
        'account_iesa_asset.create_asset_end_view_form', [
            Button('OK', 'open_created', 'tryton-ok', default=True),
            ])
    open_created = StateAction('account_iesa_asset.act_open_created_asset_tree')
    

    @classmethod
    def __setup__(cls):
        super(CreateAsset, cls).__setup__()
        cls._error_messages.update({
                'missing_account_receivable': ('Missing Account Revenue.'),
                'missing_account_credit': ('Missing Account Credit.'),
                })

    def transition_create_asset(self):
        pool = Pool()
        Company = pool.get('company.company')
        Product = pool.get('product.product')
        ProductTemplate = pool.get('product.template')
        Asset = pool.get('account.asset')
        Expense = pool.get('account.iesa.expense')
        ExpenseLine = pool.get('account.iesa.expense.line') 

        asset_product = Product()
        asset_template = ProductTemplate()
        asset = Asset()

        asset_template.name = self.asset.name 
        asset_template.type = 'assets'
        asset_template.default_uom = self.asset.unit 
        asset_template.list_price = self.asset.value 
        asset_template.depreciable = True
        #asset_template.account_asset = self.asset.depreciation_account
        #asset_template.account_expense = self.asset.depreciation_account
        #asset_template.account_depreciation = self.asset.accummulated_depreciation_account
        asset_template.account_category  = self.asset.product_account
        asset_template.company = self.asset.company
        asset_template.save()

        asset_product.template = asset_template.id 
        asset_product.code = self.asset.code 
        asset_product.save()

        asset.product = asset_product.id
        asset.value = self.asset.value 
        asset.residual_value = self.asset.residual_value
        asset.purchase_date = self.asset.purchase_date
        asset.start_date = self.asset.start_date 
        asset.end_date =self.asset.end_date
        asset.company = self.asset.company.id
        asset.save() 
        
        journal = self.asset.cash_journal.journal.id
        date = self.asset.purchase_date
        amount = self.asset.value
        description = self.asset.description
        ticket = self.asset.ticket
        receipt = self.asset.receipt 
        party = self.asset.party.id 
        account = self.asset.purchase_account.id 
        asset_account = self.asset.asset_account.id 

        lines = []

        expense_line = ExpenseLine(description=description, account=asset_account, party=party, 
            amount=amount)
        lines.append(expense_line)

        expense = Expense(
            journal=journal, amount=amount, date=date, description=description, 
            ticket=ticket, party=party,account=account, receipt=receipt, 
            lines=lines, reference=receipt, 
            )
        expense.save()
        

        if asset and expense:
            self.asset.created_asset = asset.id 
            self.asset.created_expense = expense.id
            return 'created'
        return 'created' 

    def default_created(self, fields):
        return {
            'created_asset': self.asset.created_asset.id,
            'created_expense': self.asset.created_expense.id,
            }
