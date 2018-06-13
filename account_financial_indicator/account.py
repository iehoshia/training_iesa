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
        'UpdateChartStart',
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
    is_recommended_capital = fields.Boolean('Recommended Capital')

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
        if not account or account.is_recommended_capital != self.is_recommended_capital:
            res['is_recommended_capital'] = self.is_recommended_capital
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

    @classmethod
    def default_analytic_accounts(cls):
        '''
        pool = Pool()
        AnalyticAccount = pool.get('analytic_account.account')

        accounts = []
        root_accounts = AnalyticAccount.search(
            cls.analytic_accounts_domain() + [
                ('parent', '=', None),
                ])
        for account in root_accounts:
            accounts.append({
                    'required': account.mandatory,
                    'root': account.id,
                    })
        return accounts
        ''' 
        return []

    def update_analytic_rule(self, template2analytic_rule=None,
        template2account=None):
        '''
        Update recursively types based on template.
        template2type is a dictionary with template id as key and type id as
        value, used to convert template id into type. The dictionary is filled
        with new types
        '''
        if template2analytic_rule is None:
            template2analytic_rule = {}

        if template2account is None:
            template2account = {}

        values = []
        childs = [self]
        while childs:
            for child in childs:
                if child.template:
                    vals = child.template._get_rule_value()
                    if child.template.account:
                        vals['account'] = template2account.get(child.template.account.id)
                    else:
                        vals['account'] = None
                    if vals:
                        values.append([child])
                        values.append(vals)
                    template2analytic_rule[child.template.id] = child.id
            break
            #childs = sum((c.childs for c in childs), ())
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
        #if not rule or rule.account != self.account:
        #    res['account'] = self.account
        if not rule or rule.template != self:
            res['template'] = self.id
        return res

    def create_analytic_rule(self, 
        company_id, 
        template2analytic_rule=None,
        template2account=None):
        '''
        Create recursively types based on template.
        template2type is a dictionary with template id as key and type id as
        value, used to convert template id into type. The dictionary is filled
        with new types.
        '''
        pool = Pool()
        Rule = pool.get('analytic_account.rule')
        #assert self.parent is None

        if template2analytic_rule is None:
            template2analytic_rule = {}

        def create(templates):
            values = []
            created = []
            for template in templates:
                if template.id not in template2analytic_rule:
                    vals = template._get_rule_value()
                    vals['company'] = company_id
                    if template.account:
                        vals['account'] = template2account.get(template.account.id)
                    else:
                        vals['account'] = None
                    #print "vals: " + str(vals)
                    values.append(vals)
                    created.append(template)
            print "VALUES: " + str(values)
            rules = Rule.create(values)

            for template, rule in zip(created, rules):
                template2analytic_rule[template.id] = rule.id

        childs = [self]
        #while childs:
        create(childs)
        #    break
        #    childs = sum((c.childs for c in childs), ())

class AnalyticAccountEntry(ModelView, ModelSQL):
    'Analytic Account Entry'
    __name__ = 'analytic.account.entry'
    
    template = fields.Many2One('analytic.account.entry.template', 'Template')
    companies = fields.Many2One('company.company','Companies',required=True)

    @staticmethod
    def default_companies():
        return Transaction().context.get('company')

    def update_entry(self, template2entry=None,
        template2analytic_rule=None,
        template2analytic_account=None):
        '''
        Update recursively types based on template.
        template2type is a dictionary with template id as key and type id as
        value, used to convert template id into type. The dictionary is filled
        with new types
        '''
        if template2entry is None:
            template2entry = {}

        if template2analytic_rule is None:
            template2analytic_rule = {}

        if template2analytic_account is None:
            template2analytic_account = {}

        values = []
        childs = [self]
        while childs:
            for child in childs:
                if child.template:
                    vals = child.template._get_entry_value()
                    if child.template.origin:
                        origin =  template2analytic_rule.get(child.template.origin.id)
                        vals['origin'] = 'analytic_account.rule,'+str(origin)
                    else:
                        vals['origin'] = None
                    if child.template.root:
                        vals['root'] = template2analytic_account.get(child.template.root.id)
                    else:
                        vals['root'] = None
                    if child.template.account:
                        vals['account'] = template2analytic_account.get(child.template.account.id)
                    else:
                        vals['account'] = None
                    if vals:
                        values.append([child])
                        values.append(vals)
                    template2entry[child.template.id] = child.id
            break
            #childs = sum((c.childs for c in childs), ())
        if values:
            self.write(*values)

class AnalyticAccountEntryTemplate(ModelView, ModelSQL):
    'Analytic Account Entry Template'
    __name__ = 'analytic.account.entry.template'

    #origin = fields.Reference('Origin', selection='get_origin', select=True)
    origin = fields.Many2One('analytic_account.rule.template', 'Origin')
    root = fields.Many2One(
        'analytic_account.account.template', "Root Analytic", required=True,
        domain=[
            ('type', '=', 'root'),
            ],
        )
    account = fields.Many2One(
        'analytic_account.account.template', 'Account',
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

    @classmethod
    def _get_origin(cls):
        return ['analytic_account.rule.template']

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

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
        if not entry or entry.template != self:
            res['template'] = self.id
        return res

    def create_analytic_entry(self, 
        company_id, 
        template2entry=None,
        template2analytic_rule=None, 
        template2analytic_account=None):
        '''
        Create recursively types based on template.
        template2type is a dictionary with template id as key and type id as
        value, used to convert template id into type. The dictionary is filled
        with new types.
        '''
        pool = Pool()
        Entry = pool.get('analytic.account.entry')
        #assert self.parent is None

        if template2entry is None:
            template2entry = {}

        if template2analytic_rule is None:
            template2analytic_rule = {}

        if template2analytic_account is None:
            template2analytic_account = {}

        def create(templates):
            values = []
            created = []
            for template in templates:
                if template.id not in template2entry:
                    vals = template._get_entry_value()
                    vals['companies'] = company_id
                    if template.origin:
                        origin = template2analytic_rule.get(template.origin.id)
                        vals['origin'] = 'analytic_account.rule,' + str(origin)
                    else:
                        vals['origin'] = None
                    if template.root:
                        vals['root'] = template2analytic_account.get(template.root.id)
                    else:
                        vals['root'] = None
                    if template.account:
                        vals['account'] = template2analytic_account.get(template.account.id)
                    else:
                        vals['account'] = None
                    values.append(vals)
                    created.append(template)

            entries = Entry.create(values)
            for template, entry in zip(created, entries):
                template2entry[template.id] = entry.id

        childs = [self]
        create(childs)
        #while childs:
        #    create(childs)
        #    break
        #    childs = sum((c.childs for c in childs), ())

class CreateChartAccount(ModelView):
    'Create Chart'
    __name__ = 'account.create_chart.account'

    meta_type = fields.Many2One('account.account.meta.type',
            'Consolidated Plan', required=True, domain=[('parent', '=', None)])

    @staticmethod
    def default_meta_type():
        AccountTemplate = Pool().get('account.account.meta.type')
        accounts = AccountTemplate.search([('parent','=',None)])
        if len(accounts) == 1: 
            return accounts[0].id

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
        AnalyticEntry = pool.get('analytic.account.entry.template')
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
            account_meta_template = self.account.meta_type

            # Get account meta types
            template2meta_type = {}
            account_meta_template.update_type(template2type=template2meta_type)

            # Create account types
            template2type = {}
            account_template.type.create_type(
                company.id,
                template2type=template2type,
                template2meta_type=template2meta_type)

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

            def merge_two_dicts(x, y):
                z = x.copy()   # start with x's keys and values
                z.update(y)    # modifies z with y's keys and values & returns None
                return z

            template2analytic_account_cumm = {}
            for template in analytic_templates: 
                template2analytic_account = {}
                template.create_analytic_account(
                    company.id,
                    template2analytic_account, 
                    )
                template2analytic_account_cumm = merge_two_dicts(template2analytic_account_cumm,template2analytic_account)

            
            template2analytic_rule_cumm = {}
            # Create analytic rule
            analytic_rules = AnalyticRule.search([()])
            for rule in analytic_rules:
                template2analytic_rule = {}
                rule.create_analytic_rule(
                    company.id,
                    template2analytic_rule, 
                    template2account)
                template2analytic_rule_cumm = merge_two_dicts(template2analytic_rule_cumm,template2analytic_rule)

            # Create analytic entry
            analytic_entries = AnalyticEntry.search([()])
            for entry in analytic_entries:
                template2entry = {}
                entry.create_analytic_entry(
                    company.id,
                    template2entry, 
                    template2analytic_rule_cumm, 
                    template2analytic_account_cumm, 
                    )

        return 'properties'

class UpdateChartStart(ModelView):
    'Update Chart'
    __name__ = 'account.update_chart.start'

    meta_type = fields.Many2One('account.account.meta.type',
            'Consolidated Plan', required=True, domain=[('parent', '=', None)])

    @staticmethod
    def default_meta_type():
        AccountTemplate = Pool().get('account.account.meta.type')
        accounts = AccountTemplate.search([('parent','=',None)])
        if len(accounts) == 1: 
            return accounts[0].id


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
        AnalyticAccountTemplate = \
            pool.get('analytic_account.account.template')
        AnalyticRule = \
            pool.get('analytic_account.rule')
        AnalyticRuleTemplate = \
            pool.get('analytic_account.rule.template')
        AnalyticEntryTemplate = pool.get('analytic.account.entry.template')
        AnalyticEntry = pool.get('analytic.account.entry')

        account = self.start.account
        meta_type = self.start.meta_type
        company = account.company

        # Update account meta types
        template2meta_type = {}
        meta_type.update_type(template2type=template2meta_type)

        # Update account types
        template2type = {}
        account.type.update_type(template2type=template2type,
            template2meta_type=template2meta_type)

        # Create missing account types
        if account.type.template:
            account.type.template.create_type(
                company.id,
                template2type=template2type,
                template2meta_type=template2meta_type)

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

        def merge_two_dicts(x, y):
            z = x.copy()   # start with x's keys and values
            z.update(y)    # modifies z with y's keys and values & returns None
            return z

        for analytic_account in analytic_accounts:
            analytic_account.update_analytic_account(template2account=template2analytic_account)

            # Create missing accounts
            if analytic_account.template:
                analytic_account.template.create_analytic_account(
                    company.id,
                    template2account=template2analytic_account)

        # Update analytic rules
        template2analytic_rule_cumm = {}

        analytic_rules = AnalyticRule.search([
            ('company','=',company.id)
            ])

        analytic_rule_templates = AnalyticRuleTemplate.search([()])

        existing = []
        if analytic_rules is not None:
            template2analytic_rule = {}
            # Update existing rules
            for analytic_rule in analytic_rules: 
                if analytic_rule.template: 
                    existing.append(analytic_rule.template.id)
                    analytic_rule.update_analytic_rule(
                        template2analytic_rule=template2analytic_rule,
                        template2account=template2account)
                    template2analytic_rule_cumm = merge_two_dicts(template2analytic_rule_cumm, template2analytic_rule)
        
        all_templates = []
        if analytic_rule_templates is not None:
            for analytic_rule_template in analytic_rule_templates: 
                all_templates.append(analytic_rule_template.id)
        
        not_existing = tuple(set(all_templates) - set(existing))
        
        # Create missing rules
        if not_existing is not []: 
            template2analytic_rule = {}
            for new_rule in not_existing: 
                analytic_rules = AnalyticRuleTemplate.search([('id','=',new_rule)])
                for analytic_rule in analytic_rules: 
                    new_analytic_rule = analytic_rule
                #print "NEW ANALYTIC RULE: " + str(new_analytic_rule)
                if new_analytic_rule:
                    analytic_rule.create_analytic_rule(
                        company.id,
                        template2analytic_rule=template2analytic_rule,
                        template2account=template2account)
                    template2analytic_rule_cumm = merge_two_dicts(template2analytic_rule_cumm, template2analytic_rule)

        # Update analytic entries
        template2entry = {}
        analytic_entries = AnalyticEntry.search([
            ('companies','=',company.id)
            ])
        all_existing_entries = AnalyticEntryTemplate.search([()])

        existing = []
        if analytic_entries is not None:
            for analytic_entry in analytic_entries: 
                if analytic_entry.template: 
                    existing.append(analytic_entry.template.id)
                    #print "BEFORE template2entry: " + str(template2entry)
                    analytic_entry.update_entry(template2entry=template2entry, 
                        template2analytic_rule=template2analytic_rule_cumm,
                        template2analytic_account=template2analytic_account,
                        )
        
        all_entries = []
        if all_existing_entries is not None: 
            for analytic_entry_template in all_existing_entries: 
                all_entries.append(analytic_entry_template.id)
        
        not_existing = tuple(set(all_entries) - set(existing))

        # Create missing entries
        if not_existing is not []: 
            for new_entry in not_existing: 
                analytic_entries = AnalyticEntryTemplate.search([('id','=',new_entry)])
                if analytic_entries is not []:
                    for analytic_entry in analytic_entries: 
                        new_analytic_entry = analytic_entry
                if new_analytic_entry is not None:
                    analytic_entry.create_analytic_entry(
                        company.id,
                        template2entry=template2entry,
                        template2analytic_rule=template2analytic_rule_cumm,
                        template2analytic_account=template2analytic_account)

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