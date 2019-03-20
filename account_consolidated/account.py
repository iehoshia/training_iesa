# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime
from datetime import datetime
import operator
from functools import wraps

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
import json, ast
from json import dumps, loads, JSONEncoder, JSONDecoder
from trytond.report import Report

from .numero_letras import numero_a_moneda

__all__ = [
    'Company',
    'TypeTemplate',
    'Type',
    'CreateChart',
    'CreateChartAccount',
    'CreateChartProperties',
    'CreateChartStart',
    'UpdateChartStart',
    'UpdateChartSucceed',
    'UpdateChart',
    'ConsolidatedBalanceSheetContext',
    'ConsolidatedBalanceSheetComparisionContext',
    'ConsolidatedIncomeStatementContext',
    'GeneralLedgerAccount',
    'CompanyPartyRel',
    'PrintGeneralBalanceStart',
    'PrintGeneralBalance',
    'GeneralBalance',
    'PrintIncomeStatementStart',
    'PrintIncomeStatement',
    'IncomeStatement',
    ]

_MOVE_STATES = {
    'readonly': Eval('state') == 'posted',
    }
_MOVE_DEPENDS = ['state']

__metaclass__ = PoolMeta

def inactive_records(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with Transaction().set_context(active_test=False):
            return func(*args, **kwargs)
    return wrapper

class Company(ModelSQL, ModelView):
    'Company'
    __name__ = 'company.company'
    __metaclass__ = PoolMeta

    type = fields.Selection(
        [('view','View'),
        ('normal','Normal'),],
        'Type')

    @staticmethod
    def default_type():
        return 'normal'

class TypeTemplate(tree(separator='\\'), sequence_ordered(), ModelSQL, ModelView):
    'Account Meta Type Template'
    __name__ = 'account.account.meta.type.template'
    name = fields.Char('Name', required=True)
    parent = fields.Many2One('account.account.meta.type.template', 'Parent',
            ondelete="RESTRICT")
    childs = fields.One2Many('account.account.meta.type.template', 'parent',
        'Children')
    balance_sheet = fields.Boolean('Balance Sheet')
    income_statement = fields.Boolean('Income Statement')
    display_balance = fields.Selection([
        ('debit-credit', 'Debit - Credit'),
        ('credit-debit', 'Credit - Debit'),
        ], 'Display Balance', required=True)
    type_display_balance = fields.Selection([('debit','Debit'),
            ('credit','Credit')],
            'Type')

    #@classmethod
    #def validate(cls, records):
    #    super(TypeTemplate, cls).validate(records)
    #    cls.check_recursion(records, rec_name='name')

    @staticmethod
    def default_balance_sheet():
        return False

    @staticmethod
    def default_income_statement():
        return False

    @staticmethod
    def default_display_balance():
        return 'debit-credit'

    @staticmethod
    def default_type_display_balance():
        return 'debit'

    def get_rec_name(self, name):
        if self.parent:
            return self.parent.get_rec_name(name) + '\\' + self.name
        else:
            return self.name

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
        if not type or type.type_display_balance != self.type_display_balance:
            res['type_display_balance'] = self.type_display_balance
        if not type or type.template != self:
            res['template'] = self.id
        return res

    def create_type(self, company_id, template2type=None):
        '''
        Create recursively types based on template.
        template2type is a dictionary with template id as key and type id as
        value, used to convert template id into type. The dictionary is filled
        with new types.
        '''
        pool = Pool()
        Type = pool.get('account.account.meta.type')
        assert self.parent is None

        if template2type is None:
            template2type = {}

        def create(templates):
            values = []
            created = []
            for template in templates:
                if template.id not in template2type:
                    vals = template._get_type_value()
                    vals['company'] = company_id
                    if template.parent:
                        vals['parent'] = template2type[template.parent.id]
                    else:
                        vals['parent'] = None
                    values.append(vals)
                    created.append(template)

            types = Type.create(values)
            for template, type_ in zip(created, types):
                template2type[template.id] = type_.id

        childs = [self]
        while childs:
            create(childs)
            childs = sum((c.childs for c in childs), ())

class Type(sequence_ordered(), ModelSQL, ModelView, tree(separator='\\') ):
    'Account Meta Type'
    __name__ = 'account.account.meta.type'

    _states = {
        'readonly': (Bool(Eval('template', -1)) &
            ~Eval('template_override', False)),
        }
    name = fields.Char('Name', size=None, required=True, states=_states)
    parent = fields.Many2One('account.account.meta.type', 'Parent',
        ondelete="RESTRICT", states=_states,
        domain=[
            ('company', '=', Eval('company')),
            ],
        depends=['company'])
    childs = fields.One2Many('account.account.meta.type', 'parent', 'Children',
        domain=[
            ('company', '=', Eval('company')),
        ],
        depends=['company'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
            'get_currency_digits')
    amount = fields.Function(fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits']),
        'get_amount')
    amount_cmp = fields.Function(fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits']),
        'get_amount_cmp')
    balance_sheet = fields.Boolean('Balance Sheet', states=_states)
    income_statement = fields.Boolean('Income Statement', states=_states)
    display_balance = fields.Selection([
        ('debit-credit', 'Debit - Credit'),
        ('credit-debit', 'Credit - Debit'),
        ], 'Display Balance', required=True, states=_states)
    company = fields.Many2One('company.company', 'Company', required=True,
            ondelete="RESTRICT")
    template = fields.Many2One('account.account.meta.type.template', 'Template')
    template_override = fields.Boolean('Override Template',
        help="Check to override template definition",
        states={
            'invisible': ~Bool(Eval('template', -1)),
            },
        depends=['template'])
    level = fields.Function(fields.Numeric('Level',digits=(2,0)),
        '_get_level')
    type_display_balance = fields.Selection([('debit','Debit'),
            ('credit','Credit')],
            'Type')
    custom_amount = fields.Function(fields.Numeric('Custom Amount',
        digits=(2,0)), '_get_custom_amount')

    del _states

    def _get_level(self, parent=None):
        level = 0
        if self.parent:
            level = self.parent.level + 1
        return  level

    def _get_custom_amount(self, name):
        amount = 0
        if self.type_display_balance == 'credit':
            amount  = - self.amount
        else:
            amount  = self.amount
        return amount

    def _get_childs_by_order(self, res=None):
        '''Returns the records of all the children computed recursively, and sorted by sequence. Ready for the printing'''

        Account = Pool().get('account.account.meta.type')

        if res is None:
            res = []

        childs = Account.search([('parent', '=', self.id)], order=[('sequence','ASC')])

        if len(childs)>=1:
            for child in childs:
                res.append(Account(child.id))
                child._get_childs_by_order(res=res)
        return res

    #@classmethod
    #def validate(cls, types):
    #    super(Type, cls).validate(types)
    #    cls.check_recursion(types, rec_name='name')

    @staticmethod
    def default_balance_sheet():
        return False

    @staticmethod
    def default_income_statement():
        return False

    @staticmethod
    def default_display_balance():
        return 'debit-credit'

    @staticmethod
    def default_type_display_balance():
        return 'debit'

    @classmethod
    def default_template_override(cls):
        return False

    def get_currency_digits(self, name):
        return self.company.currency.digits

    @classmethod
    def get_amount(cls, types, name):
        pool = Pool()
        Account = pool.get('account.account')
        GeneralLedger = pool.get('account.general_ledger.account')
        transaction = Transaction()
        context = transaction.context

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

        for company in context.get('companies', []):
            with transaction.set_context(company=company['id'],
                    posted=True, cumulate=True):
                accounts = Account.search([
                        ('company', '=', company['id']),
                        ('type.meta_type', 'in', [t.id for t in childs]),
                        ('kind', '!=', 'view'),
                        ])
                for account in accounts:
                    key = account.type.meta_type.id
                    type_sum[key] += (account.debit - account.credit)

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

    @classmethod
    def get_amount_cmp(cls, types, name):
        transaction = Transaction()
        current = transaction.context
        if not current.get('comparison'):
            return dict.fromkeys([t.id for t in types], None)
        new = {}
        for key, value in current.iteritems():
            if key.endswith('_cmp'):
                new[key[:-4]] = value
        with transaction.set_context(new):
            return cls.get_amount(types, name)

    @classmethod
    def view_attributes(cls):
        return [
            ('/tree/field[@name="amount_cmp"]', 'tree_invisible',
                ~Eval('comparison', False)),
            ]

    def get_rec_name(self, name):
        #if self.parent:
        #    return self.parent.get_rec_name(name) + '\\' + self.name
        #else:
        #    return self.name
        return self.name

    @classmethod
    def delete(cls, types):
        types = cls.search([
                ('parent', 'child_of', [t.id for t in types]),
                ])
        super(Type, cls).delete(types)

    def update_type(self, template2type=None):
        '''
        Update recursively types based on template.
        template2type is a dictionary with template id as key and type id as
        value, used to convert template id into type. The dictionary is filled
        with new types
        '''
        if template2type is None:
            template2type = {}

        values = []
        childs = [self]
        while childs:
            for child in childs:
                if child.template and not child.template_override:
                    vals = child.template._get_type_value(type=child)
                    if vals:
                        values.append([child])
                        values.append(vals)
                    template2type[child.template.id] = child.id
            childs = sum((c.childs for c in childs), ())
        if values:
            self.write(*values)

class CreateChart(Wizard):
    'Create Chart'
    __name__ = 'account.meta.create_chart'
    start = StateView('account.meta.create_chart.start',
        'account_consolidated.create_chart_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'account', 'tryton-ok', default=True),
            ])
    account = StateView('account.meta.create_chart.account',
        'account_consolidated.create_chart_account_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_account', 'tryton-ok', default=True),
            ])
    create_account = StateTransition()
    properties = StateView('account.meta.create_chart.properties',
        'account_consolidated.meta.create_chart_properties_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_properties', 'tryton-ok', default=True),
            ])
    create_properties = StateTransition()

    @classmethod
    def __setup__(cls):
        super(CreateChart, cls).__setup__()
        cls._error_messages.update({
                'account_chart_exists': ('A chart of consolidated accounts already exists')
                })

    def transition_create_account(self):
        pool = Pool()
        Config = pool.get('ir.configuration')
        Account = pool.get('account.account.meta.type')
        transaction = Transaction()

        company = self.account.company
        # Skip access rule
        with transaction.set_user(0):
            accounts = Account.search([()])
        if accounts:
            self.raise_user_error('account_chart_exists')

        with transaction.set_context(language=Config.get_language(),
                company=company.id):
            account_template = self.account.account_template

            # Create account types
            template2type = {}
            account_template.create_type(
                company.id,
                template2type=template2type)

        return 'end'

    def default_properties(self, fields):
        return {
            'company': self.account.company.id,
            }

    def transition_create_properties(self):
        pool = Pool()
        Configuration = pool.get('account.configuration')

        with Transaction().set_context(company=self.properties.company.id):
            account_receivable = self.properties.account_receivable
            account_payable = self.properties.account_payable
            config = Configuration(1)
            config.default_account_receivable = account_receivable
            config.default_account_payable = account_payable
            config.save()
        return 'end'

class CreateChartAccount(ModelView):
    'Create Chart'
    __name__ = 'account.meta.create_chart.account'
    company = fields.Many2One('company.company', 'Company', required=True)
    account_template = fields.Many2One('account.account.meta.type.template',
            'Account Template', required=True, domain=[('parent', '=', None)])

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

class CreateChartProperties(ModelView):
    'Create Chart'
    __name__ = 'account.meta.create_chart.properties'
    company = fields.Many2One('company.company', 'Company')
    account_receivable = fields.Many2One('account.account',
            'Default Receivable Account',
            domain=[
                ('kind', '=', 'receivable'),
                ('company', '=', Eval('company')),
            ],
            depends=['company'])
    account_payable = fields.Many2One('account.account',
            'Default Payable Account',
            domain=[
                ('kind', '=', 'payable'),
                ('company', '=', Eval('company')),
            ],
            depends=['company'])

class CreateChartStart(ModelView):
    'Create Chart'
    __name__ = 'account.meta.create_chart.start'

class UpdateChartStart(ModelView):
    'Update Chart'
    __name__ = 'account.meta.update_chart.start'
    account = fields.Many2One('account.account.meta.type', 'Root Account',
            required=True, domain=[('parent', '=', None)])

class UpdateChartSucceed(ModelView):
    'Update Chart'
    __name__ = 'account.meta.update_chart.succeed'

class UpdateChart(Wizard):
    'Update Chart'
    __name__ = 'account.meta.update_chart'
    start = StateView('account.meta.update_chart.start',
        'account_consolidated.update_chart_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Update', 'update', 'tryton-ok', default=True),
            ])
    update = StateTransition()
    succeed = StateView('account.meta.update_chart.succeed',
        'account_consolidated.update_chart_succeed_view_form', [
            Button('OK', 'end', 'tryton-ok', default=True),
            ])

    @inactive_records
    def transition_update(self):
        pool = Pool()
        TaxCode = pool.get('account.tax.code')
        TaxCodeTemplate = pool.get('account.tax.code.template')
        TaxCodeLine = pool.get('account.tax.code.line')
        TaxCodeLineTemplate = pool.get('account.tax.code.line.template')
        Tax = pool.get('account.tax')
        TaxTemplate = pool.get('account.tax.template')
        TaxRule = pool.get('account.tax.rule')
        TaxRuleTemplate = pool.get('account.tax.rule.template')
        TaxRuleLine = pool.get('account.tax.rule.line')
        TaxRuleLineTemplate = \
            pool.get('account.tax.rule.line.template')

        account = self.start.account
        company = account.company

        # Update account types
        template2type = {}
        account.update_type(template2type=template2type)
        # Create missing account types
        if account.template:
            account.template.create_type(
                company.id,
                template2type=template2type)

        # Update accounts
        #template2account = {}
        #account.update_account(template2account=template2account,
        #    template2type=template2type)
        # Create missing accounts
        #if account.template:
        #    account.template.create_account(
        #        company.id,
        #        template2account=template2account,
        #        template2type=template2type)
        return 'succeed'

class ConsolidatedBalanceSheetContext(ModelView):
    'Consolidated Balance Sheet Context'
    __name__ = 'account.consolidated_balance_sheet.context'
    date = fields.Date('Date', required=False)
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
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')
    companies = fields.One2Many('company.company','parent','Companies',
        domain=([
            ('parent','child_of',Eval('company')),
            ('type','=','normal')
            ]),
        depends=['company']
        )

    @staticmethod
    def default_date():
        Date_ = Pool().get('ir.date')
        return Transaction().context.get('date', Date_.today())

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_posted():
        return Transaction().context.get('posted', False)

class ConsolidatedBalanceSheetComparisionContext(ConsolidatedBalanceSheetContext):
    'Consolidated Balance Sheet Context'
    __name__ = 'account.consolidated_balance_sheet.comparision.context'
    comparison = fields.Boolean('Comparison')
    date_cmp = fields.Date('Date', states={
            'required': Eval('comparison', False),
            'invisible': ~Eval('comparison', False),
            },
        depends=['comparison'])

    @classmethod
    def default_comparison(cls):
        return False

    @fields.depends('comparison', 'date', 'date_cmp')
    def on_change_comparison(self):
        self.date_cmp = None
        if self.comparison and self.date:
            self.date_cmp = self.date - relativedelta(years=1)

    @classmethod
    def view_attributes(cls):
        return [
            ('/form/separator[@id="comparison"]', 'states', {
                    'invisible': ~Eval('comparison', False),
                    }),
            ]

class ConsolidatedIncomeStatementContext(ModelView):
    'Income Statement Context'
    __name__ = 'account.consolidated_income_statement.context'

    start_period = fields.Many2One('account.period', 'Start Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '<=', (Eval('end_period'), 'start_date'))
            ],
        depends=['end_period', 'fiscalyear'])
    end_period = fields.Many2One('account.period', 'End Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '>=', (Eval('start_period'), 'start_date')),
            ],
        depends=['start_period', 'fiscalyear'])
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
    company = fields.Many2One('company.company', 'Company', required=True)
    companies = fields.One2Many('company.company','parent','Companies',
        domain=([
            ('parent','child_of',Eval('company')),
            ('type','=','normal')
            ]),
        depends=['company']
        )
    posted = fields.Boolean('Posted Move', help='Show only posted move')
    comparison = fields.Boolean('Comparison')
    fiscalyear_cmp = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        states={
            'required': Eval('comparison', False),
            'invisible': ~Eval('comparison', False),
            },
        domain=[
            ('company', '=', Eval('company')),
            ],
        depends=['company'])
    start_period_cmp = fields.Many2One('account.period', 'Start Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear_cmp')),
            ('start_date', '<=', (Eval('end_period_cmp'), 'start_date'))
            ],
        states={
            'invisible': ~Eval('comparison', False),
            },
        depends=['end_period_cmp', 'fiscalyear_cmp'])
    end_period_cmp = fields.Many2One('account.period', 'End Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear_cmp')),
            ('start_date', '>=', (Eval('start_period_cmp'), 'start_date')),
            ],
        states={
            'invisible': ~Eval('comparison', False),
            },
        depends=['start_period_cmp', 'fiscalyear_cmp'])
    from_date_cmp = fields.Date("From Date",
        domain=[
            If(Eval('to_date_cmp') & Eval('from_date_cmp'),
                ('from_date_cmp', '<=', Eval('to_date_cmp')),
                ()),
            ],
        states={
            'invisible': ~Eval('comparison', False),
            },
        depends=['to_date_cmp', 'comparison'])
    to_date_cmp = fields.Date("To Date",
        domain=[
            If(Eval('from_date_cmp') & Eval('to_date_cmp'),
                ('to_date_cmp', '>=', Eval('from_date_cmp')),
                ()),
            ],
        states={
            'invisible': ~Eval('comparison', False),
            },
        depends=['from_date_cmp', 'comparison'])

    @staticmethod
    def default_fiscalyear():
        FiscalYear = Pool().get('account.fiscalyear')
        return FiscalYear.find(
            Transaction().context.get('company'), exception=False)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_posted():
        return False

    @classmethod
    def default_comparison(cls):
        return False

    @fields.depends('fiscalyear')
    def on_change_fiscalyear(self):
        self.start_period = None
        self.end_period = None

    @classmethod
    def view_attributes(cls):
        return [
            ('/form/separator[@id="comparison"]', 'states', {
                    'invisible': ~Eval('comparison', False),
                    }),
            ]

class CompanyPartyRel(ModelView, ModelSQL):
    'Company Party Relation'
    __name__ = 'company.company-party.party'
    _table = 'company_party_rel'

    party = fields.Many2One('party.party','Party',
        ondelete='RESTRICT',
         required=True, select=True)
    company = fields.Many2One('company.company','Company',
        ondelete='RESTRICT',
        required=True, select=True)

class GeneralLedgerAccount(DeactivableMixin, ModelSQL, ModelView):
    'General Ledger Account'
    __name__ = 'account.general_ledger.account'

    @classmethod
    def get_period_ids(cls, name):
        pool = Pool()
        Period = pool.get('account.period')
        context = Transaction().context

        period = None
        if name.startswith('start_'):
            period_ids = [0]
            if context.get('start_period'):
                period = Period(context['start_period'])
        elif name.startswith('end_'):
            period_ids = []
            if context.get('end_period'):
                period = Period(context['end_period'])

        if period:
            periods = Period.search([
                    ('fiscalyear', '=', context.get('fiscalyear')),
                    ('end_date', '<=', period.start_date),
                    ])
            if period.start_date == period.end_date:
                periods.append(period)
            if periods:
                period_ids = [p.id for p in periods]
            if name.startswith('end_'):
                # Always include ending period
                period_ids.append(period.id)
        return period_ids

class PrintGeneralBalanceStart(ModelView):
    'Print Consolidated General Balance Start'
    __name__ = 'print.consolidated_general_balance.start'

    company = fields.Many2One('company.company', "Company", readonly=True,
        required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    companies = fields.One2Many('company.company','parent','Companies',
        domain=([
            ('parent','child_of',Eval('company')),
            ('type','=','normal')
            ]),
        depends=['company'],
        required=True,
        )
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
    account = fields.Many2One('account.account.meta.type', 'Account Plan',
        help="The account meta plan for balance.",
        required=True,
        domain=[
            ('balance_sheet', '=', True),
            ])

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

    @classmethod
    def default_account(cls):
        Account = Pool().get('account.account.meta.type')
        company = Transaction().context.get('company')
        accounts = Account.search([
            ('balance_sheet', '=', True),
            ])
        if len(accounts)==1: 
            return accounts[0].id


class PrintGeneralBalance(Wizard):
    'Print Consolidated General Balance'
    __name__ = 'print.consolidated_general_balance'

    start = StateView('print.consolidated_general_balance.start',
        'account_consolidated.print_consolidated_general_balance_start_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('consolidated_general_balance.report')

    def do_print_(self, action):
        return action, {
            'company': self.start.company.id,
            'account': self.start.account.id,
            'companies': [{'id': x.id} for x in self.start.companies],
            'from_date': self.start.from_date,
            'to_date': self.start.to_date,
            }

class GeneralBalance(Report):
    'Consolidated General Balance Report'
    __name__ = 'consolidated_general_balance.report'

    @classmethod
    def _get_records(cls, ids, model, data):
        Account = Pool().get('account.account.meta.type')

        with Transaction().set_context(
                #from_date=data['from_date'],
                to_date=data['to_date'],
                companies=data['companies'],
                posted=True, 
                cumulate=True, 

                ):
            account = Account(data['account'])
            accounts = account._get_childs_by_order()
            return accounts

    @classmethod
    def get_context(cls, records, data):
        pool = Pool()
        Company = pool.get('company.company')
        report_context = super(GeneralBalance, cls).get_context(records, data)

        Company = Pool().get('company.company')
        company = Company(data['company'])

        report_context['company'] = company
        report_context['companies'] = Company.browse(
            [c['id'] for c in data['companies']])
        report_context['digits'] = company.currency.digits
        report_context['start_date'] = data['from_date']
        report_context['end_date'] = data['to_date']

        return report_context


class PrintIncomeStatementStart(ModelView):
    'Consollidated Income Statement Start'
    __name__ = 'print.consolidated_income_statement.start'

    company = fields.Many2One('company.company', "Company", readonly=True,
        required=True,
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
    account = fields.Many2One('account.account.meta.type', 'Account Plan',
        help="The account plan for balance.",
        required=True,
        domain=[
            ('income_statement', '=', True),
            ]
        )
    from_date = fields.Date("From Date",
        required=True, 
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
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_from_date(cls):
        return datetime.today().replace(day=1,month=1)

    @classmethod
    def default_to_date(cls):
        Date = Pool().get('ir.date')
        return Date.today()

    @classmethod
    def default_account(cls):
        Account = Pool().get('account.account.meta.type')
        company = Transaction().context.get('company')
        accounts = Account.search([
            ('income_statement', '=', True),
            ])
        if len(accounts)==1: 
            return accounts[0].id

class PrintIncomeStatement(Wizard):
    'Income Statement Balance'
    __name__ = 'print.consolidated_income_statement'

    start = StateView('print.consolidated_income_statement.start',
        'account_consolidated.print_consolidated_income_statement_start_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('consolidated_income_statement.report')

    def do_print_(self, action):
        return action, {
            'company': self.start.company.id,
            'account': self.start.account.id,
            'companies': [{'id': x.id} for x in self.start.companies],
            'from_date': self.start.from_date,
            'to_date': self.start.to_date,
            }


class IncomeStatement(GeneralBalance):
    'Consolidated Income Statement Report'
    __name__ = 'consolidated_income_statement.report'

    @classmethod
    def _get_records(cls, ids, model, data):
        Account = Pool().get('account.account.meta.type')

        with Transaction().set_context(
                from_date=data['from_date'],
                to_date=data['to_date'],
                companies=data['companies'],
                posted=True, 
                cumulate=True, 

                ):
            account = Account(data['account'])
            accounts = account._get_childs_by_order()
            return accounts