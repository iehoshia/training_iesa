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
 
__all__ = [
        'AccountTemplate',
        'RuleTemplate',
        'AnalyticAccountEntryTemplate',
        'Account', 
        'Rule', 
        'AnalyticAccountEntry', 
        'CreateChartAccount',
        'CreateChart',
    ]  

__metaclass__ = PoolMeta

class Account(ModelSQL, ModelView):
    'Analytic Account'
    __name__ = 'analytic_account.account'

    template = fields.Many2One('analytic_account.account.template', 'Template')

class AccountTemplate(ModelSQL, ModelView):
    'Analytic Account Template'
    __name__ = 'analytic_account.account.template'

    name = fields.Char('Name', required=True, translate=True, select=True)
    code = fields.Char('Code', select=True)
    type = fields.Selection([
        ('root', 'Root'),
        ('view', 'View'),
        ('normal', 'Normal'),
        ('distribution', 'Distribution'),
        ], 'Type', required=True)
    root = fields.Many2One('analytic_account.account.template', 'Root', select=True,
        domain=[
            ('parent', '=', None),
            ('type', '=', 'root'),
            ],
        states={
            'invisible': Eval('type') == 'root',
            'required': Eval('type') != 'root',
            },
        depends=['type'])
    parent = fields.Many2One('analytic_account.account.template', 'Parent', select=True,
        domain=['OR',
            ('root', '=', Eval('root', -1)),
            ('parent', '=', None),
            ],
        states={
            'invisible': Eval('type') == 'root',
            'required': Eval('type') != 'root',
            },
        depends=['root', 'type'])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('opened', 'Opened'),
        ('closed', 'Closed'),
        ], 'State', required=True)
    display_balance = fields.Selection([
        ('debit-credit', 'Debit - Credit'),
        ('credit-debit', 'Credit - Debit'),
        ], 'Display Balance', required=True)
    mandatory = fields.Boolean('Mandatory', states={
            'invisible': Eval('type') != 'root',
            },
        depends=['type'],
        help="Make this account mandatory when filling documents")

    @classmethod
    def __setup__(cls):
        super(AccountTemplate, cls).__setup__()
        cls._order.insert(0, ('code', 'ASC'))
        cls._order.insert(1, ('name', 'ASC'))

    @classmethod
    def validate(cls, templates):
        super(AccountTemplate, cls).validate(templates)
        cls.check_recursion(templates)

    @staticmethod
    def default_type():
        return 'root'

    @staticmethod
    def default_state():
        return 'draft'

    @fields.depends('parent', 'type',
        '_parent_parent.root', '_parent_parent.type')
    def on_change_parent(self):
        if self.parent and self.type != 'root':
            if self.parent.type == 'root':
                self.root = self.parent
            else:
                self.root = self.parent.root
        else:
            self.root = None

    def _get_account_value(self, account=None):
        '''
        Set the values for account creation.
        '''
        res = {}
        if not account or account.name != self.name:
            res['name'] = self.name
        if not account or account.code != self.code:
            res['code'] = self.code
        if not account or account.type != self.type:
            res['type'] = self.type
        if not account or account.display_balance != self.display_balance:
            res['display_balance'] = self.display_balance
        if not account or account.template != self:
            res['template'] = self.id
        return res

    def create_account(self, company_id, template2account=None,
            template2type=None):
        '''
        Create recursively accounts based on template.
        template2account is a dictionary with template id as key and account id
        as value, used to convert template id into account. The dictionary is
        filled with new accounts
        template2type is a dictionary with type template id as key and type id
        as value, used to convert type template id into type.
        '''
        pool = Pool()
        Account = pool.get('analytic_account.account')
        assert self.parent is None

        if template2account is None:
            template2account = {}

        if template2type is None:
            template2type = {}

        def create(templates):
            values = []
            created = []
            for template in templates:
                if template.id not in template2account:
                    vals = template._get_account_value()
                    vals['company'] = company_id
                    if template.parent:
                        vals['parent'] = template2account[template.parent.id]
                    else:
                        vals['parent'] = None
                    if template.root:
                        vals['root'] = template2type.get(template.root.id)
                    else:
                        vals['root'] = None
                    values.append(vals)
                    created.append(template)

            accounts = Account.create(values)
            for template, account in zip(created, accounts):
                template2account[template.id] = account.id

        childs = [self]
        while childs:
            create(childs)
            childs = sum((c.childs for c in childs), ())

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

class Rule(ModelSQL, ModelView):
    "Analytic Rule"
    __name__ = 'analytic_account.rule'

    template = fields.Many2One('analytic_account.rule.template', 'Template')

class RuleTemplate(ModelSQL, ModelView):
    "Analytic Rule Template"
    __name__ = 'analytic_account.rule.template'

    account = fields.Many2One(
        'account.account.template', "Account",
        domain=[
            ('type', '!=', 'view'),
            ])

    def _get_rule_value(self, rule=None):
        '''
        Set the values for account creation.
        '''
        res = {}
        if not rule or rule.account != self.account:
            res['account'] = self.account
        if not rule or rule.template != self:
            res['template'] = self.id
        return res

    def create_rule(self, company_id, template2rule=None):
        '''
        Create recursively types based on template.
        template2type is a dictionary with template id as key and type id as
        value, used to convert template id into type. The dictionary is filled
        with new types.
        '''
        pool = Pool()
        Rule = pool.get('analytic_account.rule')
        assert self.parent is None

        if template2rule is None:
            template2rule = {}

        def create(templates):
            values = []
            created = []
            for template in templates:
                if template.id not in template2rule:
                    vals = template._get_rule_value()
                    vals['company'] = company_id
                    values.append(vals)
                    created.append(template)

            rules = Rule.create(values)
            for template, rule in zip(created, rules):
                template2rule[template.id] = rule.id

        childs = [self]
        while childs:
            create(childs)
            childs = sum((c.childs for c in childs), ())

class AnalyticAccountEntry(ModelView, ModelSQL):
    'Analytic Account Entry'
    __name__ = 'analytic_account.entry'
    
    template = fields.Many2One('analytic_account.entry.template', 'Template')

class AnalyticAccountEntryTemplate(ModelView, ModelSQL):
    'Analytic Account Entry Template'
    __name__ = 'analytic_account.entry.template'

    root = fields.Many2One(
        'analytic_account.account.template', "Root Analytic", required=True,
        domain=[
            ('type', '=', 'root'),
            ],
        )
    account = fields.Many2One('analytic_account.account.template', 'Account',
        ondelete='RESTRICT',
        states={
            'required': Eval('required', False),
            },
        domain=[
            ('root', '=', Eval('root')),
            ('type', 'in', ['normal', 'distribution']),
            ],
        depends=['root', 'required', 'company'])
    required = fields.Function(fields.Boolean('Required'),
        'on_change_with_required')

    @fields.depends('root')
    def on_change_with_required(self, name=None):
        if self.root:
            return self.root.mandatory
        return False

    def _get_entry_value(self, entry=None):
        '''
        Set the values for account creation.
        '''
        res = {}
        if not entry or entry.account != self.account:
            res['account'] = self.account
        if not entry or entry.root != self.root:
            res['root'] = self.root
        if not entry or entry.template != self:
            res['template'] = self.id
        return res

    def create_entry(self, company_id, template2entry=None):
        '''
        Create recursively types based on template.
        template2type is a dictionary with template id as key and type id as
        value, used to convert template id into type. The dictionary is filled
        with new types.
        '''
        pool = Pool()
        Entry = pool.get('analytic_account.entry')
        assert self.parent is None

        if template2entry is None:
            template2entry = {}

        def create(templates):
            values = []
            created = []
            for template in templates:
                if template.id not in template2entry:
                    vals = template._get_entry_value()
                    vals['company'] = company_id
                    values.append(vals)
                    created.append(template)

            entries = Entry.create(values)
            for template, rule in zip(created, entries):
                template2entry[template.id] = entry.id

        childs = [self]
        while childs:
            create(childs)
            childs = sum((c.childs for c in childs), ())

class CreateChartAccount(ModelView):
    'Create Chart'
    __name__ = 'account.create_chart.account'

    analytic_account_template = fields.Many2One('analytic_account.account.template',
            'Analytic Account Template', required=True, domain=[('parent', '=', None)])

class CreateChart(Wizard):
    'Create Chart'
    __name__ = 'account.create_chart'

    def transition_create_account(self):
        pool = Pool()
        TaxCodeTemplate = pool.get('account.tax.code.template')
        TaxCodeLineTemplate = pool.get('account.tax.code.line.template')
        TaxTemplate = pool.get('account.tax.template')
        TaxRuleTemplate = pool.get('account.tax.rule.template')
        TaxRuleLineTemplate = \
            pool.get('account.tax.rule.line.template')
        AnalyticAccountTemplate = pool.get('analytic_account.account.template')
        AnalyticRule = pool.get('analytic_account.rule.template')
        Config = pool.get('ir.configuration')
        Account = pool.get('account.account')
        transaction = Transaction()

        company = self.account.company
        # Skip access rule
        with transaction.set_user(0):
            accounts = Account.search([('company', '=', company.id)], limit=1)
        if accounts:
            self.raise_user_warning('duplicated_chart.%d' % company.id,
                'account_chart_exists', {
                    'company': company.rec_name,
                    })

        with transaction.set_context(language=Config.get_language(),
                company=company.id):
            account_template = self.account.account_template

            # Create account types
            template2type = {}
            account_template.type.create_type(
                company.id,
                template2type=template2type)

            # Create accounts
            template2account = {}
            account_template.create_account(
                company.id,
                template2account=template2account,
                template2type=template2type)

            # Create taxes
            template2tax = {}
            TaxTemplate.create_tax(
                account_template.id, company.id,
                template2account=template2account,
                template2tax=template2tax)

            # Create tax codes
            template2tax_code = {}
            TaxCodeTemplate.create_tax_code(
                account_template.id, company.id,
                template2tax_code=template2tax_code)

            # Create tax code lines
            template2tax_code_line = {}
            TaxCodeLineTemplate.create_tax_code_line(
                account_template.id,
                template2tax=template2tax,
                template2tax_code=template2tax_code,
                template2tax_code_line=template2tax_code_line)

            # Update taxes on accounts
            account_template.update_account_taxes(template2account,
                template2tax)

            # Create tax rules
            template2rule = {}
            TaxRuleTemplate.create_rule(
                account_template.id, company.id,
                template2rule=template2rule)

            # Create tax rule lines
            template2rule_line = {}
            TaxRuleLineTemplate.create_rule_line(
                account_template.id, template2tax, template2rule,
                template2rule_line=template2rule_line)

            # Create analytic plan
            analytic_account_template = self.account.account_template
            template2analytic_account = {}
            AnalyticAccountTemplate.create_account(
                analytic_account_template.id, template2analytic_account, 
                )


        return 'properties'