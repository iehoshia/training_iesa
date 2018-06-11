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
        'UpdateChart',
    ]  

__metaclass__ = PoolMeta

def inactive_records(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with Transaction().set_context(active_test=False):
            return func(*args, **kwargs)
    return wrapper

class Account(ModelSQL, ModelView):
    'Analytic Account'
    __name__ = 'analytic_account.account'

    template = fields.Many2One('analytic_account.account.template', 'Template')

    def update_analytic_account(self, template2account=None):
        '''
        Update recursively types based on template.
        template2type is a dictionary with template id as key and type id as
        value, used to convert template id into type. The dictionary is filled
        with new types
        '''
        if template2account is None:
            template2account = {}

        values = []
        childs = [self]
        while childs:
            for child in childs:
                if child.template:
                    vals = child.template._get_account_value()
                    if vals:
                        values.append([child])
                        values.append(vals)
                    template2account[child.template.id] = child.id
            childs = sum((c.childs for c in childs), ())
        if values:
            self.write(*values)

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
    childs = fields.One2Many('analytic_account.account.template', 'parent',
        'Children')
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

    def create_analytic_account(self, company_id, template2account=None):
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
                        vals['root'] = template2account.get(template.root.id)
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

class Rule(ModelSQL, ModelView):
    "Analytic Rule"
    __name__ = 'analytic_account.rule'

    template = fields.Many2One('analytic_account.rule.template', 'Template')

    def update_analytic_rule(self, template2rule=None):
        '''
        Update recursively types based on template.
        template2type is a dictionary with template id as key and type id as
        value, used to convert template id into type. The dictionary is filled
        with new types
        '''
        if template2rule is None:
            template2rule = {}

        values = []
        childs = [self]
        while childs:
            for child in childs:
                if child.template:
                    vals = child.template._get_rule_value()
                    if vals:
                        values.append([child])
                        values.append(vals)
                    template2rule[child.template.id] = child.id
            childs = sum((c.childs for c in childs), ())
        if values:
            self.write(*values)

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

    def create_analytic_rule(self, company_id, template2rule=None):
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
            'Analytic Account Template', required=False, domain=[('parent', '=', None)])

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

        #print "TRANSITION: "

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
            analytic_templates = AnalyticAccountTemplate.search([
                ('type','=','root'),
                ('parent','=',None)
                ])
            for template in analytic_templates: 
                template2analytic_account = {}
                template.create_analytic_account(
                    company.id,
                    template2analytic_account, 
                    )

            # Create analytic rule
            analytic_rules = AnalyticRule.search([()])
            for rule in analytic_rules:
                template2rule = {}
                template.create_rule(
                    company.id,
                    template2rule, 
                    )



        return 'properties'

class UpdateChart(Wizard):
    'Update Chart'
    __name__ = 'account.update_chart'
    start = StateView('account.update_chart.start',
        'account.update_chart_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Update', 'update', 'tryton-ok', default=True),
            ])
    update = StateTransition()
    succeed = StateView('account.update_chart.succeed',
        'account.update_chart_succeed_view_form', [
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
        AnalyticAccount = \
            pool.get('analytic_account.account')

        account = self.start.account
        company = account.company

        # Update account types
        template2type = {}
        account.type.update_type(template2type=template2type)
        # Create missing account types
        if account.type.template:
            account.type.template.create_type(
                company.id,
                template2type=template2type)

        # Update accounts
        template2account = {}
        account.update_account(template2account=template2account,
            template2type=template2type)
        # Create missing accounts
        if account.template:
            account.template.create_account(
                company.id,
                template2account=template2account,
                template2type=template2type)

        # Update analytic accounts
        template2analytic_account = {}
        analytic_accounts = AnalyticAccount.search([
            ('parent','=',None),
            ('company','=',company.id)])
        for analytic_account in analytic_accounts:
            analytic_account.update_analytic_account(template2account=template2analytic_account)
            # Create missing accounts
            if analytic_account.template:
                analytic_account.template.create_analytic_account(
                    company.id,
                    template2account=template2analytic_account)

        # Update analytic rules
        template2analytic_rule = {}
        analytic_rules = AnalyticRule.search([
            ('company','=',company.id)])
        for analytic_rule in analytic_rules:
            analytic_rule.update_analytic_rule(template2rule=template2analytic_rule)
            # Create missing accounts
            if analytic_rule.template:
                analytic_rule.template.create_analytic_rule(
                    company.id,
                    template2rule=template2analytic_rule)

        # Update taxes
        template2tax = {}
        Tax.update_tax(
            company.id,
            template2account=template2account,
            template2tax=template2tax)
        # Create missing taxes
        if account.template:
            TaxTemplate.create_tax(
                account.template.id, account.company.id,
                template2account=template2account,
                template2tax=template2tax)

        # Update tax codes
        template2tax_code = {}
        TaxCode.update_tax_code(
            company.id,
            template2tax_code=template2tax_code)
        # Create missing tax codes
        if account.template:
            TaxCodeTemplate.create_tax_code(
                account.template.id, company.id,
                template2tax_code=template2tax_code)

        # Update tax code lines
        template2tax_code_line = {}
        TaxCodeLine.update_tax_code_line(
            company.id,
            template2tax=template2tax,
            template2tax_code=template2tax_code,
            template2tax_code_line=template2tax_code_line)
        # Create missing tax code lines
        if account.template:
            TaxCodeLineTemplate.create_tax_code_line(
                account.template.id,
                template2tax=template2tax,
                template2tax_code=template2tax_code,
                template2tax_code_line=template2tax_code_line)

        # Update taxes on accounts
        account.update_account_taxes(template2account, template2tax)

        # Update tax rules
        template2rule = {}
        TaxRule.update_rule(company.id, template2rule=template2rule)
        # Create missing tax rules
        if account.template:
            TaxRuleTemplate.create_rule(
                account.template.id, account.company.id,
                template2rule=template2rule)

        # Update tax rule lines
        template2rule_line = {}
        TaxRuleLine.update_rule_line(
            company.id, template2tax, template2rule,
            template2rule_line=template2rule_line)
        # Create missing tax rule lines
        if account.template:
            TaxRuleLineTemplate.create_rule_line(
                account.template.id, template2tax, template2rule,
                template2rule_line=template2rule_line)

        return 'succeed'