# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal
from collections import defaultdict, namedtuple
from itertools import combinations
import base64
import itertools

from sql import Literal, Null
from sql.aggregate import Count, Sum
from sql.conditionals import Coalesce, Case
from sql.functions import Round

from trytond.model import Workflow, ModelView, ModelSQL, fields, Check, \
    sequence_ordered
from trytond.report import Report
from trytond.wizard import Wizard, StateView, StateTransition, StateAction, \
    Button, StateReport
from trytond import backend
from trytond.pyson import If, Eval, Bool
from trytond.tools import reduce_ids, grouped_slice
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.rpc import RPC
from trytond.config import config

from trytond.modules.account.tax import TaxableMixin
from trytond.modules.product import price_digits

from numero_letras import numero_a_moneda

__all__ = [
    'CreateChart',
    'CreateChartProperties',
    'Configuration',
    'ConfigurationDefaultAccount',
    'Invoice',
    'PayInvoice',
    'InvoiceReportReceipt',
    'PayInvoiceStart',
    ] 

__metaclass__ = PoolMeta

class CreateChartProperties:
    __metaclass__ = PoolMeta
    __name__ = 'account.create_chart.properties'

    enrolment_account = fields.Many2One(
        'account.account', 'Default Enrolment Account',
        domain=[
            ('kind', '=', 'receivable'),
            ('company', '=', Eval('company')),
            ],
        depends=['company'])
    enrolment_revenue = fields.Many2One(
        'account.account', 'Default Enrolment Revenue',
        domain=[
            ('kind', '=', 'revenue'),
            ('company', '=', Eval('company')),
            ],
        depends=['company'])

class CreateChart:
    __metaclass__ = PoolMeta
    __name__ = 'account.create_chart'

    def transition_create_properties(self):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        state = super(CreateChart, self).transition_create_properties()

        with Transaction().set_context(company=self.properties.company.id):
            config = Configuration(1)
            for name in ['enrolment_account', 'enrolment_revenue']:
                setattr(config, 'default_%s' % name,
                    getattr(self.properties, name, None))
            config.save()
        return state

class Configuration:
    __name__ = 'account.configuration'
    __metaclass__ = PoolMeta

    default_enrolment_account = fields.MultiValue(fields.Many2One(
            'account.account', 'Default Enrolment Account',
            domain=[
                ('kind', '=', 'receivable'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]))

    default_enrolment_revenue = fields.MultiValue(fields.Many2One(
            'account.account', 'Default Enrolment Revenue',
            domain=[
                ('kind', '=', 'revenue'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {
                'default_product_account_expense',
                'default_product_account_revenue',
                'default_category_account_expense',
                'default_category_account_revenue',
                'default_enrolment_account',
                'default_enrolment_revenue',
                }:
            return pool.get('account.configuration.default_account')
        return super(Configuration, cls).multivalue_model(field)

class ConfigurationDefaultAccount:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration.default_account'

    default_enrolment_account = fields.Many2One(
        'account.account', "Default Enrolment Account",
        domain=[
            ('kind', '=', 'receivable'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    default_enrolment_revenue = fields.Many2One(
        'account.account', "Default Enrolment Revenue",
        domain=[
            ('kind', '=', 'revenue'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])

class Invoice(ModelSQL,ModelView):
    'Account Invoice'
    __name__ = 'account.invoice' 

    is_enrolment = fields.Boolean('Enrolment')
    subscription_origin = fields.Reference('Origin', 
        selection='get_subscription_origin', 
        select=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])

    def _pay_invoice_wizard(self, amount_to_pay):
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
            print "PAY: " + str(pay_wizard)

    def update_invoice_status(self):
        receivable = self.party.receivable
        state = 'posted'
        if receivable >= 0:
            state = 'posted'
        else: 
            receivable =-receivable
            current_amount = self.total_amount
            print "RECEIVABLE TRAINING: " + str(receivable)
            print "RECEIVABLE TRAINING: " + str(current_amount)
            if current_amount <= receivable: 
                state = 'paid'
        print "STATE: " + str(state)
        return state 

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, invoices):
        Move = Pool().get('account.move')

        cls.set_number(invoices)
        moves = []
        for invoice in invoices:
            move = invoice.get_move()
            if move != invoice.move:
                invoice.move = move
                moves.append(move)
            if invoice.state != 'posted':
                invoice.state = 'posted'
                #invoice.state = invoice.update_invoice_status()
        if moves:
            Move.save(moves)
        cls.save(invoices)
        Move.post([i.move for i in invoices if i.move.state != 'posted'])
        for invoice in invoices:
            if invoice.type == 'out':
                invoice.print_invoice()
                
                #invoice.save()

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
            print "PAY: " + str(pay_wizard) 

    def pay_invoice(self, amount, journal, date, description,
            amount_second_currency=None, second_currency=None,
            ticket=None, third_party=None, receipt=None):
        '''
        Adds a payment of amount to an invoice using the journal, date and
        description.
        Returns the payment line.
        '''

        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')

        line1 = Line(description=description, account=self.account, ticket=ticket, third_party=third_party, receipt=receipt)
        line2 = Line(description=description, ticket=ticket, third_party=third_party, receipt=receipt)
        lines = [line1, line2]

        if amount >= 0:
            if self.type == 'out':
                line1.debit, line1.credit = 0, amount
            else:
                line1.debit, line1.credit = amount, 0
        else:
            if self.type == 'out':
                line1.debit, line1.credit = -amount, 0
            else:
                line1.debit, line1.credit = 0, -amount

        line2.debit, line2.credit = line1.credit, line1.debit
        if line2.debit:
            account_journal = 'debit_account'
        else:
            account_journal = 'credit_account'
        line2.account = getattr(journal, account_journal)
        if self.account == line2.account:
            self.raise_user_error('same_%s' % account_journal, {
                    'journal': journal.rec_name,
                    'invoice': self.rec_name,
                    })
        if not line2.account:
            self.raise_user_error('missing_%s' % account_journal,
                (journal.rec_name,))

        #print "LINE1: " + str(line1.account) + " LINE2: " + str(line2.account)

        for line in lines:
            if line.account.party_required:
                line.party = self.party
            if amount_second_currency:
                line.amount_second_currency = amount_second_currency.copy_sign(
                    line.debit - line.credit)
                line.second_currency = second_currency

        #print "LINES: " + str(lines)

        period_id = Period.find(self.company.id, date=date)

        move = Move(journal=journal, period=period_id, date=date,
            company=self.company, lines=lines, origin=self)
        move.save()
        Move.post([move])

        for line in move.lines:
            if line.account == self.account:
                self.add_payment_lines({self: [line]})
                return line
        raise Exception('Missing account')

    @classmethod
    def _get_subscription_origin(cls):
        'Return list of Model names for origin Reference'
        return ['sale.subscription','sale.opportunity']

    @classmethod
    def get_subscription_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_subscription_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    @classmethod 
    def __setup__(cls): 
        super(Invoice, cls).__setup__() 
        cls.party.domain=[('company', '=', Eval('context', {}).get('company', -1))]
        cls._error_messages.update({
                'missing_account_payable': ('Missing account payable.'),
                'missing_account_receivable': ('Missing account receivable.'),
                })
        cls._buttons.update({
                'cancel': {
                    'invisible': (~Eval('state').in_(['draft', 'validated'])
                        & ~((Eval('state') == 'posted')
                            & (Eval('type') == 'in'))),
                    'help': 'Cancel the invoice',
                    'depends': ['state', 'type'],
                    },
                'draft': {
                    'invisible': (~Eval('state').in_(['cancel', 'validated'])
                        | ((Eval('state') == 'cancel')
                            & Eval('cancel_move', -1))),
                    'icon': If(Eval('state') == 'cancel', 'tryton-clear',
                        'tryton-go-previous'),
                    'depends': ['state'],
                    },
                'validate_invoice': {
                    'pre_validate':
                        ['OR',
                            ('invoice_date', '!=', None),
                            ('type', '!=', 'in'),
                        ],
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'post': {
                    'pre_validate':
                        ['OR',
                            ('invoice_date', '!=', None),
                            ('type', '!=', 'in'),
                        ],
                    'invisible': Eval('state') == 'posted',
                    'depends': ['state'],
                    },
                'pay': {
                    'invisible': Eval('state') != 'posted',
                    'depends': ['state'],
                    },
                })

    def _create_party_address(self, party): 
        pool = Pool()
        Party = pool.get('party.party')
        PartyAddress = pool.get('party.address')

        address = PartyAddress(party=party, 
                city="Guatemala")
        address.save()
        print "PARTY ID: " + str(address.id) +"ADDRESS:  " + str(address.city) + "PARTY: " + str(address.party)
        print "PARTY ADDRESSES:  " + str(party.addresses)
        return address

    def __get_account_payment_term(self):
        '''
        Return default account and payment term
        '''
        pool = Pool()
        AccountConfiguration = pool.get('account.configuration')
        account_config = AccountConfiguration(1)
        default_account_receivable = account_config.get_multivalue('default_account_receivable')
        default_account_payable = account_config.get_multivalue('default_account_payable')
        if default_account_receivable is None: 
            self.raise_user_error('missing_account_receivable')
        if default_account_payable is None: 
            self.raise_user_error('missing_account_payable')

        self.account = None
        if self.party:
            if self.type == 'out':
                if self.party.account_receivable is not None: 
                    self.account = self.party.account_receivable
                else:
                    self.account = default_account_receivable.id
                if self.party.customer_payment_term:
                    self.payment_term = self.party.customer_payment_term
            elif self.type == 'in':
                if self.party.account_payable is not None:
                    self.account = self.party.account_payable
                else:
                    self.account = default_account_payable.id
                if self.party.supplier_payment_term:
                    self.payment_term = self.party.supplier_payment_term

    @fields.depends('party', 'payment_term', 'type', 'company')
    def on_change_party(self):
        self.invoice_address = None
        self.__get_account_payment_term()

        if self.party:
            self.invoice_address = self.party.address_get(type='invoice')
            self.party_tax_identifier = self.party.tax_identifier

class MoveLine(ModelSQL, ModelView):
    'Account Move Line'
    __name__ = 'account.move.line'

    _states = {
        'readonly': Eval('move_state') == 'posted',
        }
    _depends = ['move_state']

    ticket = fields.Char('Ticket', states=_states, depends=_depends)
    third_party = fields.Char('Third Party', states=_states, depends=_depends)
    receipt = fields.Char('Receipt', states=_states, depends=_depends)

    @classmethod 
    def __setup__(cls): 
        super(MoveLine, cls).__setup__() 
        cls._order[0] = ('id', 'DESC')

class PayInvoiceStart(ModelView):
    'Pay Invoice'
    __name__ = 'account.invoice.pay.start'

    is_ticket = fields.Boolean('Bank Deposit')
    third_party = fields.Char('Party', 
        required=True)
    ticket = fields.Char('Ticket', 
        states={
                'required': Eval('is_ticket', True),
                'invisible': ~Eval('is_ticket', True),
                },)
    receipt = fields.Char('Receipt', required=True,
        select=True)

    @classmethod
    def default_is_ticket(cls):
        return True 

class PayInvoice(Wizard):
    'Pay Invoice'
    __name__ = 'account.invoice.pay'

    start = StateView('account.invoice.pay.start',
        'account_invoice.pay_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'choice', 'tryton-ok', default=True),
            ])
    choice = StateTransition()
    ask = StateView('account.invoice.pay.ask',
        'account_invoice.pay_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'pay', 'tryton-ok', default=True),
            ])
    pay = StateTransition()
    print_ = StateReport('account.invoice.receipt')

    def transition_choice(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Currency = pool.get('currency.currency')
        transaction = Transaction().context 
        current_invoice = transaction.get('current_invoice')
        if current_invoice is not None:
            invoice = Invoice(current_invoice)
        else: 
            invoice = Invoice(Transaction().context['active_id'])
        print "INVOICE CHOICE: " + str(invoice)

        with Transaction().set_context(date=self.start.date):
            amount = Currency.compute(self.start.currency,
                self.start.amount, invoice.company.currency)
            amount_invoice = Currency.compute(
                self.start.currency, self.start.amount, invoice.currency)
        _, remainder = self.get_reconcile_lines_for_amount(invoice, amount)
        if (remainder == Decimal('0.0')
                and amount_invoice <= invoice.amount_to_pay):
            return 'pay'
        return 'ask'

    def transition_pay(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Currency = pool.get('currency.currency')
        MoveLine = pool.get('account.move.line')

        transaction = Transaction().context 
        current_invoice = transaction.get('current_invoice')
        if current_invoice is not None:
            invoice = Invoice(current_invoice)
        else: 
            invoice = Invoice(Transaction().context['active_id'])

        with Transaction().set_context(date=self.start.date):
            amount = Currency.compute(self.start.currency,
                self.start.amount, invoice.company.currency)

        reconcile_lines, remainder = \
            self.get_reconcile_lines_for_amount(invoice, amount)

        amount_second_currency = None
        second_currency = None
        if self.start.currency != invoice.company.currency:
            amount_second_currency = self.start.amount
            second_currency = self.start.currency

        if (abs(amount) > abs(invoice.amount_to_pay)
                and self.ask.type != 'writeoff'):
            self.raise_user_error('amount_greater_amount_to_pay',
                (invoice.rec_name,))

        line = None
        print "JOURNAL: " + str(self.start.journal)
        if not invoice.company.currency.is_zero(amount):
            line = invoice.pay_invoice(amount,
                self.start.journal, 
                self.start.date,
                self.start.description, 
                amount_second_currency,
                second_currency, 
                self.start.ticket or None, 
                self.start.third_party or None,
                self.start.receipt or None)
        print "LINE: " + str(line)

        if remainder != Decimal('0.0'):
            if self.ask.type == 'writeoff':
                lines = [l for l in self.ask.lines] + \
                    [l for l in invoice.payment_lines
                        if not l.reconciliation]
                if line and line not in lines:
                    # Add new payment line if payment_lines was cached before
                    # its creation
                    lines += [line]
                if lines:
                    MoveLine.reconcile(lines,
                        journal=self.ask.journal_writeoff,
                        date=self.start.date)
        else:
            if line:
                reconcile_lines += [line]
            if reconcile_lines:
                MoveLine.reconcile(reconcile_lines)

        return 'print_' 


    def do_print_(self, action=None):
        
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Party = pool.get('party.party')
        Line = pool.get('account.invoice.line')
        Lang = pool.get('ir.lang')
        Currency = pool.get('currency.currency')

        default = {}

        transaction = Transaction().context 
        current_invoice = transaction.get('current_invoice')
        if current_invoice is not None:
            invoice = Invoice(current_invoice)
        else: 
            invoice = Invoice(Transaction().context['active_id'])
        party = Party(invoice.party)
        line = Line(invoice.lines[0].id)
        if len(invoice.lines)>1:
            line2 = Line(invoice.lines[1].id).product.name
        else: 
            line2 = ''

        lang = Lang(party.lang)
        currency = Currency(invoice.currency)
        
        data = {
        	'amount':self.start.amount, 
            'date':self.start.date,
            'journal': self.start.journal.name,
            'description':self.start.description,
            'is_ticket':self.start.is_ticket, 
            'ticket':self.start.ticket, 
            'third_party':self.start.third_party, 
            'party':party.name, 
            'number': invoice.number,
            'product':line.product.name, 
            'product2':line2,
            'month':invoice.description, 
            }

        return action, data

class InvoiceReportReceipt(Report):
    'Invoice Report Receipt'
    __name__ = 'account.invoice.receipt'

    @classmethod
    def _get_records(cls, ids, model, data):
        return None 

    @classmethod
    def get_context(cls, records, data):

        report_context = super(InvoiceReportReceipt, cls).get_context(records, data)

        amount = data['amount']
        amount_on_letters = numero_a_moneda(amount)

        report_context['amount'] = data['amount'] 
        report_context['party'] = data['party'] 
        report_context['date'] = data['date'] 
        report_context['number'] = data['number'] 
        report_context['journal'] = data['journal'] 
        report_context['is_ticket'] = data['is_ticket']
        report_context['ticket'] = data['ticket']
        report_context['third_party'] = data['third_party']
        report_context['description'] = data['description'] 
        report_context['product'] = data['product'] 
        report_context['product2'] = data['product2'] 
        report_context['month'] = data['month'] 
        report_context['amount_on_letters'] = amount_on_letters
        
        return report_context
