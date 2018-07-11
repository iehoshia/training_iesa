#! -*- coding: utf8 -*-
# This file is part of the sale_pos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

import datetime
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta
from trytond.model import ModelView, fields, ModelSQL, \
        Workflow, sequence_ordered
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Bool, Eval, Not, If 
from itertools import groupby
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
        Button, StateReport
from functools import wraps
from trytond.transaction import Transaction
from trytond.report import Report
from decimal import Decimal

from trytond.modules.product import price_digits

_ZERO = Decimal(0)
_YEAR = datetime.datetime.now().year 
_FIRSTDAY = datetime.date(_YEAR,1,1)

__all__ = ['Subscription',
            'SubscriptionContext',
            'Line',
            'LineConsumption',
            'PrintOverdueReportStart',
            'PrintOverdueReport',
            'OverdueReportTable',
            'OverdueReport',
            'PrintGradeOverdueReportStart',
            'PrintGradeOverdueReport',
            'GradeOverdueReportTable',
            'GradeOverdueReport',
            'CreateLineConsumption',
            'CreateSubscriptionInvoice',
            'CreateSubscriptionInvoiceStart']

__metaclass__ = PoolMeta

_DOMAIN = []

def allmonth(year):
    list = []
    for i in range(0,-2,-1):
        d = date(year-i, 1, 1)                    # January 1st
        f = date(year-i, 1, 1)                    # January 1st
        d += timedelta( (5 - d.weekday() + 7) % 7)  # First Sunday
        f += timedelta( f.weekday() + 6)  # First Friday
        while d.year == year-i:
            numero = d.month
            etiqueta = numero_mes(numero-1) + ' - ' +str(d.year)
            list.append( (etiqueta,etiqueta)) 
            d += timedelta(days = 30)
            f += timedelta(days = 30)
    return list 

def numero_mes(numero):
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
    return switcher.get(numero, "ninguno")

def mes_actual(fecha):
    mes = numero_mes(fecha.month-1)
    year = fecha.year
    semana = str(mes) + ' - ' + str(year)
    return semana 

def fecha_inicio_mes(mes):
    digit = ''
    anhio = ''
    for char in mes:
        digit += char 
        if char == ' ':
            anhio = mes.replace(digit,' ')
            anhio = anhio.replace('-',' ')
            break
    mes = mes_numero(digit)
    dias = digit * 7
    anhio = int(anhio)

    actual = datetime.date(anhio, mes, 1)
    return actual

def fecha_fin_mes(mes):
    digit = ''
    anhio = ''
    for char in mes:
        digit += char 
        if char == ' ':
            anhio = mes.replace(digit,' ')
            anhio = anhio.replace('-',' ')
            break
    mes = mes_numero(digit)
    anhio = int(anhio)

    actual = datetime.date(anhio, mes, 1) + relativedelta(day=31)
    return actual

def process_opportunity(func):
    @wraps(func)
    def wrapper(cls, subscriptions):
        pool = Pool()
        Opportunity = pool.get('sale.opportunity')
        with Transaction().set_context(_check_access=False):
            opportunities = [s.origin for s in cls.browse(subscriptions)
                if isinstance(s.origin, Opportunity)]
        func(cls, subscriptions)
        with Transaction().set_context(_check_access=False):
            Opportunity.process(opportunities)
    return wrapper

class SubscriptionContext(ModelView):
    "Subscription Context"
    __name__ = 'sale.subscription.context' 

    student = fields.Many2One('party.party','Student', # student
        domain=['AND', 
                [('is_student', '=', True)],
                [('company', '=', Eval('context', {}).get('company', -1))],
            ],
        )
    subscriber = fields.Many2One('party.party','Subscriber', #suscriptor
        domain=['AND', 
                [('is_subscriber', '=', True)],
                [('company', '=', Eval('context', {}).get('company', -1))],
            ]
        )
    course = fields.Many2One('sale.subscription.service', #course
        'Grade',
        domain=[('company', '=', Eval('context', {}).get('company', -1))],
        )  

class Subscription(ModelSQL, ModelView):
    "Subscription"
    __name__ = 'sale.subscription'

    student = fields.Many2One(
        'party.party', "Student", required=True,
        states={
            'readonly': ((Eval('state') != 'draft') 
                | (Eval('lines', [0]) & Eval('student'))),
            },
        depends=['state','company'],
        domain=['AND', [('is_student', '=', True)],
                [ ('company', '=', Eval('company',-1) )],
            ],
        help="The student who subscribe.")

    origin = fields.Reference('Origin', 
        selection='get_origin', 
        select=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])

    invoices = fields.One2Many('account.invoice', 'subscription_origin', 'Invoices')

    amount = fields.Function(
                fields.Numeric('Total',
                    digits=(16, Eval('currency_digits', 2)),
                ), 'get_amount')

    registration_date = fields.Date('Fecha de inscripcion',
        required=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])

    section = fields.Char('Section',
        required=False,
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])

    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')

    receivable = fields.Function(
        fields.Numeric('Receivable',
            digits=(16, 2), 
            ),
        'get_receivable_payable')

    enrolment = fields.Many2One('product.product','Enrolment',
        domain=['AND', 
            [('is_enrolment', '=', True)],
            [('company', '=', Eval('company', -1) )],
        ],  
        required=True, 
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state','company']
        )

    unit_price_enrolment = fields.Numeric("Enrolment Price", 
        digits=(16,2),
        required=True,  
        states={'readonly': Eval('state') != 'draft',},
        depends=['state'],
        )

    grade = fields.Function(fields.Many2One('sale.subscription.service',
        'Grade'), 'get_grade',searcher='search_grade')

    @classmethod
    def search_grade(cls, name, clause):
        return [('lines.service',) + tuple(clause[1:])]

    @fields.depends('enrolment', 'currency', 'party', 'start_date')
    def on_change_enrolment(self):
        pool = Pool()
        Product = pool.get('product.product')

        if not self.enrolment:
            return

        party = None
        quantity = 1 
        party_context = {}
        if self.party:
            party = self.party
            if party.lang:
                party_context['language'] = party.lang.code

        enrolment = self.enrolment
        category = enrolment.sale_uom.category
        if self.enrolment:
            unit = enrolment.sale_uom
            unit_digits = enrolment.sale_uom.digits

        with Transaction().set_context(self._get_context_sale_price()):
            self.unit_price_enrolment = Product.get_sale_price(
                [enrolment], quantity or 0)[enrolment.id]
            if self.unit_price_enrolment:
                self.unit_price_enrolment = self.unit_price_enrolment.quantize(
                    Decimal(1) / 10 ** self.__class__.unit_price_enrolment.digits[1])

    def _get_context_sale_price(self):
        context = {}
        '''if getattr(self, 'subscription', None):
            if getattr('currency', None):
                context['currency'] = self.currency.id
            if getattr('party', None):
                context['customer'] = self.party.id
            if getattr('start_date', None):
                context['sale_date'] = self.start_date'''
        if self.currency:
            context['currency'] = self.currency.id
        if self.party:
            context['customer'] = self.party.id
        if self.start_date:
            context['sale_date'] = self.start_date

        if self.enrolment:
            context['uom'] = self.enrolment.default_uom.id
        return context

    @classmethod 
    def __setup__(cls): 
        super(Subscription, cls).__setup__() 
        cls.party.depends=['company']
        cls.company.domain=[]
        cls.party.domain=['AND', 
                [('is_subscriber', '=', True)],
                [('company', '=', Eval('company',-1) )],
            ]
        cls.lines.required=True
        cls.end_date.required=True
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'quotation']),
                    'icon': 'tryton-cancel',
                    },
                'draft': {
                    'invisible': Eval('state').in_(['draft', 'closed']),
                    'icon': If(Eval('state') == 'canceled',
                        'tryton-clear', 'tryton-go-previous'),
                    },
                'quote': {
                    'pre_validate':
                        ['OR',
                            ('registration_date', '!=', None),
                            ('enrolment', '!=', None),
                            ('lines', '!=', []),
                        ],
                    'invisible': Eval('state') != 'draft',
                    'icon': 'tryton-go-next',
                    },
                'run': {
                    'invisible': Eval('state') != 'quotation',
                    'icon': 'tryton-go-next',
                    },
                })
        cls._error_messages.update({
                'missing_account_enrolment': (
                    "You need to define an enrolment account."),
                })


    def get_receivable_payable(self, name):
        amount = self.student.receivable
        return amount  
        
    def get_grade(self, name):
        return self.lines[0].service.id if self.lines else None

    def get_amount(self, name):
        amount = Decimal('0.0')
        if self.lines: 
            for line in self.lines: 
                if line.unit_price is not None: 
                    amount += line.unit_price
        return amount 


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

    def _get_invoice(self, invoice_date=None):

        pool = Pool()
        Date = pool.get('ir.date')
        Invoice = pool.get('account.invoice')
        
        address = self.student.address_get(type='invoice')
        if address is None: 
            self._create_party_address(self.student)
        invoice = Invoice(
            company=self.company, 
            type='out', 
            party=self.student,
            invoice_address=self.student.address_get(type='invoice'),
            currency=self.currency,
            invoice_date=invoice_date,
            accounting_date=invoice_date, 
            reference='MAT: '+self.number, 
            description=mes_actual(invoice_date),
            account=self.party.account_receivable,
            subscription_origin=self, 
            )
        invoice.on_change_type()
        invoice.payment_term = self.payment_term
        return invoice

    @classmethod
    def _check_enrolment(cls, party=None, reference=None):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        invoices = Invoice.search([
            ('party','=',party),
            ('reference','=',reference),
            ('is_enrolment','=',True),
            ])
        if invoices:
            return True
        return False 

    def create_enrolment_invoice(self):
        'Create and return an enrolment invoice'
        pool = Pool()
        Invoice = pool.get('account.invoice')
        InvoiceLine = pool.get('account.invoice.line')
        Uom = pool.get('product.uom')
        AccountConfiguration = pool.get('account.configuration')
        account_config = AccountConfiguration(1)

        pool = Pool()
        Invoice = pool.get('account.invoice')

        address = self.student.address_get(type='invoice')
        if address is None: 
            self._create_party_address(self.student)

        invoice = Invoice(
            company=self.company,
            type='out',
            party=self.student,
            invoice_address=self.student.address_get(type='invoice'),
            currency=self.currency,
            reference='MAT: '+str(self.number),
            description='INS - '+ str(self.registration_date.year),
            invoice_date=self.registration_date,
            accounting_date=self.registration_date,
            is_enrolment=True, 
            subscription_origin=self, 
            )
        invoice.on_change_type()
        invoice.payment_term = self.payment_term
        default_enrolment_account = account_config.get_multivalue('default_enrolment_account')
        default_enrolment_revenue = account_config.get_multivalue('default_enrolment_revenue')
        if default_enrolment_account is None: 
            self.raise_user_error('missing_account_enrolment')
        if default_enrolment_revenue is None: 
            self.raise_user_error('missing_account_enrolment')
        
        invoice.account = default_enrolment_account
        invoice.save()
        invoice.update_taxes([invoice])

        line = InvoiceLine()
        line.invoice_type = 'out'
        line.type = 'line'
        line.quantity = 1
        line.unit = self.enrolment.default_uom 
        line.unit_price = self.unit_price_enrolment
        line.product = self.enrolment
        line.description = self.enrolment.name
        line.party = self.student 
        line.account = default_enrolment_revenue
        line.invoice = invoice 

        if not line.account:
            cls.raise_user_error('missing_account_revenue', {
                    'product': enrolment.rec_name,
                    })

        taxes = []
        pattern = line._get_tax_rule_pattern()
        party = invoice.party
        for tax in line.product.customer_taxes_used:
            if party.customer_tax_rule:
                tax_ids = party.customer_tax_rule.apply(tax, pattern)
                if tax_ids:
                    taxes.extend(tax_ids)
                continue
            taxes.append(tax.id)
        if party.customer_tax_rule:
            tax_ids = party.customer_tax_rule.apply(None, pattern)
            if tax_ids:
                taxes.extend(tax_ids)
        line.taxes = taxes
        line.save()

        return invoice

    @classmethod
    def generate_invoice(cls, date=None, party=None, enrolment=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Consumption = pool.get('sale.subscription.line.consumption')
        Invoice = pool.get('account.invoice')
        InvoiceLine = pool.get('account.invoice.line')
        Subscription = pool.get('sale.subscription')
        company =  Transaction().context.get('company')

        if date is None:
            date = Date.today()

        consumptions = Consumption.search([
                ('invoice_line', '=', None),
                ('line.subscription.next_invoice_date', '<=', date),
                ('line.subscription.state', 'in', ['running', 'closed']),
                ('company','=',company)
                ],
            order=[
                ('line.subscription.id', 'DESC'),
                ])

        def keyfunc(consumption):
            return consumption.line.subscription
        invoices = {}
        lines = {}

        if consumptions:
            invoice_date = consumptions[0].date
        for subscription, consumptions in groupby(consumptions, key=keyfunc):
            invoices[subscription] = invoice = subscription._get_invoice(
                invoice_date)
            lines[subscription] = Consumption.get_invoice_lines(
                consumptions, invoice)

        all_invoices = invoices.values()
        
        Invoice.save(all_invoices)

        all_invoice_lines = []
        for subscription, invoice in invoices.iteritems():
            invoice_lines, _ = lines[subscription]
            for line in invoice_lines:
                line.invoice = invoice
            all_invoice_lines.extend(invoice_lines)
        InvoiceLine.save(all_invoice_lines)

        all_consumptions = []
        for values in lines.itervalues():
            for invoice_line, consumptions in zip(*values):
                for consumption in consumptions:
                    assert not consumption.invoice_line
                    consumption.invoice_line = invoice_line
                    all_consumptions.append(consumption)
        Consumption.save(all_consumptions)

        Invoice.update_taxes(all_invoices)

        subscriptions = cls.search([
                ('next_invoice_date', '<=', date),
                ('company','=',company)
                ])

        for subscription in subscriptions:
            if subscription.state == 'running':
                while subscription.next_invoice_date <= date:
                    subscription.next_invoice_date = (
                        subscription.compute_next_invoice_date())
            else:
                subscription.next_invoice_date = None
        for subscription in subscriptions:
            # check invoice enrolment 
            party = subscription.student.id
            subscription_reference = 'MAT: ' + str(subscription.number)
            exist_enrolment = subscription._check_enrolment(party, subscription_reference)

            if not exist_enrolment:
                subscription.create_enrolment_invoice()
        cls.save(subscriptions)

    @classmethod
    @ModelView.button
    @Workflow.transition('running')
    @process_opportunity
    def run(cls, subscriptions):
        pool = Pool()
        Line = pool.get('sale.subscription.line')
        Subscription = pool.get('sale.subscription')
        Party = pool.get('party.party')
        lines = []
        state = 'none'
        party = ''
        enrolment = ''
        for subscription in subscriptions:
            subscription.state = 'running'
            start_date = subscription.start_date
            state = subscription.state
            if not subscription.next_invoice_date: 
                subscription.next_invoice_date = (
                    subscription.compute_next_invoice_date())
            for line in subscription.lines:
                if (line.next_consumption_date is None
                        and not line.consumed):
                    line.next_consumption_date = (
                        line.compute_next_consumption_date())
            lines.extend(subscription.lines)
            party = subscription.party.id
            enrolment = subscription.enrolment
        Line.save(lines) 
        cls.save(subscriptions) 
        Line.generate_consumption(
            date=start_date)
        Subscription.generate_invoice(date=start_date, party=party, enrolment=enrolment)

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return ['sale.subscription','sale.opportunity']

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    @classmethod
    @process_opportunity
    def delete(cls, subscriptions):
        super(Subscription, cls).delete(subscriptions)

    @classmethod
    @process_opportunity
    def cancel(cls, subscriptions):
        super(Subscription, cls).cancel(subscriptions)

    @classmethod
    @process_opportunity
    def draft(cls, subscriptions):
        super(Subscription, cls).draft(subscriptions)

    @classmethod
    @process_opportunity
    def quote(cls, subscriptions):
        super(Subscription, cls).quote(subscriptions)

    @classmethod
    @process_opportunity
    def process(cls, subscriptions):
        super(Subscription, cls).process(subscriptions)

    @classmethod
    def default_invoice_recurrence(cls):
        Recurrence = Pool().get('sale.subscription.recurrence.rule.set')
        recurrences = Recurrence.search([])
        if recurrences:
            return recurrences[0].id 
        return None 

    @classmethod 
    def default_registration_date(cls):
        Date = Pool().get('ir.date')
        date = Date.today()
        return date 

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query=False):
        transaction = Transaction().context 
        
        student = transaction.get('student')
        subscriber = transaction.get('subscriber')
        course = transaction.get('course')
        
        domain = domain[:]
        if student is not None: 
            domain = [domain, ('student','=',student)]
        if subscriber is not None: 
            domain = [domain, ('party','=',subscriber)] 
        if course is not None:  
            domain = [domain, ('lines.service','=',course)] 

        records = super(Subscription, cls).search(domain, offset=offset, limit=limit,
             order=order, count=count, query=query)

        if Transaction().user:
            # Clear the cache as it was not cleaned for confidential 
            cache = Transaction().get_cache()
            cache.pop(cls.__name__, None)
        return records

class LineConsumption(ModelSQL, ModelView):
    "Subscription Line Consumption"
    __name__ = 'sale.subscription.line.consumption'

    company = fields.Many2One(
        'company.company', "Company", required=False, select=True,
        help="Make the subscription belong to the company."
        )

class Line(sequence_ordered(), ModelSQL, ModelView):
    "Subscription Line"
    __name__ = 'sale.subscription.line'

    company = fields.Many2One(
        'company.company', "Company", required=True, select=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        #domain=[
        #    ('id', If(Eval('context', {}).contains('company'), '=', '!='),
        #        Eval('context', {}).get('company', -1)),
        #    ],
        depends=['state'],
        help="Make the subscription line belong to the company.")

    @classmethod 
    def __setup__(cls): 
        super(Line, cls).__setup__() 
        cls.service.depends=['company','subscription_state']
        cls.service.domain=[('company', '=', Eval('company',-1) )]
        cls.unit_price.digits=(16,2)

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def generate_consumption(cls, date=None, party=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Consumption = pool.get('sale.subscription.line.consumption')
        Subscription = pool.get('sale.subscription')
        company = Transaction().context.get('company')

        if date is None:
            date = Date.today()

        if party is not None: 
            remainings = all_lines = cls.search([
                ('consumption_recurrence', '!=', None),
                ('next_consumption_date_delayed', '<=', date),
                ('subscription.state', '=', 'running'),
                ('company','=',company),
                ('subscription.student','=',party)
                ])
        else:
            remainings = all_lines = cls.search([
                ('consumption_recurrence', '!=', None),
                ('next_consumption_date_delayed', '<=', date),
                ('subscription.state', '=', 'running'),
                ( 'company','=',company)
                ])
        consumptions = []
        subscription_ids = set()
        while remainings:
            lines, remainings = remainings, []
            for line in lines:
                consumptions.append(
                    line.get_consumption(line.next_consumption_date))
                line.next_consumption_date = (
                    line.compute_next_consumption_date())
                line.consumed = True
                if line.next_consumption_date is None:
                    subscription_ids.add(line.subscription.id)
                elif line.get_next_consumption_date_delayed() <= date:
                    remainings.append(line)
        Consumption.save(consumptions)
        cls.save(all_lines)
        Subscription.process(Subscription.browse(list(subscription_ids)))

    def get_consumption(self, date):
        pool = Pool()
        Consumption = pool.get('sale.subscription.line.consumption')
        company = Transaction().context.get('company')
        return Consumption(line=self, quantity=self.quantity, date=date,company=company)

    @classmethod
    def generate_consumption_monthly(cls, party=None, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Subscription = pool.get('sale.subscription')
        Line = pool.get('sale.subscription.line')

        if date is None:
            date = Date.today()

        cur_date = _FIRSTDAY

        while cur_date <= date:
            Line.generate_consumption(date=cur_date)
            Subscription.generate_invoice(date=cur_date)
            cur_date += relativedelta(months=1)

    @classmethod
    def generate_consumption_cash(cls, party=None, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Subscription = pool.get('sale.subscription')
        Line = pool.get('sale.subscription.line')

        if date is None:
            date = Date.today()

        cur_date = _FIRSTDAY

        while cur_date <= date:
            Line.generate_consumption(date=cur_date, party=party)
            Subscription.generate_invoice(date=cur_date)
            cur_date += relativedelta(months=1)

    @fields.depends('service', 'quantity', 'unit', 'description',
        'subscription', '_parent_subscription.currency',
        '_parent_subscription.party', '_parent_subscription.start_date')
    def on_change_service(self):
        pool = Pool()
        Product = pool.get('product.product')

        if not self.service:
            self.consumption_recurrence = None
            self.consumption_delay = None
            return

        party = None
        party_context = {}
        if self.subscription and self.subscription.party:
            party = self.subscription.party
            if party.lang:
                party_context['language'] = party.lang.code

        product = self.service.product
        category = product.sale_uom.category
        if not self.unit or self.unit.category != category:
            self.unit = product.sale_uom
            self.unit_digits = product.sale_uom.digits

        with Transaction().set_context(self._get_context_sale_price()):
            self.unit_price = Product.get_sale_price(
                [product], self.quantity or 0)[product.id]
            if self.unit_price:
                self.unit_price = self.unit_price.quantize(
                    Decimal(1) / 10 ** self.__class__.unit_price.digits[1])

        if not self.description:
            with Transaction().set_context(party_context):
                description = Product(product.id).description
                if description is not None: 
                    self.description = Product(product.id).description
                else:
                    self.description = Product(product.id).rec_name

        self.consumption_recurrence = self.service.consumption_recurrence
        self.consumption_delay = self.service.consumption_delay

class CreateSubscriptionInvoiceStart(ModelView):
    "Create Subscription Invoice"
    __name__ = 'sale.subscription.create_invoice.start'

    party = fields.Many2One('party.party','Party', # student
        domain=['AND', 
                [('is_student', '=', True)],
                [('company', '=', Eval('context', {}).get('company', -1))],
            ],
        required=True,     
        ) 

# WIZARD

class CreateLineConsumption(Wizard):
    "Create Subscription Line Consumption"
    __name__ = 'sale.subscription.line.consumption.create'

    def do_create_(self, action):
        pool = Pool()
        Line = pool.get('sale.subscription.line')
        Line.generate_consumption_monthly(date=self.start.date)
        return action, {}

class CreateSubscriptionInvoice(Wizard):
    "Create Subscription Invoice"
    __name__ = 'sale.subscription.create_invoice'

    def transition_create_(self):
        pool = Pool()
        Line = pool.get('sale.subscription.line')
        Line.generate_consumption_cash(date=self.start.date, party=self.start.party)
        return 'end'

# OVERDUE REPORTE

class PrintOverdueReportStart(ModelView):
    'Overdue Report Start'
    __name__ = 'overdue.report.print.start'
    
    date = fields.Date('Current Date', required=True,
        readonly=True)
    #amount = fields.Numeric('Amount', required=True)
    user = fields.Many2One('res.user','User',
        required=True, 
        readonly=True, 
        )

    @staticmethod
    def default_amount():
        return Decimal(0)

    @classmethod
    def default_user(cls):
        pool = Pool()
        User = pool.get('res.user')
        cursor = Transaction().connection.cursor()
        user = User(Transaction().user).id
        return user 

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

class PrintOverdueReport(Wizard):
    'Overdue Report'
    __name__ = 'overdue.report.print'
    
    start = StateView('overdue.report.print.start',
        'training.print_overdue_report_start_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('overdue.report')

    def do_print_(self, action):
        data = {
            #'amount': self.start.amount, 
            'date': self.start.date,
            'user': self.start.user.name,
            }
        return action, data

class OverdueReportTable(ModelSQL, ModelView):
    'Overdue Report Table'
    __name__ = 'overdue.report.table'

    name = fields.Char('Name')

class OverdueReport(Report):
    'Overdue Report'
    __name__ = 'overdue.report'

    @classmethod
    def _get_records(cls, ids, model, data):
        pool = Pool()
        #Party = pool.get('party.party')
        Subscription = pool.get('sale.subscription')

        clause = ''
        clause = clause[:]
        company = Transaction().context.get('company')
        #amount = data['amount']

        clause = [clause,
                    ('company','=',company)
                ]
        
        start_date = date(date.today().year, 1, 1)
        end_date =  date(date.today().year, 12, 31)
        
        clause = [clause,
                    ('start_date','>=',start_date),
                    ('end_date','<=',end_date),
                    ('state','in',['running','closed']),
                ]
        
        #clause = [clause,
        #            ('party.receivable','>=',amount)
        #        ]
        
        #asc order
        #return Subscription.search(clause,
        #        order=[('party.receivable', 'DESC')])
        return Subscription.search(clause)

    @classmethod
    def get_context(cls, records, data):
        report_context = super(OverdueReport, cls).get_context(records, data)

        pool = Pool()
        Subscription = pool.get('sale.subscription')

        clause = ''
        clause = clause[:]
        company = Transaction().context.get('company')
        #amount = data['amount']

        start_date = date(date.today().year, 1, 1)
        end_date =  date(date.today().year, 12, 31)
        
        clause = [clause,
                    ('company','=',company)
                ]
        clause = [clause,
                    ('start_date','>=',start_date),
                    ('end_date','<=',end_date),
                    ('state','in',['running','closed']),
                ]

        subscriptions = Subscription.search(clause)

        report_context['date'] = data['date']
        report_context['user'] = data['user']
        
        report_context['total'] = sum((x.student.receivable for x in subscriptions))
        
        return report_context

# GRADE OVERDUE REPORTE

class PrintGradeOverdueReportStart(ModelView):
    'Grade Overdue Report Start'
    __name__ = 'grade.overdue.report.print.start'
    
    date = fields.Date('Current Date', required=True,
        readonly=True)
    user = fields.Many2One('res.user','User',
        required=True, 
        readonly=True, 
        )
    grade = fields.Many2One('sale.subscription.service', 'Grade',
        required=True,
        domain=[('company', '=', Eval('context', {}).get('company', -1))],
        )

    @classmethod
    def default_user(cls):
        pool = Pool()
        User = pool.get('res.user')
        cursor = Transaction().connection.cursor()
        user = User(Transaction().user).id
        return user 

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @staticmethod
    def default_amount():
        return Decimal(0)

class PrintGradeOverdueReport(Wizard):
    'Grade Overdue Report'
    __name__ = 'grade.overdue.report.print'
    
    start = StateView('grade.overdue.report.print.start',
        'training.print_grade_overdue_report_start_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('grade.overdue.report')

    def do_print_(self, action):
        data = {
            'date': self.start.date,
            'user': self.start.user.name,
            'grade': self.start.grade.id, 
            }
        return action, data

class GradeOverdueReportTable(ModelSQL, ModelView):
    'Grade Overdue Report Table'
    __name__ = 'grade.overdue.report.table'

    name = fields.Char('Name')
    
class GradeOverdueReport(Report):
    'Grade Overdue Report'
    __name__ = 'grade.overdue.report'

    @classmethod
    def _get_records(cls, ids, model, data):
        pool = Pool()

        Subscription = pool.get('sale.subscription')

        clause = ''
        clause = clause[:]
        company = Transaction().context.get('company')
        grade = data['grade']

        start_date = date(date.today().year, 1, 1)
        end_date =  date(date.today().year, 12, 31)

        clause = [clause,
                    ('company','=',company)
                ]
        clause = [clause,
                    ('grade','=',grade)
                ]
        clause = [clause,
                    ('start_date','>=',start_date),
                    ('end_date','<=',end_date),
                    ('state','in',['running','closed']),
                ]
            
        return Subscription.search(clause,
            )

    @classmethod
    def get_context(cls, records, data):
        report_context = super(GradeOverdueReport, cls).get_context(records, data)

        pool = Pool()
        Subscription = pool.get('sale.subscription')
        Grade = pool.get('sale.subscription.service')

        clause = ''
        clause = clause[:]
        company = Transaction().context.get('company')
        #amount = data['amount']
        grade = data['grade']
        grade_name = Grade(grade).product.name

        start_date = date(date.today().year, 1, 1)
        end_date =  date(date.today().year, 12, 31)
        
        clause = [clause,
                    ('company','=',company)
                ]
        clause = [clause,
                    ('start_date','>=',start_date),
                    ('end_date','<=',end_date),
                    ('state','in',['running','closed']),
                ]
        clause = [clause,
                    ('grade','=',grade)
                ]
        
        subscriptions = Subscription.search(clause)

        report_context['date'] = data['date']
        report_context['user'] = data['user']
        report_context['grade'] = grade_name
        report_context['total'] = sum((x.student.receivable for x in subscriptions))
        
        return report_context