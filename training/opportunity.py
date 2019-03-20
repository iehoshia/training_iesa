#! -*- coding: utf8 -*-
# This file is part of the sale_pos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

import datetime
from decimal import Decimal 
from trytond.model import ModelView, fields, ModelSQL, \
        Workflow, sequence_ordered
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, In, If, Get, Bool
from datetime import timedelta, date 
from itertools import groupby
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
        Button
from trytond.transaction import Transaction

__all__ = ['SaleOpportunity',
			'SaleOpportunityLine',
			'SaleMeeting',
			]

__metaclass__ = PoolMeta

_STATES_START = {
    'readonly': Eval('state') != 'lead',
    }
_DEPENDS_START = ['state']

_STATES_STOP = {
    'readonly': In(Eval('state'), ['converted', 'won', 'lost', 'cancelled']),
}
_DEPENDS_STOP = ['state']

class SaleOpportunity(Workflow, ModelSQL, ModelView):
    'Sale Opportunity'
    __name__ = "sale.opportunity"

    '''horario = fields.Many2One('training.horario',
    	'Horario', 
    	states={
            'readonly': Eval('state').in_(['converted', 'lost', 'cancelled']),
            'required': ~Eval('state').in_(['lead', 'lost', 'cancelled']),
            }, depends=['state'])'''
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
    	states={
            'readonly': Eval('state').in_(['converted', 'lost', 'cancelled']),
            'required': ~Eval('state').in_(['lead', 'lost', 'cancelled']),
            }, depends=['state'])
    subscriptions = fields.One2Many('sale.subscription', 'origin', 'Suscripciones')

    meetings = fields.One2Many('sale.meeting',
    	'opportunity','Seguimiento',
        states=_STATES_START, 
        depends=_DEPENDS_START
	)

    def _get_sale_opportunity(self):
        '''
        Return subscription for an opportunity
        '''

        pool = Pool()
        Subscription = pool.get('sale.subscription')
        Date = pool.get('ir.date')
        Recurrence = pool.get('sale.subscription.recurrence.rule.set')
        Party = pool.get('party.party')
        recurrences = Recurrence.search([])
        recurrence = recurrences[0].id
        parties = Party.search(['id','=',self.party.id])
        for party in parties:
        		Party.write([party],
        			{'estudiante':True})

        return Subscription(
            description=self.description,
            party=self.party,
            estudiante=self.party, 
            payment_term=self.payment_term,
            company=self.company,
            invoice_address=self.address,
            currency=self.company.currency,
            start_date=Date.today(),
            invoice_recurrence=recurrence,
            #horario = self.horario, 
            asesor = self.employee, 
            medio = self.medio, 
            origin=self,
            )

    def create_sale(self):
        '''
        Create a subscription for the opportunity and return the subscription
        '''
        subscription = self._get_sale_opportunity()
        sale_lines = []
        for line in self.lines:
            sale_lines.append(line.get_sale_line(subscription))
        subscription.lines = sale_lines
        return subscription

    @classmethod
    @ModelView.button
    @Workflow.transition('converted')
    def convert(cls, opportunities):
        pool = Pool()
        Subscription = pool.get('sale.subscription')
        subscriptions = [o.create_sale() for o in opportunities if not o.subscriptions]
        Subscription.save(subscriptions)

    @staticmethod
    def _sale_won_states():
        return ['running','closed']

    @staticmethod
    def _sale_lost_states():
        return ['canceled']

    def is_won(self):
        sale_won_states = self._sale_won_states()
        sale_lost_states = self._sale_lost_states()
        end_states = sale_won_states + sale_lost_states
        return (self.subscriptions
            and all(s.state in end_states for s in self.subscriptions)
            and any(s.state in sale_won_states for s in self.subscriptions))

    def is_lost(self):
        sale_lost_states = self._sale_lost_states()
        return (self.subscriptions
            and all(s.state in sale_lost_states for s in self.subscriptions))

    @classmethod
    def process(cls, opportunities):
        won = []
        lost = []
        converted = []
        for opportunity in opportunities:
            sale_amount = opportunity.sale_amount
            if opportunity.amount != sale_amount:
                opportunity.amount = sale_amount
            if opportunity.is_won():
                won.append(opportunity)
            elif opportunity.is_lost():
                lost.append(opportunity)
            elif (opportunity.state != 'converted'
                    and opportunity.subscriptions):
                converted.append(opportunity)
        cls.save(opportunities)
        if won:
            cls.won(won)
        if lost:
            cls.lost(lost)
        if converted:
            cls.convert(converted)

    @property
    def is_forecast(self):
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        return self.end_date or datetime.date.max > today

    @classmethod
    @Workflow.transition('won')
    def won(cls, opportunities):
        pool = Pool()
        Date = pool.get('ir.date')
        cls.write(filter(lambda o: o.is_forecast, opportunities), {
                'end_date': Date.today(),
                'state': 'won',
                })

    @property
    def sale_amount(self):
    	
        pool = Pool()
        Currency = pool.get('currency.currency')

        if not self.subscriptions:
            #print "NO SUBSCRIPTIONS"
            return

        sale_lost_states = self._sale_lost_states()
        amount = 0
        for subscription in self.subscriptions:
            if subscription.state not in sale_lost_states:
                amount += Currency.compute(subscription.currency, 
                	subscription.amount,
                    self.currency)
        return amount

    @classmethod
    def default_employee(cls):
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

    @fields.depends('party')
    def on_change_party(self):
        self.invoice_address = None
        if self.party:
            self.address = self.party.address_get(type='invoice')
            self.payment_term = self.party.customer_payment_term

class SaleOpportunityLine(sequence_ordered(), ModelSQL, ModelView):
    'Sale Opportunity Line'
    __name__ = "sale.opportunity.line"

    service = fields.Many2One(
        'sale.subscription.service', "Service", required=True,
        )
    
    @fields.depends('service','product','unit','quantity')
    def on_change_service(self):
        if self.service:
            self.product = self.service.product.id 
            self.product = self.service.product.id 
            self.unit = self.service.product.sale_uom.id
            self.quantity = 1	

    def get_sale_line(self, sale):
        '''
        Return sale line for opportunity line
        '''
        SaleLine = Pool().get('sale.subscription.line')
        sale_line = SaleLine(
            subscription=sale,
            quantity=self.quantity,
            unit=self.unit,
            service=self.service,
            )
        sale_line.on_change_service()
        return sale_line

class SaleMeeting(ModelView, ModelSQL):
    'Sale Opportunity Meeting'
    __name__='sale.meeting'

    _order_name = 'hora'

    opportunity = fields.Many2One('sale.opportunity', 'Opportunity',
    )
    fecha = fields.Date('Fecha',
    	required=True)
    hora = fields.Time('Hora',
    	required=True)
    descripcion = fields.Text('Descripcion',
    	required=True)
    asesor = fields.Many2One('company.employee', 'Asesor',
    	domain=[('company', '=', Eval('company'))],
    	required=True,
    	readonly=True)
    medio_contacto = fields.Selection(
    	[
		    ('Llamar', 'Llamar'),
		    ('Correo', 'Enviar correo'),
		    ('Whatsapp', 'Whatsapp'),
		    ('SMS', 'SMS'),
		    ('Visita', 'Visita'),
		    ('Otro', 'Otro'),

		], 'Medio', sort=False,
		required=True, 
    	)
    hora_ = fields.Function(fields.Char('Hora'),
    	'get_hora')
    party = fields.Function(fields.Many2One('party.party','Cliente'),
    	'get_party')
    user = fields.Many2One('res.user','Usuario',
    	readonly=True)

    def get_hora(self, name):
    	hora = self.hora 
    	hour = self.hora.hour
    	minute = self.hora.minute 
    	hora_ = 'Hora ' + str(hour)+':'+str(minute)
    	return hora_ 

    def get_party(self, name):
        if self.opportunity:
            return self.opportunity.party.id 

    @classmethod
    def default_user(cls):
        pool = Pool()
        User = pool.get('res.user')
        cursor = Transaction().connection.cursor()
        user = User(Transaction().user).id
        return user  

    @classmethod
    def default_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

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