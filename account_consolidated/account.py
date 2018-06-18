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
    ModelSingleton, ModelView, ModelSQL, DeactivableMixin, fields, Unique, sequence_ordered)
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    Button
from trytond.report import Report
from trytond.tools import reduce_ids, grouped_slice
from trytond.pyson import Eval, If, PYSONEncoder, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond import backend
import json, ast

from numero_letras import numero_a_moneda

__all__ = [
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
    'GeneralLedgerAccount',
    'CompanyPartyRel',
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

class TypeTemplate(sequence_ordered(), ModelSQL, ModelView):
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

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)
        super(TypeTemplate, cls).__register__(module_name)

    @classmethod
    def validate(cls, records):
        super(TypeTemplate, cls).validate(records)
        cls.check_recursion(records, rec_name='name')

    @staticmethod
    def default_balance_sheet():
        return False

    @staticmethod
    def default_income_statement():
        return False

    @staticmethod
    def default_display_balance():
        return 'debit-credit'

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

class Type(sequence_ordered(), ModelSQL, ModelView):
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
    del _states

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        super(Type, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @classmethod
    def validate(cls, types):
        super(Type, cls).validate(types)
        cls.check_recursion(types, rec_name='name')

    @staticmethod
    def default_balance_sheet():
        return False

    @staticmethod
    def default_income_statement():
        return False

    @staticmethod
    def default_display_balance():
        return 'debit-credit'

    @classmethod
    def default_template_override(cls):
        return False

    def get_currency_digits(self, name):
        return self.company.currency.digits

    @classmethod
    def get_amount(cls, types, name):
        pool = Pool()
        Account = pool.get('account.account')
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

        for company in context.get('companies', []):
            with transaction.set_context(company=company['id']):
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
        if self.parent:
            return self.parent.get_rec_name(name) + '\\' + self.name
        else:
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
            accounts = Account.search([('company', '=', company.id)], limit=1)
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

            # Create accounts
            #template2account = {}
            #account_template.create_account(
            #    company.id,
            #    template2account=template2account,
            #    template2type=template2type)

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
    date = fields.Date('Date', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')
    companies = fields.One2Many('company.company','parent','Companies',
        domain=([('parent','child_of',Eval('company'))]),
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

        #print "NAME: " + str(name)

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
        #print "PERIOD_IDS: " + str(period_ids)
        return period_ids
