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
    account_depreciation = fields.Many2One(
        'account.account', "Account Accumulated Depreciation",
        required=True, 
        domain=[
            ('kind', '=', 'other'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    account_asset = fields.Many2One(
        'account.account', "Account Depreciation ",
        required=True, 
        domain=[
            ('kind', '=', 'expense'),
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

    @classmethod
    @ModelView.button_action(
        'account_iesa_asset.act_created_asset')
    def correct(cls, assets):
        pass

class CreateAssetEnd(ModelSQL, ModelView):
    'Create Asset End'
    __name__ = 'create.asset.end'
    company = fields.Many2One('company.company', 'Company', required=True)
    asset = fields.Many2One('account.asset','Asset',
        domain=[('company','=',Eval('company',-1))]
        )

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_asset():
        asset = Transaction().context.get('created_asset_id')
        if asset: 
            return asset.id 

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
    open_created = StateAction('account_iesa_asset.act_open_created_asset')
    

    @classmethod
    def __setup__(cls):
        super(CreateAsset, cls).__setup__()

    def transition_create_asset(self):
        pool = Pool()
        Company = pool.get('company.company')
        Product = pool.get('product.product')
        ProductTemplate = pool.get('product.template')
        Asset = pool.get('account.asset')

        asset_product = Product()
        asset_template = ProductTemplate()
        asset = Asset()

        asset_template.name = self.asset.name 
        asset_template.type = 'assets'
        asset_template.default_uom = self.asset.unit 
        asset_template.list_price = self.asset.value 
        asset_template.depreciable = True
        asset_template.account_asset = self.asset.account_asset
        asset_template.account_expense = self.asset.account_asset
        asset_template.account_depreciation = self.asset.account_depreciation
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
        asset.save() 

        if asset:
            return 'created'
        return 'created' 

