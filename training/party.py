#! -*- coding: utf8 -*-
# This file is part of the sale_pos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta, date
from decimal import Decimal 
from io import BytesIO
from trytond.model import ModelView, fields, ModelSQL
from trytond.pool import PoolMeta, Pool
from trytond.pyson import If, Eval, Bool, PYSONEncoder, Not
from trytond.transaction import Transaction

__all__ = ['Party']
__metaclass__ = PoolMeta

_ZERO = Decimal('0.0')
#_YEAR = datetime.datetime.now().year

try:
    from PIL import Image
except ImportError:
    Image = None
_states_subscriber = {
            'invisible': ~Eval('is_subscriber'),
            }
_states_student = {
            'invisible': ~Eval('is_student'),
            }

class Party(ModelSQL, ModelView):
    __name__ = 'party.party'

    dob = fields.Date('Date of Birth')
    age = fields.Function(
            fields.Char('Age'),
            'get_age')
    sex = fields.Selection([
        ('F', 'Femenino'),
        ('M', 'Masculino'),
        ], 'Sex',
        states=_states_subscriber)
    scholarship = fields.Char(
        'Scholarship',
        states=_states_subscriber)
    civil_status = fields.Char(
        'Civil Status',
        states=_states_subscriber
    )
    profession = fields.Char(
        'Profession',
        states=_states_subscriber
    )
    is_subscriber= fields.Boolean('Subscriber')
    is_student = fields.Boolean('Student')
    dpi = fields.Char('DPI', 
        states=_states_subscriber)

    photo = fields.Binary('Avatar')

    skype = fields.Function(fields.Char('Skype'), 'get_mechanism')
    sip = fields.Function(fields.Char('SIP'), 'get_mechanism')

    subscriptions = fields.One2Many('sale.subscription','party','Subscriptions')
    subscriptions_student = fields.One2Many('sale.subscription','student','Subscriptions')
    invoices = fields.One2Many('account.invoice','party','Invoices')
    company = fields.Many2One('company.company', 'Company', required=False,
        readonly=False, 
        #invisible=True, 
        #domain=[
        #    ('id', If(Eval('context', {}).contains('company'), '=', '!='),
        #        Eval('context', {}).get('company', -1)),
        #    ]
        ) 
    license = fields.Char('License',
        states=_states_student)

    @classmethod 
    def __setup__(cls): 
        super(Party, cls).__setup__() 
        cls.name.required=True 
    
    def get_age(self, name):
        today = datetime.today().date()
        if self.dob is not None: 

            start = datetime.strptime(str(self.dob), '%Y-%m-%d')
            end = datetime.strptime(str(today),'%Y-%m-%d')

            rdelta = relativedelta(end, start)
            
            years_months_days = str(rdelta.years) + 'a ' \
            + str(rdelta.months) + 'm ' \
            + str(rdelta.days) + 'd'
            return years_months_days

            '''today = date.today()
            edad = today.year - self.nacimiento.year - ((today.month, today.day) < (self.nacimiento.month, self.nacimiento.day))
            return str(edad)'''

    @classmethod
    def convert_photo(cls, data):
        if data and Image:
            image = Image.open(BytesIO(data))
            image.thumbnail((200, 200), Image.ANTIALIAS)
            data = BytesIO()
            image.save(data, image.format)
            data = fields.Binary.cast(data.getvalue())
        return data

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        args = []
        for parties, vals in zip(actions, actions):
            vals = vals.copy()
            person_id = parties[0].id
            # We use this method overwrite to make the fields that have a
            # unique constraint get the NULL value at PostgreSQL level, and not
            # the value '' coming from the client

            if 'photo' in vals:
                vals['photo'] = cls.convert_photo(vals['photo'])

            args.append(parties)
            args.append(vals)
        return super(Party, cls).write(*args)

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('code'):
                values['code'] = cls._new_code()
            if 'photo' in values:
                values['photo'] = cls.convert_photo(values['photo'])
        return super(Party, cls).create(vlist)

    @classmethod
    def default_profession(cls):
        return 'Estudiante'

    @classmethod
    def default_civil_status(cls):
        return 'Soltero'

    @classmethod
    def default_scolarship(cls):
        return 'Ninguna'

    @classmethod
    def default_sex(cls):
        return 'M'

    @classmethod
    def default_customer_payment_term(cls):
        PaymentTerm = Pool().get('account.invoice.payment_term')
        payments = PaymentTerm.search([])
        if payments: 
            return payments[0].id 
        else:
            return None 

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def view_attributes(cls):
        return super(Party, cls).view_attributes() + [
            ('//page[@id="subscription"]', 'states', {
                    'invisible': ~Eval('is_subscriber'),
                    })] + [
            #[
            #('//page[@id="general"]', 'states', {
            #        'invisible': ~Eval('is_subscriber'),
            #        })] + 
                
            ('//page[@id="subscriptions_student"]', 'states', {
                    'invisible': ~Eval('is_student'),
                    })] + [
            ('//page[@id="invoice"]', 'states', {
                    'invisible': ~Eval('is_student'),
                    })] + [
            #[
            #('//page[@id="accounting"]', 'states', {
            #        'invisible': ~Eval('is_student'),
                    #})] + 
                    
            ('//page[@id="notes"]', 'states', {
                    'invisible': ~Eval('is_student'),
                    })]