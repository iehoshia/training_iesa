# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime
import calendar 
from datetime import timedelta, date  

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
    Button, StateReport
from trytond.report import Report
from trytond.tools import reduce_ids, grouped_slice
from trytond.pyson import Eval, If, PYSONEncoder, Bool, Not, Date
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.report import Report
from trytond.rpc import RPC

from trytond import backend

from numero_letras import numero_a_moneda

__all__ = [
    'Move',
    'CancelMoves',
    'GeneralLedgerAccountContext',
    'BalanceSheetContext',
    'IncomeStatementContext',
    'PrintGeneralJournalStart',
    'AccountMoveReport',
    'PaymentParty',
    'Payment',
    'PaymentMoveReference',
    'PaymentMoveLine',
    'GeneralLedger',
    'PaymentLine',
    'PaymentContext',
    'PaymentReceipt',
    'GeneralLedgerLine', 
    'PrintPaymentReportStart',
    'PrintPaymentReportWizard',
    'PrintPaymentReport',
    ]  
__metaclass__ = PoolMeta

_MOVE_STATES = {
    'readonly': Eval('state') == 'posted',
    }
_MOVE_DEPENDS = ['state']

_STATES = {
    'readonly': Eval('state') != 'draft',
}
_DEPENDS = ['state']

_TYPE = [
    ('out', 'Customer'),
    ('in', 'Supplier'),
]

_TYPE2JOURNAL = {
    'out': 'revenue',
    'in': 'expense',
}

_ZERO = Decimal('0.0')

STATES = [
    ('draft', 'Draft'),
    ('posted', 'Posted'),
    ('quotation', 'Quotation'),
    ('canceled', 'Canceled'),
    ]

_YEAR = datetime.datetime.now().year
_NOW = datetime.datetime.now()

def month_number_spanish(number):
    switcher = {
        0: "Enero",
        1: "Febrero",
        2: "Marzo",
        3: "Abril",
        4: "Mayo",
        5: "Junio",
        6: "Julio",
        7: "Agosto",
        8: "Septiembre",
        9: "Octubre",
        10: "Noviembre",
        11: "Diciembre",
    }
    return switcher.get(number, "None")

def month_name(number):
    Date = Pool().get('ir.date')
    today = Date.today()
    month = date.month
    return month

def allmonth(year):
    list = []
    for i in range(0,12):    
        label = month_number_spanish(i) + ' - ' +str(year)
        list.append( (i,label) ) 
    return list 

def first_day_month(date):
    first_day =  date.replace(day=1)
    return first_day

def last_day_month(date):
    last_day = date.replace(day = calendar.monthrange(date.year, date.month)[1])
    return last_day

class Move(ModelSQL, ModelView):
    'Account Move'
    __metaclass__ = PoolMeta
    __name__ = 'account.move'

    is_third_party = fields.Boolean('Party',
        states=_MOVE_STATES, depends=_MOVE_DEPENDS)
    third_party = fields.Char('Party',
        states={
                'readonly': Eval('state') == 'posted',
                'required': Eval('is_third_party', True),
                'invisible': ~Eval('is_third_party', True),
                }, depends=_MOVE_DEPENDS,
        )
    amount = fields.Function(fields.Numeric('Total Amount',
            digits=(16, 2)),'get_amount')
    amount_in_letters = fields.Function(fields.Numeric('Amount in Letters'),
        'get_amount_in_letters')
    ticket = fields.Char('Ticket',
        states=_MOVE_STATES, depends=_MOVE_DEPENDS)

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls._order = [
            ('post_date', 'ASC'),
            ('post_number','DESC'),
            ('id', 'ASC'),
            ]

    @classmethod
    def _get_origin(cls):
        origins = super(Move, cls)._get_origin()
        origins.append('account.iesa.payment')
        return origins

    def get_amount(self, name):
        amount = Decimal('0.0')
        if self.lines: 
            for line in self.lines: 
                amount += line.debit 
            amount = abs(amount)
            return amount 
        return amount 

    def get_ticket(self, name):
        if self.origin: 
            if self.origin.ticket:
                return self.origin.ticket 

    def get_amount_in_letters(self, name):
        amount_in_letters = numero_a_moneda(self.amount)
        return amount_in_letters

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('number',) + tuple(clause[1:]),
            ('post_number',) + tuple(clause[1:]),
            ('description',) + tuple(clause[1:]),
            ('journal',) + tuple(clause[1:]),
            (cls._rec_name,) + tuple(clause[1:]), 
            ]

class CancelMoves(Wizard):
    'Cancel Moves'
    __name__ = 'account.move.cancel'

    def transition_cancel(self):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')

        moves = Move.browse(Transaction().context['active_ids'])
        for move in moves:
            default = self.default_cancel(move)
            cancel_move = move.cancel(default=default)
            to_reconcile = defaultdict(list)
            for line in move.lines + cancel_move.lines:
                if line.account.reconcile:
                    to_reconcile[line.account, line.party].append(line)
            for lines in to_reconcile.values():
                Line.reconcile(lines)
        return 'end'

class GeneralLedgerAccountContext(ModelView):
    'General Ledger Account Context'
    __name__ = 'account.general_ledger.account.context'

    @classmethod
    def default_posted(cls):
        return True

class BalanceSheetContext(ModelView):
    'Balance Sheet Context'
    __name__ = 'account.balance_sheet.context'

    @staticmethod
    def default_posted():
        return True

    @classmethod
    def default_posted(cls):
        return True

class IncomeStatementContext(ModelView):
    'Income Statement Context'
    __name__ = 'account.income_statement.context'

    @classmethod
    def default_posted(cls):
        return True

class PrintGeneralJournalStart(ModelView):
    'Print General Journal'
    __name__ = 'account.move.print_general_journal.start'

    @classmethod
    def default_posted(cls):
        return True

class AnalyticAccountContext(ModelSQL, ModelView):
    'Analytic Account Context'
    __name__ = 'analytic_account.account.context'

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

    @classmethod
    def default_from_date(cls):
        return Transaction().context.get('from_date')

    @classmethod
    def default_to_date(cls):
        return Transaction().context.get('to_date')

class AccountMoveReport(Report):
    __name__ = 'account.move.report'

    @classmethod
    def get_context(cls, records, data):
        pool = Pool()
        Company = pool.get('company.company')
        context = Transaction().context

        report_context = super(AccountMoveReport, cls).get_context(records, data)

        report_context['company'] = Company(context['company'])
        
        report_context['from_date'] = context.get('from_date')
        report_context['to_date'] = context.get('to_date')

        return report_context

class PaymentParty(ModelSQL, ModelView):
    'Payment - Party'
    __name__ = 'account.iesa.payment-party.party'
    _table = 'payment_party_rel'

    payment = fields.Many2One('account.iesa.payment', 
            'Payment', ondelete='CASCADE',
            required=True, select=True)
    party = fields.Many2One('party.party', 
            'Party', ondelete='CASCADE',
            required=True, select=True,
            #domain=['AND',
            #        [('company','=',Eval('context', {}).get('company', -1) )],
            #        [('is_student','=',True)]
            #]
            )

class Payment(Workflow, ModelView, ModelSQL):
    'Payment'
    __name__ = 'account.iesa.payment'
    _order_name = 'number'

    company = fields.Many2One('company.company', 'Company', required=True,
        states=_STATES, select=True, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=_DEPENDS)
    is_third_party = fields.Boolean('Is Third Party')
    number = fields.Char('Number', size=None, select=True, 
        required=False)
    reference = fields.Char('Reference', size=None, states=_STATES,
        depends=_DEPENDS)
    description = fields.Char('Description', size=None, states=_STATES,
        depends=_DEPENDS, required=True,) 
    state = fields.Selection(STATES, 'State', readonly=True)
    invoice_date = fields.Date('Payment Date',
        states={
            'readonly': Eval('state').in_(['posted', 'canceled']),
            'required': Eval('state').in_(['draft','posted'],),
            },
        depends=['state'])
    accounting_date = fields.Date('Accounting Date', states=_STATES,
        depends=_DEPENDS)
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
        required=False, states=_STATES, depends=['state'],
        )

    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states=_STATES, depends=_DEPENDS)
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    currency_date = fields.Function(fields.Date('Currency Date'),
        'on_change_with_currency_date')
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        states=_STATES, depends=_DEPENDS,
        domain=[('type', '=', 'cash')])
    move = fields.Many2One('account.move', 'Move', readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    account = fields.Many2One('account.account', 'Account', 
        required=False,
        states=_STATES, depends=_DEPENDS + ['type', 'company'],
        domain=[
            ('company', '=', Eval('company', -1)),
            ('kind', '=', 'receivable'),
            ])
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', states=_STATES, depends=_DEPENDS,
        required=False)
    lines = fields.One2Many('account.iesa.payment.line','payment', 
        'Payment Lines',
        required=True,
        states=_STATES, depends=_DEPENDS+['company'],
        domain=[
            ('company', '=', Eval('company', -1)),
        ])
    invoices = fields.Function(fields.Many2Many('account.invoice', None, None, 
            'Invoices',
            domain=[
                ('company','=',Eval('company',-1))
            ],
            states=_STATES,
            depends=['state','company'],
        ),'get_invoices')
    existing_move_lines = fields.Function(fields.Many2Many('account.move.line', None, None, 
            'Payment Moves',
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
    amount_receivable = fields.Numeric('Balance',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'],
            readonly=False, )
    comment = fields.Text('Comment', states=_STATES, depends=_DEPENDS)
    ticket = fields.Char('Ticket',  states=_STATES, 
        required=True)
    receipt = fields.Char('Receipt')
    third_party = fields.Char('Third Party', 
        required=False, 
        states=_STATES, )
    subscriber = fields.Many2One('party.party','Subscriber',
        states=_STATES, 
        required=True, 
        domain=[
                ('company', '=', Eval('company',-1)),
                If(Not(Bool(Eval('is_third_party',False))),
                        ('is_subscriber', '=', True), 
                        ('active', '=', True), 
                    ) 
            ],
        depends=['company','is_third_party'],
        )        

    @classmethod
    def __setup__(cls):
        super(Payment, cls).__setup__()
        cls._order = [
            ('number', 'DESC'),
            ('id', 'DESC'),
            ]
        cls._error_messages.update({
                'missing_account_receivable': ('Missing Account Revenue.'),
                'amount_can_not_be_zero': ('Amount to Pay can not be zero.'),
                'post_unbalanced_payment': ('You can not post payment "%s" because '
                    'it is an unbalanced.'),
                'modify_payment': ('You can not modify payment "%s" because '
                    'it is posted or cancelled.'),
                'delete_cancel': ('Payment "%s" must be cancelled before '
                    'deletion.'),
                'delete_numbered': ('The numbered payment "%s" can not be '
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
        from_date = transaction.get('from_date')
        to_date = transaction.get('to_date')
        
        domain = domain[:]
        if party is not None: 
            domain = [domain, ('subscriber','=',party)]
        if from_date is not None:
            domain = [domain, ('invoice_date','>=',from_date)]
        if to_date is not None:
            domain = [domain, ('invoice_date','<=',to_date)] 


        records = super(Payment, cls).search(domain, offset=offset, limit=limit,
             order=order, count=count, query=query)

        if Transaction().user:
            # Clear the cache as it was not cleaned for confidential 
            cache = Transaction().get_cache()
            cache.pop(cls.__name__, None)
        return records

    @classmethod
    def delete(cls, payments):
        cls.check_modify(payments)
        # Cancel before delete
        cls.cancel(payments)
        PaymentLine = Pool().get('account.iesa.payment.line')
        for payment in payments:
            if payment.state != 'canceled':
                cls.raise_user_error('delete_cancel', (payment.rec_name,))
            if payment.number:
                cls.raise_user_error('delete_numbered', (payment.rec_name,))
        PaymentLine.delete([l for p in payment for l in p.lines])
        super(Payment, cls).delete(payments)

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('number',) + tuple(clause[1:]),
            ('description',) + tuple(clause[1:]),
            ('subscriber',) + tuple(clause[1:]),
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

    @staticmethod
    def default_journal():
        pool = Pool()
        Journal = pool.get('account.journal')
        journals = Journal.search([('name','=','Caja')])
        if len(journals)==1: 
            return journals[0].id

    @staticmethod
    def default_is_third_party():
        return False

    @classmethod
    def default_payment_term(cls):
        PaymentTerm = Pool().get('account.invoice.payment_term')
        payment_terms = PaymentTerm.search(cls.payment_term.domain)
        if len(payment_terms) == 1:
            return payment_terms[0].id

    @classmethod
    def default_invoice_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    def get_incoming_moves(self, name):
        moves = []
        if self.warehouse_input == self.warehouse_storage:
            return [m.id for m in self.moves]
        for move in self.moves:
            if move.to_location == self.warehouse_input:
                moves.append(move.id)
        return moves

    def __on_change_is_third_party_subscriber(self): 
        if self.state == 'draft': 
            pool = Pool()
            Subscription = pool.get('sale.subscription')
            Line = pool.get('account.iesa.payment.line')
            Invoice = pool.get('account.invoice')
            MoveLine = pool.get('account.move.line')
            AccountConfiguration = pool.get('account.configuration')
            account_config = AccountConfiguration(1)
            default_account_receivable = account_config.get_multivalue('default_account_receivable')

            self.lines = []
            self.existing_move_lines = []
            self.invoices = []
            self.amount_receivable = 0

            if self.subscriber is not None and self.is_third_party is False:
                party_id = self.subscriber.id
                subscriptions = Subscription.search([('party','=',party_id)])
                lines = []
                parties = []
                amount_receivable = 0
                if subscriptions is not None: 
                    for subscription in subscriptions:
                        line = Line()
                        line.party = subscription.student.id
                        line.payment_state = 'draft'
                        line.company = subscription.company.id
                        line.account = default_account_receivable.id
                        amount = 0 if subscription.student.receivable <= 0 else subscription.student.receivable
                        line.amount = amount
                        description = self.description if self.description is not None else ''
                        line.description = description
                        lines.append(line)
                        parties.append(subscription.student.id)
                        amount_receivable += amount
                    self.lines = lines
                    self.amount_receivable = amount_receivable
                    # TODO add date future 
                    print "PARTIES: " + str(parties)
                    invoices = Invoice.search([('party','in',parties),
                        ('state','=','posted'),
                        ])
                    if invoices is not None: 
                        self.invoices = invoices
                    # TODO add moves 
                    moves = MoveLine.search([('party','in',parties),
                        ('state','=','valid')])
                    if moves is not None: 
                        self.existing_move_lines = moves
            if self.subscriber is not None and self.is_third_party is True: 
                party_id = self.subscriber.id
                lines = []
                line = Line()
                line.party = party_id
                line.payment_state = 'draft'
                line.company = self.company.id
                line.account = default_account_receivable.id
                line.amount = 0
                lines.append(line)
                self.lines = lines 

    @fields.depends('subscriber','lines','existing_move_lines','is_third_party','company','state')
    def on_change_is_third_party(self, name=None):
        self.__on_change_is_third_party_subscriber() 

    @fields.depends('subscriber','lines','existing_move_lines','is_third_party','company','description','state')
    def on_change_subscriber(self, name=None):
        self.__on_change_is_third_party_subscriber()

    @fields.depends('subscriber','lines','existing_move_lines','is_third_party','company','description','state')
    def on_change_description(self, name=None):
        self.__on_change_is_third_party_subscriber()

    @fields.depends('subscriber','invoices','lines')
    def get_invoices(self, name=None):
        invoices = []
        return invoices

    def get_moves(self, name=None):
        moves = []
        return moves

    @fields.depends('lines','invoices','existing_move_lines')
    def on_change_lines (self, name=None):
        found_invoices = []
        Invoice = Pool().get('account.invoice')
        MoveLine = Pool().get('account.move.line')
        amount_receivable = 0 
        parties = [] 
        if self.lines:
            for line in self.lines:
                if line.party: 
                    parties.append(line.party.id)
                    amount = 0 if line.party.receivable <= 0 else line.party.receivable
                    amount_receivable += amount
        if parties is not []:
            found_invoices = Invoice.search([('party','in',parties)])
            found_moves = MoveLine.search([('party','in',parties)])
            if found_invoices is not None:  
                self.invoices = found_invoices 
            if found_moves is not None: 
                self.existing_move_lines = found_moves 
            self.amount_receivable = amount_receivable



    def __get_account_payment_term(self):
        '''
        Return default account and payment term
        '''
        self.account = None
        if self.party:
            if self.type == 'out':
                self.account = self.party.account_receivable_used
                if self.party.customer_payment_term:
                    self.payment_term = self.party.customer_payment_term
            elif self.type == 'in':
                self.account = self.party.account_payable_used
                if self.party.supplier_payment_term:
                    self.payment_term = self.party.supplier_payment_term

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @fields.depends('invoice_date')
    def on_change_with_currency_date(self, name=None):
        Date = Pool().get('ir.date')
        return self.invoice_date or Date.today()

    #@fields.depends('parties')
    #def on_change_with_party_lang(self, name=None):
    #    Config = Pool().get('ir.configuration')
    #    if self.party:
    #        if self.party.lang:
    #            return self.party.lang.code
    #    return Config.get_language()

    #@fields.depends('company')
    #def on_change_with_company_party(self, name=None):
    #    if self.company:
    #        return self.company.party.id

    @classmethod
    def set_number(cls, payments):
        '''
        Fill the number field with the payment sequence
        '''
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('sale.configuration')

        config = Config(1)
        for payment in payments:
            if payment.number:
                continue
            payment.number = Sequence.get_id(
                config.iesa_payment_sequence.id)
        cls.save(payments)

    @fields.depends('invoice_date')
    def on_change_with_currency_date(self, name=None):
        Date = Pool().get('ir.date')
        return self.invoice_date or Date.today()

    @classmethod
    def check_modify(cls, payments):
        '''
        Check if the payments can be modified
        '''
        for payment in payments:
            if (payment.state in ('posted', 'cancel') ):
                cls.raise_user_error('modify_payment', (payment.rec_name,))

    def _pay_invoice_wizard(self, invoice, amount_to_pay):
        PayWizard = Pool().get('account.invoice.pay', type='wizard')
        pool = Pool()
        start = pool.get('account.invoice.pay.start')
        ask = pool.get('account.invoice.pay.ask')
        
        with Transaction().set_context(current_invoice=invoice):
            session_id, _, _ = PayWizard.create()
            pay_wizard = PayWizard(session_id)
            start.journal = self.journal
            start.currency = self.currency 
            start.amount = amount_to_pay
            start.date = self.invoice_date 
            start.description = self.description
            start.third_party = self.description
            start.ticket = self.description
            start.receipt = self.description
            ask.type = 'partial'
            ask.amount = amount_to_pay
            pay_wizard.start = start 
            pay_wizard.ask=ask 
            pay_wizard.transition_choice()
            pay_wizard.transition_pay()
            pay_wizard.do_print_()

    def get_move(self):

        pool = Pool()
        Move = pool.get('account.move')    
        MoveLine = pool.get('account.move.line')
        Period = pool.get('account.period')
        
        journal = self.journal 
        date = self.invoice_date
        amount = self.amount
        move_description = self.number + ' - ' + self.description
        ticket =  self.ticket
        origin = self 
        lines = []
        
        for line in self.lines: 
            description = line.description or self.description
            if line.account.party_required:
                new_line = MoveLine(description=description, account=line.account, party=line.party)
            else:
                new_line = MoveLine(description=description, account=line.account)
            new_line.debit, new_line.credit = 0, line.amount
            lines.append(new_line)
        
        credit_line = MoveLine(description=self.description, )
        credit_line.debit, credit_line.credit = self.amount, 0
        account_journal = 'debit_account'
        credit_line.account = getattr(journal, account_journal)
        
        if not credit_line.account:
            self.raise_user_error('missing_%s' % account_journal,
                (journal.rec_name,))

        lines.append(credit_line)

        period_id = Period.find(self.company.id, date=date)

        move = Move(journal=journal, period=period_id, date=date, state='draft', 
            company=self.company, lines=lines, origin=self, description=move_description,
            ticket=ticket)
        move.save()
        if move.state != 'posted':
            Move.post([move])

        return move

    @classmethod
    @ModelView.button
    @Workflow.transition('canceled')
    def cancel(cls, payments):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, payments):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    def quote(cls, payments):
        for payment in payments: 
            company = payment.company
            total_amount = payment.amount
            current_amount = 0

            for line in payment.lines: 
                current_amount += line.amount 
            balance = total_amount - current_amount

            if not company.currency.is_zero(balance):
                cls.raise_user_error('post_unbalanced_payment', (payment.rec_name,))
        cls.set_number(payments)

    @classmethod
    @ModelView.button_action(
        'account_iesa.report_iesa_payment')
    @Workflow.transition('posted')
    def post(cls, payments):
        
        '''
        Adds a payment of amount to an invoice using the journal, date and
        description.
        Returns the payment line.
        '''

        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')
        Invoice = pool.get('account.invoice')
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')
        move = None 

        payments_ids = cls.browse([p for p in payments])
        for payment in payments_ids: 
            move = payment.get_move()
            payment.accounting_date = Date.today()
            moves = []
            if move != payment.move: 
                payment.move = move
                moves.append(move)
            if moves:
                Move.save(moves)
            payment.state = 'posted'
        cls.save(payments_ids)

class PaymentMoveReference(ModelView, ModelSQL):
    'Payment Move Reference'
    __name__ = 'account.iesa.payment.move.line'

    payment = fields.Many2One('account.iesa.payment','Payment')
    party = fields.Many2One('party.party','Party')
    description = fields.Char('Description')
    amount = fields.Numeric('Amount')


class PaymentLine(ModelView, ModelSQL):
    'Payment Line'
    __name__ = 'account.iesa.payment.line'

    _states = {
        'readonly': Eval('payment_state') != 'draft',
        }
    _depends = ['payment_state']

    _student_domain = ['AND',
            ['company','=',Eval('company',-1)],
            ['is_student','=',True]
        ]
    _subscriber_domain = ['AND',
            ['company','=',Eval('company',-1)],
            ['is_subscriber','=',True]
        ]

    payment_state = fields.Function(fields.Selection(STATES, 'Payment State'),
        'on_change_with_payment_state')
    payment_third_party = fields.Function(fields.Boolean('Is Third Party'),
        'on_change_with_payment_third_party')
    payment = fields.Many2One('account.iesa.payment','Payment', required=True)
    account = fields.Many2One('account.account','Account', 
        required=True, 
        domain=[('company','=',Eval('company', -1) )],
        states={
            'readonly': _states['readonly'],
            },
        depends=['payment'] + _depends,
        )
    description = fields.Char('Description')
    party = fields.Many2One('party.party','Party',
        required=True, 
        domain=['AND',
            [('company','=',Eval('company',-1))],
            #[('is_subscriber', '=', ~Eval('_parent_payment.is_third_party',False) )],
        ],
        states={
            #'required': ~Eval('payment'),
            #'required': Eval('party_required', False),
            'readonly': _states['readonly'],
            },
        depends=['payment','_parent_payment','company'] + _depends ,
        )
    party_required = fields.Function(fields.Boolean('Party Required'),
        'on_change_with_party_required')
    amount = fields.Numeric('Amount', 
                    digits=(16, Eval('currency_digits', 2)), 
                    required=True, 
        states={
            'required': ~Eval('payment'),
            'readonly': _states['readonly'],
            },
        depends=['payment','currency_digits'] + _depends,
        )
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    company = fields.Many2One('company.company','Company')

    @classmethod
    def __setup__(cls):
        super(PaymentLine, cls).__setup__()
        cls.__rpc__.update({
                'on_write': RPC(instantiate=0),
                })
        cls._order[0] = ('id', 'DESC')


    @fields.depends('account')
    def on_change_with_party_required(self, name=None):
        if self.account:
            return self.account.party_required
        return False

    @fields.depends('payment', '_parent_payment.is_third_party')
    def on_change_with_payment_third_party(self, name=None):
        if self.payment:
            return self.payment.is_third_party
        return False

    @fields.depends('payment', '_parent_payment.state')
    def on_change_with_payment_state(self, name=None):
        if self.payment:
            return self.payment.state
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

class PaymentMoveLine(ModelSQL):
    'Payment - Move Line'
    __name__ = 'account.iesa.payment-account.move.line'
    _table = 'payment_move_line_rel'

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

class PaymentReceipt(Report):
    'Payment Receipt'
    __name__ = 'account.iesa.payment.report'

    #@classmethod
    #def _get_records(cls, ids, model, data):
    #    return None 

    @classmethod
    def get_context(cls, records, data):

        report_context = super(PaymentReceipt, cls).get_context(records, data)

        amount = 0
        for record in records: 
            amount = record.amount

        amount_on_letters = numero_a_moneda(amount)
        report_context['amount_on_letters'] = amount_on_letters
        
        return report_context

class GeneralLedgerLine(ModelSQL, ModelView):
    __metaclass__ = PoolMeta
    'General Ledger Line'
    __name__ = 'account.general_ledger.line'

    move_ticket = fields.Char('Ticket')
    post_number = fields.Char('Post Number')

    @classmethod
    def table_query(cls):
        pool = Pool()
        Line = pool.get('account.move.line')
        Move = pool.get('account.move')
        LedgerAccount = pool.get('account.general_ledger.account')
        Account = pool.get('account.account')
        transaction = Transaction()
        database = transaction.database
        context = transaction.context
        line = Line.__table__()
        move = Move.__table__()
        account = Account.__table__()
        columns = []
        for fname, field in cls._fields.iteritems():
            if hasattr(field, 'set'):
                continue
            field_line = getattr(Line, fname, None)
            if fname == 'balance':
                if database.has_window_functions():
                    w_columns = [line.account]
                    if context.get('party_cumulate', False):
                        w_columns.append(line.party)
                    column = Sum(line.debit - line.credit,
                        window=Window(w_columns,
                            order_by=[move.date.asc, line.id])).as_('balance')
                else:
                    column = (line.debit - line.credit).as_('balance')
            elif fname == 'move_description':
                column = Column(move, 'description').as_(fname)
            elif fname == 'move_ticket':
                column = Column(move, 'ticket').as_(fname)
            elif fname == 'post_number':
                column = Column(move, 'post_number').as_(fname)
            elif fname == 'party_required':
                column = Column(account, 'party_required').as_(fname)
            elif (not field_line
                    or fname == 'state'
                    or isinstance(field_line, fields.Function)):
                column = Column(move, fname).as_(fname)
            else:
                column = Column(line, fname).as_(fname)
            columns.append(column)
        start_period_ids = set(LedgerAccount.get_period_ids('start_balance'))
        end_period_ids = set(LedgerAccount.get_period_ids('end_balance'))
        period_ids = list(end_period_ids.difference(start_period_ids))
        with Transaction().set_context(periods=period_ids):
            line_query, fiscalyear_ids = Line.query_get(line)
        return line.join(move, condition=line.move == move.id
            ).join(account, condition=line.account == account.id
                ).select(*columns, where=line_query)

class PaymentContext(ModelView):
    'Payment Context'
    __name__ = 'account.iesa.payment.context'

    #date = fields.Date('Date')
    party = fields.Many2One('party.party','Party',
        domain=[
            ('company', '=', Eval('context', {}).get('company', -1))],
        help='The party that generate the expense',
    )
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
    company = fields.Many2One('company.company', 'Company', required=True,
        states=_STATES, select=True, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=_DEPENDS)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

class PrintPaymentReportStart(ModelView):
    'Print Payment Report Start'
    __name__ = 'print.payment.report.start'
    
    party = fields.Many2One('party.party','Party',
        domain=[
            ('company', '=', Eval('context', {}).get('company', -1))],
        help='The party that generate the payment',
    )
    date = fields.Date('Date', required=True,
        readonly=True)
    month = fields.Selection(allmonth(_YEAR), 'Month',
        sort=False)
    from_date = fields.Date("From Date",
        domain=[
            If(Eval('to_date') & Eval('from_date'),
                ('from_date', '<=', Eval('to_date')),
                ()),
            ],
        depends=['to_date'],
        required=True,)
    to_date = fields.Date("To Date",
        domain=[
            If(Eval('from_date') & Eval('to_date'),
                ('to_date', '>=', Eval('from_date')),
                ()),
            ],
        depends=['from_date'],
        required=True,)

    @classmethod
    def default_month(cls):
        Date = Pool().get('ir.date')
        today = Date.today()
        month = today.month
        return month

    @classmethod
    def default_from_date(cls):
        Date = Pool().get('ir.date')
        today = Date.today()
        date = datetime.date(today.year, today.month,1)
        first_day = first_day_month(date)
        return first_day

    @classmethod
    def default_to_date(cls):
        Date = Pool().get('ir.date')
        today = Date.today()
        date = datetime.date(today.year, today.month,1)
        last_day = last_day_month(date)
        return last_day

    @fields.depends('month', 'from_date','to_date')
    def on_change_month(self):
        Date = Pool().get('ir.date')
        today = Date.today()
        month = int(self.month+1)
        date = datetime.date(today.year, month,1)
        self.from_date = first_day_month(date)
        self.to_date =  last_day_month(date)

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

class PrintPaymentReportWizard(Wizard):
    'Print Payment Report Wizard'
    __name__ = 'print.payment.report.wizard'
    
    start = StateView('print.payment.report.start',
        'account_iesa.print_payment_report_start', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('account.iesa.payment.report.print')

    def do_print_(self, action):
        if self.start.party: 
            data = {
                    'from_date': self.start.from_date,
                    'to_date': self.start.to_date,
                    'date': self.start.date,
                    'party':self.start.party.id, 
                    } 
        else: 
            data = {
                    'from_date': self.start.from_date,
                    'to_date': self.start.to_date,
                    'date': self.start.date,
                    } 
        return action, data

class PrintPaymentReport(Report):
    'Print Payment Report Group'
    __name__ = 'account.iesa.payment.report.print'

    @classmethod
    def _get_records(cls, ids, model, data):

        pool = Pool()
        Payment = pool.get('account.iesa.payment')
        Company = pool.get('company.company')
        company = Company(Transaction().context['company'])
        from_date = data['from_date']
        to_date = data['to_date']
        from_date = datetime.date(from_date.year, from_date.month, from_date.day)
        to_date = datetime.date(to_date.year, to_date.month, to_date.day)

        clause = [
            ('invoice_date','>=',from_date),
            ('invoice_date','<=',to_date),
            ('company','=',company),
            ('state','!=','canceled')
        ]
        
        if 'party' in data:
            clause.append(('subscriber','=',data['party']))

        print "CLAUSE: " + str(clause)
        
        return Payment.search(clause,
                order=[
                    ('number', 'ASC'),
                ]
            )

    @classmethod
    def get_context(cls, records, data):
        pool = Pool()
        Payment = pool.get('account.iesa.payment')
        Party = pool.get('party.party')
        Company = pool.get('company.company')
        company = Company(Transaction().context['company'])

        from_date = data['from_date']
        to_date = data['to_date']
        from_date = datetime.date(from_date.year, from_date.month, from_date.day)
        to_date = datetime.date(to_date.year, to_date.month, to_date.day)
        report_context = super(PrintPaymentReport, cls).get_context(records, data)

        clause = [
                ('invoice_date','>=',from_date),
                ('invoice_date','<=',to_date),
                ('company','=',company)
        ]

        if 'party' in data:
            clause.append(('subscriber','=',data['party']))
        
        records = Payment.search(clause,
                order=[('number', 'ASC')])

        payments = Payment.search(clause)

        report_context['company'] = company
        report_context['from_date'] = data['to_date']
        report_context['to_date']  = data['from_date']
        report_context['total'] = sum((x.amount for x in records))

        return report_context
