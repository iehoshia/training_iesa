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

__all__ = [
            'CreateChartAccountTemplate',
            'CreateChartTemplate',
            'AccountTypeTemplate',
            'AccountType',
            'UpdateChartStartTemplate',
            'UpdateChartTemplate', 
		]

def inactive_records(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with Transaction().set_context(active_test=False):
            return func(*args, **kwargs)
    return wrapper

class CreateChartAccountTemplate(ModelView):
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

class CreateChartTemplate(Wizard):
    'Create Chart Template'
    __name__ = 'account.create_chart'
    start = StateView('account.create_chart.start',
        'account.create_chart_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'account', 'tryton-ok', default=True),
            ])
    account = StateView('account.create_chart.account',
        'account.create_chart_account_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_account', 'tryton-ok', default=True),
            ])
    create_account = StateTransition()
    properties = StateView('account.create_chart.properties',
        'account.create_chart_properties_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_properties', 'tryton-ok', default=True),
            ])
    create_properties = StateTransition()

    @classmethod
    def __setup__(cls):
        super(CreateChartTemplate, cls).__setup__()
        cls._error_messages.update({
                'account_chart_exists': ('A chart of accounts already exists '
                    'for the company "%(company)s".')
                })

    def transition_create_account(self):
        pool = Pool()
        TaxCodeTemplate = pool.get('account.tax.code.template')
        TaxCodeLineTemplate = pool.get('account.tax.code.line.template')
        TaxTemplate = pool.get('account.tax.template')
        TaxRuleTemplate = pool.get('account.tax.rule.template')
        TaxRuleLineTemplate = \
            pool.get('account.tax.rule.line.template')
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

            # Update taxes and replaced_by on accounts
            account_template.update_account2(template2account, template2tax)

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
        return 'properties'

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
        if not type or type.type_display_balance != self.type_display_balance:
            res['type_display_balance'] = self.type_display_balance
        if not type or type.template != self:
            res['template'] = self.id
        return res

    def create_type(self, company_id, template2type=None,
        template2meta_type=None):
        '''
        Create recursively types based on template.
        template2type and template2meta_type is a dictionary with template id 
        as key and type id as value, used to convert template id into type. 
        The dictionary is filled with new types.
        '''
        pool = Pool()
        Type = pool.get('account.account.type')
        assert self.parent is None

        if template2type is None:
            template2type = {}

        if template2meta_type is None: 
            template2meta_type = {}

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
                    if template.meta_type:
                        vals['meta_type'] = template2meta_type[template.meta_type.id]
                    else:
                        vals['meta_type'] = None
                    values.append(vals)
                    created.append(template)

            types = Type.create(values)
            for template, type_ in zip(created, types):
                template2type[template.id] = type_.id

        childs = [self]
        while childs:
            create(childs)
            childs = sum((c.childs for c in childs), ())

class AccountType(ModelSQL, ModelView):
    'Account Type'
    __name__ = 'account.account.type'

    meta_type = fields.Many2One('account.account.meta.type','Meta Type')

    def update_type(self, template2type=None,
        template2meta_type=None):
        '''
        Update recursively types based on template.
        template2type is a dictionary with template id as key and type id as
        value, used to convert template id into type. The dictionary is filled
        with new types
        '''
        if template2type is None:
            template2type = {}

        if template2meta_type is None:
            template2meta_type = {}

        values = []
        childs = [self]
        while childs:
            for child in childs:
                if child.template and not child.template_override:
                    vals = child.template._get_type_value(type=child)
                    current_meta = child.meta_type.id if child.meta_type else None
                    #if child.template.meta_type:
                    #    vals['meta_type'] = template2meta_type[child.template.meta_type.id]
                    #else:
                    #    vals['meta_type'] = None
                    if child.template.meta_type:
                        meta_type = template2meta_type.get(
                            child.template.meta_type.id)
                    else:
                        meta_type = None
                    if current_meta != meta_type:
                        vals['meta_type'] = meta_type

                    if vals:
                        values.append([child])
                        values.append(vals)
                    template2type[child.template.id] = child.id
            childs = sum((c.childs for c in childs), ())
        #print "VALUES: "+str(values)
        if values:
            self.write(*values)

class UpdateChartStartTemplate(ModelView):
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

class UpdateChartTemplate(Wizard):
    'Update Chart'
    __name__ = 'account.update_chart'

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
        account_meta_template = self.start.meta_type
        company = account.company

        # Get account meta types
        template2meta_type = {}
        account_meta_template.update_type(template2type=template2meta_type)

        print("TEMPLATE 2 META TYPE", str(template2meta_type))

        # Update account types
        template2type = {}
        account.type.update_type(template2type=template2type, template2meta_type=template2meta_type)
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

        # Update taxes and replaced_by on accounts
        account.update_account2(template2account, template2tax)

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