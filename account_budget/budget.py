# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal, ROUND_DOWN

from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import If, Eval, Bool
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    Button

__all__ = [
    'BudgetAccount', 'Budget',  'BudgetPeriod', 'CopyBudgetStart',
    'CopyBudget', 'DistributePeriodStart', 'DistributePeriod']

__metaclass__ = PoolMeta

class BalanceMixin:
    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"),
            'on_change_with_currency')
    currency_digits = fields.Function(fields.Integer("Currency Digits"),
            'on_change_with_currency_digits')
    amount = fields.Numeric("Amount", digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'], required=True,
        help="The expected amount for this budget and its childs.")
    balance = fields.Function(fields.Numeric("Balance",
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'],
            help="The real amount for this budget line."),
        'get_balance')
    difference = fields.Function(fields.Numeric("Difference",
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_difference')

    def on_change_with_currency(self, name=None):
        raise NotImplementedError

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @classmethod
    def _get_balance_query(cls, sub_ids):
        raise NotImplementedError

    @classmethod
    def get_balance(cls, records, name):
        cursor = Transaction().connection.cursor()
        ids = [p.id for p in records]
        balances = {}.fromkeys(ids, Decimal('0'))
        for sub_ids in grouped_slice(ids):
            cursor.execute(*cls._get_balance_query(sub_ids))
            balances.update(dict(cursor.fetchall()))

        # SQLite uses float for SUM
        for record_id, balance in balances.iteritems():
            if isinstance(balance, Decimal):
                break
            balances[record_id] = Decimal(str(balance))

        for record in records:
            balances[record.id] = record.currency.round(balances[record.id])
        return balances

    @classmethod
    def get_difference(cls, records, name):
        differences = {}
        for record in records:
            #print "BALANCE: " + str(record.balance)
            differences[record.id] = record.amount - record.balance
        return differences


class BudgetMixin(BalanceMixin, ModelSQL, ModelView):
    name = fields.Char("Name", required=True,
        help="The main identifier of this budget.")
    company = fields.Many2One('company.company', "Company", required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ], select=True,
        help="Make the budget belong to the company.")
    left = fields.Integer("Left", required=True, select=True)
    right = fields.Integer("Right", required=True, select=True)
    type = fields.Selection([('debit','Debit'),
        ('credit','Credit')],
        'Type')

    @classmethod
    def _childs_domain(cls):
        return [('company', '=', Eval('company'))]

    @classmethod
    def _childs_depends(cls):
        return ['company']

    @classmethod
    def __setup__(cls):
        if not hasattr(cls, 'parent'):
            domain = cls._childs_domain()
            depends = cls._childs_depends()
            cls.parent = fields.Many2One(cls.__name__, "Parent", select=True,
                help="Add the budget below the parent.",
                left='left', right='right', ondelete='RESTRICT',
                domain=domain, depends=depends)
            cls.children = fields.One2Many(cls.__name__, 'parent', "Children",
                help="Add children below the budget.",
                domain=domain, depends=depends)
        super(BudgetMixin, cls).__setup__()
        cls._buttons.update({
                'copy_budget': {
                    },
                })
        cls._error_messages.update({
                'invalid_children_amount': (
                    'The children amount "%(children_amount)s" of budget '
                    '"%(budget)s" can not be higher than its own amount '
                    '"%(amount)s".'
                    ),
                })

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_left(cls):
        return 0

    @classmethod
    def default_right(cls):
        return 0

    @fields.depends('company')
    def on_change_with_currency(self, name=None):
        if self.company:
            return self.company.currency.id

    def get_rec_name(self, name):
        if self.parent:
            return self.parent.get_rec_name(name) + '\\' + self.name
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        if isinstance(clause[2], basestring):
            values = clause[2].split('\\')
            values.reverse()
            domain = []
            field = 'name'
            for name in values:
                domain.append((field, clause[1], name.strip()))
                field = 'parent.' + field
        else:
            domain = [('name',) + tuple(clause[1:])]
        ids = [w.id for w in cls.search(domain, order=[])]
        return [('parent', 'child_of', ids)]

    @classmethod
    def copy_budget(cls, budgets):
        raise NotImplementedError

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        default.setdefault('left', 0)
        default.setdefault('right', 0)
        return super(BudgetMixin, cls).copy(records, default=default)

    @classmethod
    def validate(cls, records):
        super(BudgetMixin, cls).validate(records)
        for record in records:
            record.check_amounts()

    def check_amounts(self):
        children_amount = sum((c.amount for c in self.children), Decimal(0))
        if abs(children_amount) > abs(self.amount):
            self.raise_user_error('invalid_children_amount', {
                    'children_amount': children_amount,
                    'amount': self.amount,
                    'budget': self.rec_name,
                    })


class Budget(BudgetMixin):
    'Account Budget'
    __name__ = 'account.budget'

    fiscalyear = fields.Many2One('account.fiscalyear', "Fiscal Year",
        required=True,
        domain=[
            ('company', '=', Eval('company')),
            ],
        depends=['company'],
        help="The fiscalyear used to compute the balances.")
    accounts = fields.Many2Many('account.budget-account.account',
        'budget', 'account', "Accounts",
        domain=[
            ('company', '=', Eval('company')),
            ('kind', '!=', 'view'),
            ],
        depends=['company'],
        help="Add accounts to compute the budget balance.")
    periods = fields.One2Many('account.budget.period', 'budget', "Periods",
        help="Add budget detail for each period.")

    @classmethod
    def _childs_domain(cls):
        return super(Budget, cls)._childs_domain() + [
            ('fiscalyear', '=', Eval('fiscalyear')),
            ]

    @classmethod
    def _childs_depends(cls):
        return super(Budget, cls)._childs_depends() + ['fiscalyear']

    @classmethod
    def __setup__(cls):
        super(Budget, cls).__setup__()
        cls._buttons.update({
                'distribute_periods': {
                    'invisible': Bool(Eval('periods', [1])),
                    },
                })
        cls._error_messages.update({
                'invalid_period_amount': (
                    'The period amount "%(period_amount)s" of budget '
                    '"%(budget)s" can not be higher than its own amount '
                    '"%(amount)s".'
                    ),
                })

    @classmethod
    def _get_balance_query(cls, sub_ids):
        pool = Pool()
        BudgetAccount = pool.get('account.budget-account.account')
        MoveLine = pool.get('account.move.line')
        Move = pool.get('account.move')
        Period = pool.get('account.period')

        table_a = cls.__table__()
        table_c = cls.__table__()
        account = BudgetAccount.__table__()
        line = MoveLine.__table__()
        move = Move.__table__()
        period = Period.__table__()
        balance = Sum( Coalesce(line.credit, 0) -Coalesce(line.debit, 0) )

        #print "BALANCE: " + str(balance)

        return table_a.join(table_c,
            condition=(table_c.left >= table_a.left)
            & (table_c.right <= table_a.right)
            ).join(account, condition=account.budget == table_c.id
            ).join(period,
            condition=period.fiscalyear == table_c.fiscalyear
            ).join(move, condition=move.period == period.id
            ).join(line, condition=(
                (line.account == account.account)
                & (line.move == move.id))
            ).select(table_a.id, balance,
            where=reduce_ids(table_a.id, sub_ids),
            group_by=table_a.id)

    @classmethod
    @ModelView.button_action('account_budget.wizard_copy_budget')
    def copy_budget(cls, budgets):
        pass

    @classmethod
    @ModelView.button_action('account_budget.wizard_distribute_periods')
    def distribute_periods(cls, budgets):
        pass

    @classmethod
    def copy(cls, budgets, default=None):
        if default is None:
            default = {}
        default.setdefault('periods')
        return super(Budget, cls).copy(budgets, default=default)

    def check_amounts(self):
        super(Budget, self).check_amounts()
        period_amount = sum((p.amount for p in self.periods), Decimal(0))
        if abs(period_amount) > abs(self.amount):
            self.raise_user_error('invalid_period_amount', {
                    'period_amount': period_amount,
                    'amount': self.amount,
                    'budget': self.rec_name,
                    })

    def distribute_linear(self, period, periods):
        return self.amount / Decimal(len(periods))

    def distribute(self, method_name, periods, create=True):
        pool = Pool()
        BudgetPeriod = pool.get('account.budget.period')
        method = getattr(self, 'distribute_%s' % method_name)
        to_create = []
        if not self.periods:
            for period in periods:
                budget_period = BudgetPeriod()
                budget_period.budget = self
                budget_period.period = period
                amount = self.company.currency.round(method(period, periods),
                    rounding=ROUND_DOWN)
                budget_period.amount = amount
                to_create.append(budget_period)
        for child in self.children:
            to_create.extend(child.distribute(
                    method_name, periods, create=False))
        if create:
            BudgetPeriod.save(to_create)
        return to_create

class BudgetAccount(ModelSQL):
    'Account Budget - Account'
    __name__ = 'account.budget-account.account'
    
    budget = fields.Many2One('account.budget', "Budget", select=True,
        required=True, ondelete="CASCADE")
    account = fields.Many2One('account.account', "Account", select=True,
        required=True, ondelete="CASCADE")

class BudgetPeriod(BalanceMixin, ModelSQL, ModelView):
    'Account Budget Period'
    __name__ = 'account.budget.period'
    budget = fields.Many2One('account.budget', "Budget", select=True,
        required=True, ondelete="CASCADE",
        help="The budget of this period distribution.")
    fiscalyear = fields.Function(fields.Many2One(
            'account.fiscalyear', 'Fiscal Year'), 'on_change_with_fiscalyear')
    period = fields.Many2One('account.period', "Period", required=True,
        help="The period to restrict the amount to.",
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ],
        depends=['fiscalyear'])

    @fields.depends('budget')
    def on_change_with_fiscalyear(self, name=None):
        if self.budget and self.budget.fiscalyear:
            return self.budget.fiscalyear.id

    @fields.depends('budget')
    def on_change_with_currency(self, name=None):
        if self.budget:
            return self.budget.currency.id

    @classmethod
    def _get_balance_query(cls, sub_ids):
        pool = Pool()
        Budget = pool.get('account.budget')
        BudgetAccount = pool.get('account.budget-account.account')
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        table = cls.__table__()
        table_a = Budget.__table__()
        table_c = Budget.__table__()
        account = BudgetAccount.__table__()
        move = Move.__table__()
        line = MoveLine.__table__()
        balance = Sum(Coalesce(line.credit, 0) - Coalesce(line.debit, 0)) 
        return table.join(table_a,
            condition=(table_a.id == table.budget)
            ).join(table_c,
            condition=(table_c.left >= table_a.left)
            & (table_c.right <= table_a.right)
            ).join(account, condition=account.budget == table_c.id
            ).join(line, condition=line.account == account.account
            ).join(move, condition=((move.id == line.move)
                & (move.period == table.period))).select(
            table.id, balance,
            where=reduce_ids(table.id, sub_ids),
            group_by=table.id)

    @classmethod
    def validate(cls, periods):
        super(BudgetPeriod, cls).validate(periods)
        budgets = {p.budget for p in periods}
        for budget in budgets:
            budget.check_amounts()


class CopyBudgetStartMixin(ModelView):
    'Copy Budget Start'
    __name__ = 'account.budget.copy.start'
    name = fields.Char("Name", required=True,
        help="The main identifier of the new created budget.")
    zero_amounts = fields.Boolean("Zero Amounts",
        help="Check to reset all the budget amounts to zero.")


class CopyBudgetStart(CopyBudgetStartMixin):
    'Copy Budget Start'
    __name__ = 'account.budget.copy.start'
    company = fields.Many2One('company.company', "Company", readonly=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        help="The fiscalyear on which the new created budget will apply.",
        domain=[
            ('company', '=', Eval('company')),
            ],
        depends=['company'])

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')


class CopyBudgetMixin(Wizard):
    _start_fields = ['name']

    def default_start(self, field_names):
        pool = Pool()
        context = Transaction().context
        Budget = pool.get(context['active_model'])
        budget = Budget(context['active_id'])
        defaults = {}
        for name in self._start_fields:
            defaults[name] = getattr(budget, name)
        return defaults

    def default_values(self):
        return {'name': self.start.name}

    def write_values(self):
        values = {}
        if self.start.zero_amounts:
            values['amount'] = Decimal(0)
        return values

    def do_copy(self, action):
        pool = Pool()
        Budget = pool.get(Transaction().context['active_model'])
        budgets = Budget.browse(Transaction().context['active_ids'])
        new_budgets = Budget.copy(budgets, default=self.default_values())
        budget_ids = [b.id for b in new_budgets]
        to_write = Budget.search([('parent', 'child_of', budget_ids)])
        Budget.write(to_write, self.write_values())

        data = {'res_id': budget_ids}
        if len(new_budgets) == 1:
            action['views'].reverse()
        return action, data


class CopyBudget(CopyBudgetMixin):
    'Copy Budget'
    __name__ = 'account.budget.copy'
    start = StateView('account.budget.copy.start',
        'account_budget.copy_budget_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Copy', 'copy', 'tryton-ok', default=True),
            ])
    copy = StateAction('account_budget.act_budget_form')

    def write_values(self):
        values = super(CopyBudget, self).write_values()
        values.update({
                'fiscalyear': self.start.fiscalyear.id,
                })
        return values


class DistributePeriodStart(ModelView):
    'Distribute Periods Start'
    __name__ = 'account.budget.distribute_period.start'

    method = fields.Selection([
            ('linear', "Linear"),
            ], "Distribution Method", required=True)

    @classmethod
    def default_method(cls):
        return 'linear'


class DistributePeriod(Wizard):
    'Distribute Budget'
    __name__ = 'account.budget.distribute_period'
    start = StateView('account.budget.distribute_period.start',
        'account_budget.distribute_period_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Distribute", 'distribute', 'tryton-ok', default=True),
            ])
    distribute = StateTransition()

    def transition_distribute(self):
        pool = Pool()
        Budget = pool.get('account.budget')
        Period = pool.get('account.period')

        budget = Budget(Transaction().context['active_id'])
        periods = Period.search([
                ('fiscalyear', '=', budget.fiscalyear.id),
                ])
        budget.distribute(self.start.method, periods)
        return 'end'
