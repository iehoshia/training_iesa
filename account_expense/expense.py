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

from numero_letras import numero_a_moneda

__all__ = [
    'Move',
    'Expense',
    'ExpenseLine',
    'ExpenseContext', 
    'ExpenseMoveLine',
    'ExpenseMoveReference',
    'ExpenseReport',
    'CancelExpenses',
    'CancelExpensesDefault',
    ]  
__metaclass__ = PoolMeta

_STATES = {
    'readonly': Eval('state') != 'draft',
}
_DEPENDS = ['state']

_ZERO = Decimal('0.0')

STATES = [
    ('draft', 'Draft'),
    ('posted', 'Posted'),
    ('quotation', 'Quotation'),
    ('canceled', 'Canceled'),
    ]

class Move(ModelSQL, ModelView):
    'Account Move'
    __metaclass__ = PoolMeta
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        origins = super(Move, cls)._get_origin()
        origins.append('account.iesa.expense')
        return origins


class Expense(Workflow, ModelView, ModelSQL):
    'Account Expense'
    __name__ = 'account.iesa.expense'
    _order_name = 'number'

    company = fields.Many2One('company.company', 'Company', required=True,
        states=_STATES, select=True, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=_DEPENDS)
    number = fields.Char('Number', size=None, select=True, 
        required=False)
    reference = fields.Char('Reference', size=None, states=_STATES,
        depends=_DEPENDS)
    description = fields.Char('Description', size=None, states=_STATES,
        depends=_DEPENDS, required=True)
    state = fields.Selection(STATES, 'State', readonly=True)
    date = fields.Date('Expense Date',
        states={
            'readonly': Eval('state').in_(['posted', 'canceled']),
            'required': Eval('state').in_(['draft','posted'],),
            },
        depends=['state'])
    accounting_date = fields.Date('Accounting Date', states=_STATES,
        depends=_DEPENDS)
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states=_STATES, depends=_DEPENDS)
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    currency_date = fields.Function(fields.Date('Currency Date'),
        'on_change_with_currency_date')
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        states=_STATES, depends=_DEPENDS,
        domain=[('type', 'in', ['cash', 'statement'])]) 
    account = fields.Many2One('account.account', 'Account', 
        required=False,
        states=_STATES, depends=_DEPENDS + ['company'],
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    move = fields.Many2One('account.move', 'Move', readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    cancel_move = fields.Many2One('account.move', 'Cancel Move', readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    lines = fields.One2Many('account.iesa.expense.line','expense', 
        'Expense Lines',
        required=True,
        states=_STATES, depends=_DEPENDS+['company'],
        context={'description':Eval('description')},
        domain=[
            ('company', '=', Eval('company', -1)),
        ])
    existing_move_lines = fields.Function(fields.Many2Many('account.move.line', None, None, 
            'Expense Moves',
            domain=[
                ('company','=',Eval('company',-1))
            ],
            states=_STATES,
            depends=['state','company'],
        ),'get_moves')
    amount = fields.Numeric('Amount', digits=(16,
                Eval('currency_digits', 2)), 
                depends=['currency_digits'],
                required=True, 
                states=_STATES, 
                )
    comment = fields.Text('Comment', states=_STATES, depends=_DEPENDS)
    ticket = fields.Char('Ticket',  states=_STATES, 
        required=False)
    receipt = fields.Char('Receipt')
    party = fields.Many2One('party.party','Party',
        required=True, 
        states=_STATES, 
        domain=['AND',
            [('company', '=', Eval('context', {}).get('company', -1))],
            [('is_provider','=',True)],
        ],
        help='The party that generate the expense',
    )

    @classmethod
    def __setup__(cls):
        super(Expense, cls).__setup__()
        cls._order = [
            ('number', 'DESC'),
            ('id', 'DESC'),
            ]
        cls._error_messages.update({
                'missing_account_receivable': ('Missing Account Revenue.'),
                'missing_account_credit': ('Missing Account Credit.'),
                'amount_can_not_be_zero': ('Amount to Pay can not be zero.'),
                'post_unbalanced_expense': ('You can not post expense "%s" because '
                    'it is an unbalanced.'),
                'modify_expense': ('You can not modify expense "%s" because '
                    'it is posted or cancelled.'),
                'delete_cancel': ('Expense "%s" must be cancelled before '
                    'deletion.'),
                'delete_numbered': ('The numbered expense "%s" can not be '
                    'deleted.'),
                })
        cls._transitions |= set((
                ('draft', 'canceled'),
                ('draft', 'quotation'),
                ('quotation', 'posted'),
                ('quotation', 'draft'),
                ('quotation', 'canceled'),
                ('canceled', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'quotation']),
                    'icon': 'tryton-cancel',
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': Eval('state').in_(['draft','posted','canceled']),
                    'icon': If(Eval('state') == 'canceled',
                        'tryton-clear', 'tryton-go-previous'),
                    'depends': ['state'],
                    },
                'quote': {
                    'invisible': Eval('state') != 'draft',
                    'icon': 'tryton-go-next',
                    'depends': ['state'],
                    },
                'post': {
                    'invisible': Eval('state') != 'quotation',
                    'icon': 'tryton-ok',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query=False):
        transaction = Transaction().context 
        
        party = transaction.get('party')
        date = transaction.get('date')
        
        domain = domain[:]
        if party is not None: 
            domain = [domain, ('party','=',party)]
        if date is not None:  
            domain = [domain, ('date','=',date)] 

        records = super(Expense, cls).search(domain, offset=offset, limit=limit,
             order=order, count=count, query=query)

        if Transaction().user:
            # Clear the cache as it was not cleaned for confidential 
            cache = Transaction().get_cache()
            cache.pop(cls.__name__, None)
        return records

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('number',) + tuple(clause[1:]),
            ('description',) + tuple(clause[1:]),
            ('party',) + tuple(clause[1:]),
            ('ticket',) + tuple(clause[1:]),
            ]

    def get_rec_name(self, name):
        if self.number:
            return self.number
        elif self.description:
            return '[%s]' % self.description
        return '(%s)' % self.id

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.id

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.digits
        return 2

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def default_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    @fields.depends('party','lines','existing_move_lines','company','description')
    def on_change_party(self, name=None):
        pool = Pool()
        Line = pool.get('account.iesa.expense.line')
        MoveLine = pool.get('account.move.line')

        self.lines = []
        self.existing_move_lines = []
        self.invoices = []
        

        if self.party is not None: 
            party = self.party.id
            description = self.description
            lines = []
            line = Line()
            line.party = party
            line.description = description
            line.expense_state = 'draft'
            line.company = self.company.id
            line.amount = 0
            lines.append(line)
            self.lines = lines 

    def get_moves(self, name=None):
        moves = []
        return moves

    @fields.depends('journal', 'account', 'ticket')
    def on_change_journal(self, name=None):
        self.account = None
        if self.journal: 
            Sequence = Pool().get('ir.sequence') 
            self.account = self.journal.debit_account.id

    @fields.depends('lines','existing_move_lines')
    def on_change_lines (self, name=None):
        found_invoices = []
        MoveLine = Pool().get('account.move.line')
        
        parties = [] 
        if self.lines:
            for line in self.lines:
                if line.party: 
                    parties.append(line.party.id)
        if parties is not []:
            found_moves = MoveLine.search([('party','in',parties)])
            if found_moves is not None: 
                self.existing_move_lines = found_moves 

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @fields.depends('date')
    def on_change_with_currency_date(self, name=None):
        Date = Pool().get('ir.date')
        return self.date or Date.today()

    @classmethod
    def set_number(cls, expenses):
        '''
        Fill the number field with the expense sequence
        '''
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('sale.configuration')

        config = Config(1)
        for expense in expenses:
            if expense.number:
                continue
            expense.number = Sequence.get_id(
                config.iesa_expense_sequence.id)
        cls.save(expenses)

    @fields.depends('date')
    def on_change_with_currency_date(self, name=None):
        Date = Pool().get('ir.date')
        return self.date or Date.today()

    def get_move(self):

        pool = Pool()
        Move = pool.get('account.move')    
        Period = pool.get('account.period')
        MoveLine = pool.get('account.move.line')
        
        journal = self.journal 
        date = self.date
        amount = self.amount
        description = self.number + ' - ' + self.description + ' - ' + self.reference
        ticket = self.ticket
        origin = self 
        lines = []

        credit_line = MoveLine(description=self.description)
        credit_line.debit, credit_line.credit = 0, self.amount
        credit_line.account = self.account
        
        if not credit_line.account:
            self.raise_user_error('missing_account_credit')

        lines.append(credit_line)
        
        for line in self.lines: 
            if line.account.party_required:
                new_line = MoveLine(description=line.description, account=line.account, party=line.party)
            else:
                new_line = MoveLine(description=line.description, account=line.account)
            new_line.debit, new_line.credit = line.amount, 0
            lines.append(new_line)

        period_id = Period.find(self.company.id, date=date)

        move = Move(journal=journal, period=period_id, date=date,
            company=self.company, lines=lines, origin=self, description=description)
        move.save()
        Move.post([move])

        return move


    @classmethod
    @ModelView.button
    @Workflow.transition('canceled')
    def cancel(cls, expenses):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')

        cancel_moves = []
        delete_moves = []
        to_save = []
        for expense in expenses:
            if expense.move:
                if expense.move.state == 'draft':
                    delete_moves.append(expense.move)
                elif not expense.cancel_move:
                    expense.cancel_move = expense.move.cancel()
                    to_save.append(expense)
                    cancel_moves.append(expense.cancel_move)
        if cancel_moves:
            Move.save(cancel_moves)
        cls.save(to_save)
        if delete_moves:
            Move.delete(delete_moves)
        if cancel_moves:
            Move.post(cancel_moves)
        # Write state before reconcile to prevent expense to go to paid state
        cls.write(expenses, {
                'state': 'canceled',
                })
        # Reconcile lines to pay with the cancellation ones if possible
        for expense in expenses:
            if not expense.move or not expense.cancel_move:
                continue
            to_reconcile = []
            for line in expense.move.lines + expense.cancel_move.lines:
                if line.account == expense.account:
                    if line.reconciliation:
                        break
                    to_reconcile.append(line)
            else:
                if to_reconcile:
                    Line.reconcile(to_reconcile)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, expenses):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    def quote(cls, expenses):
        for expense in expenses: 
            company = expense.company
            total_amount = expense.amount
            current_amount = 0

            for line in expense.lines: 
                current_amount += line.amount 
            balance = total_amount - current_amount

            if not company.currency.is_zero(balance):
                cls.raise_user_error('post_unbalanced_expense', (expense.rec_name,))
        cls.set_number(expenses)

    @classmethod
    @ModelView.button_action(
        'account_expense.report_iesa_expense')
    @Workflow.transition('posted')
    def post(cls, expenses):
        
        '''
        Post de expense
        '''

        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')
        
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        expenses_ids = cls.browse([e for e in expenses])
        for expense in expenses_ids: 
            move = expense.get_move()
            expense.accounting_date = Date.today()
            moves = []
            if move != expense.move: 
                expense.move = move
                moves.append(move)
            if moves:
                Move.save(moves)
            expense.state = 'posted'
        cls.save(expenses_ids)

    @classmethod
    def check_modify(cls, expenses):
        '''
        Check if the expenses can be modified
        '''
        for expense in expenses:
            if (expense.state in ('posted', 'cancel') ):
                cls.raise_user_error('modify_expense', (expense.rec_name,))

    @classmethod
    def delete(cls, expenses):
        cls.check_modify(expenses)
        # Cancel before delete
        cls.cancel(expenses)
        for expense in expenses:
            if expense.state != 'canceled':
                cls.raise_user_error('delete_cancel', (expense.rec_name,))
            if expense.number:
                cls.raise_user_error('delete_numbered', (expense.rec_name,))
        ExpenseLine.delete([l for e in expenses for l in e.lines])
        super(Expense, cls).delete(expenses)

class ExpenseMoveReference(ModelView, ModelSQL):
    'Expense Move Reference'
    __name__ = 'account.iesa.expense.move.line'

    expense = fields.Many2One('account.iesa.expense','Expense')
    party = fields.Many2One('party.party','Party')
    description = fields.Char('Description')
    amount = fields.Numeric('Amount')

class ExpenseLine(ModelView, ModelSQL):
    'Expense Line'
    __name__ = 'account.iesa.expense.line'

    _states = {
        'readonly': Eval('expense_state') != 'draft',
        }
    _depends = ['expense_state']

    expense_state = fields.Function(fields.Selection(STATES, 'Expense State'),
        'on_change_with_expense_state')
    expense = fields.Many2One('account.iesa.expense','Expense', required=True)
    account = fields.Many2One('account.account','Account', 
        required=True, 
        domain=[('company','=',Eval('company', -1) )],
        states={
            'readonly': _states['readonly'],
            },
        depends=['expense'] + _depends,
        )
    description = fields.Char('Description')
    party = fields.Many2One('party.party','Party',
        required=True, 
        domain=['AND',
            [('company', '=', Eval('context', {}).get('company', -1))],
            [('is_provider','=',True)],
        ],
        states={
            'readonly': _states['readonly'],
            },
        depends=['expense','_parent_expense','company'] + _depends ,
        )
    party_required = fields.Function(fields.Boolean('Party Required'),
        'on_change_with_party_required')
    amount = fields.Numeric('Amount', 
                    digits=(16, Eval('currency_digits', 2)), 
                    required=True, 
        states={
            'required': ~Eval('expense'),
            'readonly': _states['readonly'],
            },
        depends=['expense','currency_digits'] + _depends,
        )
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    company = fields.Many2One('company.company','Company')

    #@staticmethod
    #def default_party():  


    @fields.depends('account')
    def on_change_with_party_required(self, name=None):
        if self.account:
            return self.account.party_required
        return False

    @fields.depends('expense', '_parent_expense.state')
    def on_change_with_expense_state(self, name=None):
        if self.expense:
            return self.expense.state
        return 'draft'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_account():
        AccountConfiguration = Pool().get('account.configuration')
        account_config = AccountConfiguration(1)
        default_account_receivable = account_config.get_multivalue('default_account_receivable')
        if default_account_receivable: 
            return default_account_receivable.id
        return None

    @staticmethod
    def default_amount():
        return Decimal('0.0')

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.id

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.digits
        return 2

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_description():
        description = Transaction().context.get('description') or ''
        return description

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

class InvoiceParty(ModelSQL):
    'Invoice - Party'
    __name__ = 'account.invoice-party.party'
    _table = 'invoice_party_rel'

    invoice = fields.Many2One('account.invoice', 'Invoice', ondelete='CASCADE',
            required=True, select=True)
    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
            required=True, select=True)

class ExpenseMoveLine(ModelSQL):
    'Expense - Move Line'
    __name__ = 'account.iesa.expense-account.move.line'
    _table = 'expense_move_line_rel'

    line = fields.Many2One('account.move.line', 'Line', ondelete='CASCADE',
            required=True, select=True)
    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
            required=True, select=True)

class GeneralLedger(Report):
    __name__ = 'account.iesa.report_general_ledger'

    @classmethod
    def get_context(cls, records, data):
        pool = Pool()
        Company = pool.get('company.company')
        Fiscalyear = pool.get('account.fiscalyear')
        Period = pool.get('account.period')
        context = Transaction().context

        report_context = super(GeneralLedger, cls).get_context(records, data)

        report_context['company'] = Company(context['company'])
        report_context['fiscalyear'] = Fiscalyear(context['fiscalyear'])

        for period in ['start_period', 'end_period']:
            if context.get(period):
                report_context[period] = Period(context[period])
            else:
                report_context[period] = None
        report_context['from_date'] = context.get('from_date')
        report_context['to_date'] = context.get('to_date')
        report_context['accounts'] = records

        return report_context

class ExpenseReport(Report):
    'Expense Receipt'
    __name__ = 'account.iesa.expense.report'

    @classmethod
    def get_context(cls, records, data):

        report_context = super(ExpenseReport, cls).get_context(records, data)

        amount = 0
        for record in records: 
            amount = record.amount
        Company = Pool().get('company.company')
        company = Company(Transaction().context.get('company'))


        amount_on_letters = numero_a_moneda(amount)
        report_context['company'] = company
        report_context['amount_on_letters'] = amount_on_letters
        
        return report_context

class ExpenseContext(ModelView):
    'Expense Context'
    __name__ = 'account.iesa.expense.context'

    date = fields.Date('Date')
    party = fields.Many2One('party.party','Party',
        domain=[
            ('company', '=', Eval('context', {}).get('company', -1))],
        help='The party that generate the expense',
    )

class CancelExpenses(Wizard):
    'Cancel Expenses'
    __name__ = 'account.iesa.expense.cancel'
    start_state = 'default'
    default = StateView('account.iesa.expense.cancel.default',
        'account_expense.expense_cancel_default_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'cancel', 'tryton-ok', default=True),
            ])
    cancel = StateTransition()

    def default_cancel(self, move):
        default = {}
        if self.default.description:
            default['description'] = self.default.description
        return default

    def transition_cancel(self):
        pool = Pool()
        Expense = pool.get('account.iesa.expense')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')

        expenses = Expense.browse(Transaction().context['active_ids'])
        for expense in expenses: 
            move = expense.move
            if move is not None: 
                moves = Move.browse([move])
                for move in moves:
                    default = self.default_cancel(move)
                    cancel_move = move.cancel(default=default)
                    to_reconcile = defaultdict(list)
                    for line in move.lines + cancel_move.lines:
                        if line.account.reconcile:
                            to_reconcile[(line.account, line.party)].append(line)
                    for lines in to_reconcile.values():
                        Line.reconcile(lines)
        # Write state before reconcile to prevent expense to go to paid state
        Expense.write(expenses, {
                'state': 'canceled',
                })
        return 'end'

class CancelExpensesDefault(ModelView):
    'Cancel Expenses'
    __name__ = 'account.iesa.expense.cancel.default'
    description = fields.Char('Description')