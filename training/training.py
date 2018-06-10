#! -*- coding: utf8 -*-
# This file is part of the sale_pos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

import datetime
from decimal import Decimal 
from trytond.model import ModelView, fields, ModelSQL, \
        Workflow, sequence_ordered
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Bool, Eval, Not, If 
from datetime import timedelta, date 
from itertools import groupby
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
        Button
from functools import wraps
from trytond.transaction import Transaction

_ZERO = Decimal(0)

__all__ = ['Subscription',
            'SubscriptionContext',
            'Horario', 
            'Line']

__metaclass__ = PoolMeta

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

    #horario = fields.Many2One('training.horario','Horario') # schedule
    student = fields.Many2One('party.party','Estudiante', # student
        domain=[('estudiante', '=', True)])
    subscriptor = fields.Many2One('party.party','Suscriptor', #suscriptor
        domain=[('suscriptor', '=', True)])
    course = fields.Many2One('sale.subscription.service', #course
        'Curso') 

class Subscription(ModelSQL, ModelView):

    "Subscription"
    __name__ = 'sale.subscription'


    estudiante = fields.Many2One(
        'party.party', "Estudiante", required=True,
        states={
            'readonly': ((Eval('state') != 'draft') 
                | (Eval('lines', [0]) & Eval('estudiante'))),
            },
        depends=['state'],
        domain=['AND', [('estudiante', '=', True)],
                [('company', '=', Eval('context', {}).get('company', -1))],
            ],
        help="El estudiante que se suscribe.")

    medio = fields.Selection(
        [
            ('Facebook', 'Facebook'),
            ('Google', 'Google'),
            ('Volante', 'Volante'),
            ('Stand', 'Stand'),
            ('Manta', 'Manta'),
            ('Muppy', 'Muppy'),
            ('Otro', 'Otro'),

        ], 'Medio', sort=False,
        required=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state']) 
    horario = fields.Many2One('training.horario',
        'Horario', required=False,
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    asesor = fields.Many2One('company.employee', 'Asesor',
        help="Asesor educativo.", required=False,
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])

    origin = fields.Reference('Origin', 
        selection='get_origin', 
        select=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])

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

    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')

    receivable = fields.Function(
        fields.Numeric('Por cobrar',
            digits=(16, 2), 
            ),
        'get_receivable_payable') 

    @classmethod 
    def __setup__(cls): 
        super(Subscription, cls).__setup__() 
        cls.party.domain=['AND', 
                [('estudiante', '=', True)],
                [('company', '=', Eval('context', {}).get('company', -1))],
            ]


    def get_receivable_payable(self, name):
        amount = self.party.receivable
        return amount  
        '''Party = Pool().get('party.party')
        for subscription in subscriptions:
            if subscription.party:
                party = Party(subscription.party)
                print int(party)
                #amount = int(party.receivable.value)
                amount = 0 
                result = {
                    'receivable': amount,
                }
                for key in result.keys():
                    if key not in names:
                        del result[key]
                return result
            else: 
                amount = 0 
                result = {
                    'receivable': amount,
                }
                return result '''

    @classmethod
    def get_amount(cls, subscriptions, names):
        amount = {}
        for subscription in subscriptions:
            amount[subscription.id] = sum(
                    (line.unit_price for line in subscription.lines), _ZERO)

        result = {
            'amount': amount,
            }
        for key in result.keys():
            if key not in names:
                del result[key]
        return result

    def _get_invoice(self, invoice_date=None):
        print "PASS get_invoice: " 
        pool = Pool()
        Date = pool.get('ir.date')
        Invoice = pool.get('account.invoice')
        invoice = Invoice(
            company=self.company, 
            type='out', 
            party=self.party,
            invoice_address=self.invoice_address,
            currency=self.currency,
            invoice_date=invoice_date,
            reference='SU: '+self.number, 
            description=mes_actual(invoice_date),
            account=self.party.account_receivable,
            )
        invoice.on_change_type()
        invoice.payment_term = self.payment_term
        return invoice

    @classmethod
    def generate_invoice(cls, date=None):
        print "PASS invoices: " + str(date)
        pool = Pool()
        Date = pool.get('ir.date')
        Consumption = pool.get('sale.subscription.line.consumption')
        Invoice = pool.get('account.invoice')
        InvoiceLine = pool.get('account.invoice.line')

        if date is None:
            date = Date.today()

        consumptions = Consumption.search([
                ('invoice_line', '=', None),
                ('line.subscription.next_invoice_date', '<=', date),
                ('line.subscription.state', 'in', ['running', 'closed']),
                ],
            order=[
                ('line.subscription.id', 'DESC'),
                ])
        print "PASS Consumptions: " + str(consumptions)

        def keyfunc(consumption):
            return consumption.line.subscription
        invoices = {}
        lines = {}
        #print "PASS consumptions detail: " + str(consumptions)
        if consumptions:
            invoice_date = consumptions[0].date
        for subscription, consumptions in groupby(consumptions, key=keyfunc):
            invoices[subscription] = invoice = subscription._get_invoice(
                invoice_date)
            lines[subscription] = Consumption.get_invoice_lines(
                consumptions, invoice)

        all_invoices = invoices.values()
        print "PASS invoices: " + str(all_invoices)
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
                ])
        for subscription in subscriptions:
            if subscription.state == 'running':
                while subscription.next_invoice_date <= date:
                    subscription.next_invoice_date = (
                        subscription.compute_next_invoice_date())
            else:
                subscription.next_invoice_date = None
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
        for subscription in subscriptions:
            subscription.state = 'running'
            start_date = subscription.start_date
            state = subscription.state
            parties = Party.search(['id','=',subscription.party.id])
            for party in parties:
                Party.write([party],
                    {'suscriptor':True})
            if not subscription.next_invoice_date: 
                subscription.next_invoice_date = (
                    subscription.compute_next_invoice_date())
            for line in subscription.lines:
                if (line.next_consumption_date is None
                        and not line.consumed):
                    line.next_consumption_date = (
                        line.compute_next_consumption_date())
            lines.extend(subscription.lines)
        Line.save(lines) 
        cls.save(subscriptions) 
        print (subscriptions)
        print('STATE: ' + str(state))
        Line.generate_consumption(
            date=start_date)
        Subscription.generate_invoice(
            date=start_date)

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

    @fields.depends('estudiante','party')
    def on_change_estudiante(self):
        if self.estudiante:
            self.party = self.estudiante
            self.invoice_address = self.estudiante.address_get(type='invoice')
            self.payment_term = self.estudiante.customer_payment_term
        else: 
            self.party = None 
            self.invoice_address= None 
            self.payment_term = None 
            self.invoice_recurrence = None 

    @classmethod
    def default_invoice_recurrence(cls):
        Recurrence = Pool().get('sale.subscription.recurrence.rule.set')
        recurrences = Recurrence.search([])
        if recurrences:
            return recurrences[0].id 
        return None 

    @classmethod
    def default_asesor(cls):
        User = Pool().get('res.user')
        employee_id = None
        if Transaction().context.get('employee'):
            employee_id = Transaction().context['employee']
        else:
            user = User(Transaction().user)
            if user.employee:
                employee_id = user.employee.id
        if employee_id:
            return employee_id

    @classmethod 
    def default_registration_date(cls):
        Date = Pool().get('ir.date')
        date = Date.today()
        return date 

    @classmethod 
    def default_medio(cls):
        return 'Facebook'

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query=False):
        #pool = Pool() 
        #Subscription = pool.get('sale.subscription')
        transaction = Transaction().context 
        horario = transaction.get('horario')
        estudiante = transaction.get('estudiante')
        suscriptor = transaction.get('suscriptor')
        course = transaction.get('course')
        
        domain = domain[:]
        #if horario is not None: 
        #    domain = [domain, ('horario','=',horario)]
        if estudiante is not None: 
            domain = [domain, ('estudiante','=',estudiante)]
        if suscriptor is not None: 
            domain = [domain, ('party','=',suscriptor)]
        if course is not None: 
            domain = [domain, ('lines.service','=',course)]

        records = super(Subscription, cls).search(domain, offset=offset, limit=limit,
             order=order, count=count, query=query)

        if Transaction().user:
            # Clear the cache as it was not cleaned for confidential
            cache = Transaction().get_cache()
            cache.pop(cls.__name__, None)
        return records

class Line(sequence_ordered(), ModelSQL, ModelView):

    "Subscription Line"
    __name__ = 'sale.subscription.line'

    company = fields.Many2One(
        'company.company', "Company", required=True, select=True,
        states={
            'readonly': Eval('state') != 'draft',
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=['state'],
        help="Make the subscription line belong to the company.")

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def generate_consumption(cls, date=None):
        print "PASS consumptions: " + str(date)
        pool = Pool()
        Date = pool.get('ir.date')
        Consumption = pool.get('sale.subscription.line.consumption')
        Subscription = pool.get('sale.subscription')
        context = Transaction().context
        company = context['company']

        if date is None:
            date = Date.today()

        remainings = all_lines = cls.search([
                ('consumption_recurrence', '!=', None),
                ('next_consumption_date_delayed', '<=', date),
                ('subscription.state', '=', 'running'),
                ( 'company','=',company)
                ])
        print "PASS Remainings: "+ str(remainings)

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
        print "PASS consumptions list: " + str(consumptions)
        Consumption.save(consumptions)
        cls.save(all_lines)
        Subscription.process(Subscription.browse(list(subscription_ids)))

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

class Horario(ModelSQL, ModelView):
    "Horario"
    __name__ = 'training.horario'

    name = fields.Char('Horario')
    domingo = fields.Boolean('Domingo')
    lunes = fields.Boolean('Lunes')
    martes = fields.Boolean('Martes')
    miercoles = fields.Boolean('Miercoles')
    jueves = fields.Boolean('Jueves')
    viernes = fields.Boolean('Viernes')

    hora_inicio = fields.Time('Hora de Inicio', 
        required=True)
    hora_fin = fields.Time('Hora de Finalizacion',
        required=True)

    @fields.depends('hora_inicio','hora_fin',
        'domingo','lunes','martes','miercoles','jueves',
        'viernes')
    def on_change_domingo(self):
        name = self.on_change_dia()
        self.name = name

    @fields.depends('hora_inicio','hora_fin',
        'domingo','lunes','martes','miercoles','jueves',
        'viernes')
    def on_change_lunes(self):
        name = self.on_change_dia()
        self.name = name 

    @fields.depends('hora_inicio','hora_fin',
        'domingo','lunes','martes','miercoles','jueves',
        'viernes')
    def on_change_martes(self):
        name = self.on_change_dia()
        self.name = name

    @fields.depends('hora_inicio','hora_fin',
        'domingo','lunes','martes','miercoles','jueves',
        'viernes')
    def on_change_miercoles(self):
        name = self.on_change_dia()
        self.name = name

    @fields.depends('hora_inicio','hora_fin',
        'domingo','lunes','martes','miercoles','jueves',
        'viernes')
    def on_change_jueves(self):
        name = self.on_change_dia()
        self.name = name 

    @fields.depends('hora_inicio','hora_fin',
        'domingo','lunes','martes','miercoles','jueves',
        'viernes')
    def on_change_viernes(self):
        name = self.on_change_dia()
        self.name = name 

    @fields.depends('hora_inicio','hora_fin',
        'domingo','lunes','martes','miercoles','jueves',
        'viernes')
    def on_change_hora_inicio(self):
        name = self.on_change_dia()
        self.name = name

    @fields.depends('hora_inicio','hora_fin',
        'domingo','lunes','martes','miercoles','jueves',
        'viernes')
    def on_change_hora_fin(self):
        name = self.on_change_dia()
        self.name = name  

    def on_change_dia(self):
        name = ' '
        if self.domingo: name += 'Domingo / '
        if self.lunes: name += 'Lunes / '
        if self.martes: name += 'Martes / '
        if self.miercoles: name += 'Miercoles / '
        if self.jueves: name += 'Jueves / '
        if self.viernes: name += 'Viernes / ' 
        hora_inicio = ''
        hora_fin = ''
        if self.hora_inicio:
            hora_inicio = self.hora_inicio.strftime("%H:%M")
        if self.hora_fin:
            hora_fin = self.hora_fin.strftime("%H:%M") 
        name = name + hora_inicio + ' - ' + hora_fin
        return name 

    def get_rec_name(self, name):
        if self.name:
            return self.name
        else:
            return ''

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, value = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        domain = [bool_op,
            ('name', operator, value),
            ('name', operator, value),
            ]
        return domain

    @classmethod
    def __setup__(cls):
        super(Horario, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC')) 