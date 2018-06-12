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
        #if not type or type.meta_type != self.meta_type:
        #    res['meta_type'] = self.meta_type
        if not type or type.template != self:
            res['template'] = self.id
        return res

    def create_type(self, company_id, template2type=None,
        template2meta_type=None):
        '''
        Create recursively types based on template.
        template2type is a dictionary with template id as key and type id as
        value, used to convert template id into type. The dictionary is filled
        with new types.
        '''
        pool = Pool()
        Type = pool.get('account.account.type')
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
                    if child.template.meta_type:
                        vals['meta_type'] = template2meta_type[child.template.meta_type.id]
                    else:
                        vals['meta_type'] = None
                    if vals:
                        values.append([child])
                        values.append(vals)
                    template2type[child.template.id] = child.id
            childs = sum((c.childs for c in childs), ())
        #print "VALUES: "+str(values)
        if values:
            self.write(*values)