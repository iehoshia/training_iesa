#! -*- coding: utf8 -*-
# This file is part of the sale_pos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

import datetime
from datetime import timedelta, date  
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from trytond.model import ModelStorage, ModelView, fields, ModelSQL, Unique
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Bool, Eval, Not, Id, PYSONEncoder, If, In, Get
from datetime import timedelta, date 
from trytond.transaction import Transaction
from trytond.report import Report
from trytond.wizard import Wizard, StateTransition, StateView, StateAction, \
    StateReport, Button
from sql import Literal
from sql.aggregate import Max, Sum

def dummy(number=None):
    if number is not None: 
        return number 
    else 
        return 0 

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

def mes_numero(mes):
    mes = mes.replace(' ','')
    switcher = {
        "Enero":1,
        "Febrero":2,
        "Marzo":3,
        "Abril":4,
        "Mayo":5,
        "Junio":6,
        "Julio":7,
        "Agosto":8,
        "Septiembre":9,
        "Octubre":10,
        "Noviembre":11,
        "Diciembre":12,
    }
    return switcher.get(mes, 0)

def fecha_inicio_mes(mes):
    digit = ''
    anhio = ''
    for char in mes:
        digit += char 
        if char == ' ':
            anhio = mes.replace(digit,' ')
            anhio = anhio.replace('-',' ')
            break
    #print digit
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
    #print digit
    mes = mes_numero(digit)
    anhio = int(anhio)

    actual = datetime.date(anhio, mes, 1) + relativedelta(day=31)
    return actual

def semanas(year):
    list = []
    for i in range(0,-2,-1):
        #print str(i)
        d = date(year-i, 1, 1)                    # January 1st
        f = date(year-i, 1, 1)                    # January 1st
        d += timedelta( (5 - d.weekday() + 7) % 7)  # First Sunday
        f += timedelta( f.weekday() + 6)  # First Friday
        while d.year == year-i:
            s = d.isocalendar()[1]            
            semana = str(s) + ' - ' +str(year-i)
            etiqueta = 'Semana # '+str(s) + ' - '+ str(year - i) #+ ' del '+ unicode(d)+' al ' +unicode(f)
            list.append( (semana, etiqueta ) ) 
            d += timedelta(days = 7)
            f += timedelta(days = 7)
    return list

def allmonth(year):
    list = []
    for i in range(0,-2,-1):
        #print str(i)
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

def semana_actual(date):
    """This code was provided in the previous answer! It's not mine!"""
    s = date.isocalendar()[1]
    year = date.year
    semana = str(s) + ' - ' + str(year)
    return semana 

def mes_actual(fecha):
    """This code was provided in the previous answer! It's not mine!"""
    mes = numero_mes(fecha.month-1)
    year = fecha.year
    semana = str(mes) + ' - ' + str(year)
    return semana 

def semana(semana):
    digit = ''
    for char in semana:
        digit += char
        if char == ' ':
            break 
    return digit         

def fecha_inicio_semana(semana):
    #print semana
    digit = ''
    for char in semana:
        digit += char 
        if char == ' ':
            #print digit
            anhio = semana.replace(digit,' ')
            anhio = anhio.replace('-',' ')
            #print 'ANHIO: ' + anhio
            break
    digit = int(digit)
    dias = digit * 7
    anhio = int(anhio)

    actual = datetime.date(anhio, 1, 1) + timedelta(dias - 7)
    return actual

def fecha_fin_semana(semana):
    #print semana
    digit = ''
    for char in semana:
        digit += char 
        if char == ' ':
            #print digit
            anhio = semana.replace(digit,' ')
            anhio = anhio.replace('-',' ')
            #print 'ANHIO: ' + anhio
            break
    digit = int(digit)
    dias = digit * 7
    anhio = int(anhio)

    actual = datetime.date(anhio, 1, 1) + timedelta(dias - 1)
    return actual

def mes(semana): 
    digit = ''
    for char in semana:
        digit += char 
        if char == ' ':
            #print digit
            anhio = semana.replace(digit,' ')
            anhio = anhio.replace('-',' ')
            #print 'ANHIO: ' + anhio
            break
    digit = int(digit)
    dias = digit * 7
    anhio = int(anhio)
    dias = digit * 7
    actual = datetime.date(anhio, 1, 1) + timedelta(dias -1 )
    
    numero = actual.month
    mes = numero_mes(numero-1)
    anhio = str(anhio)
    return mes + ' - ' + anhio

__all__ = [
    'Reporte',
    'InformeIglesia',
    'InformeIglesiaContexto',
    'InformeDistrito',
    'InformeDistritoContexto', 
    'InformeZona',
    'InformeZonaContexto',
    'InformeCampo',
    'InformeCampoContexto',
    'InformeUnion',
    'InformeUnionContexto',
    'ImprimirReporteIglesiaInicio',
    'ImprimirReporteIglesia',
    'ReporteIglesia',
    'ReporteIglesiaTable',
    'ImprimirReporteDistritoInicio',
    'ImprimirReporteDistrito',
    'ReporteDistrito',
    'ReporteDistritoTable',
    'ImprimirReporteZonaInicio',
    'ImprimirReporteZona',
    'ReporteZona',
    'ReporteZonaTable',
    'ImprimirReporteCampoInicio',
    'ImprimirReporteCampo',
    'ReporteCampo',
    'ReporteCampoTable',
    'ImprimirReporteUnionInicio',
    'ImprimirReporteUnion',
    'ReporteUnion',
    'ReporteUnionTable',
    ]

__metaclass__ = PoolMeta

_YEAR = datetime.datetime.now().year
_NOW = datetime.datetime.now()
_DOMAIN = []

class Reporte(ModelView, ModelSQL):
    'Reporte'
    __name__ = 'disc.reporte'

    pastor = fields.Many2One('res.user','Pastor',
        required=True, 
        readonly=True, 
        )
    iglesia = fields.Many2One('disc.iglesia', 'Iglesia', 
        required=True,
        domain = 
            [If(
                Id('party',
                        'group_party_admin').in_(
                        Eval('context', {}).get('groups', [])), 
            [],
            [('pastor', '=', Eval('pastor'))],
            )], 
        depends=['pastor'],
        )
    distrito = fields.Many2One('disc.distrito',
        'Distrito',
        required = True,
        )
    zona = fields.Many2One('disc.zona',
        'Zona',
        required = True,
    )
    campo = fields.Many2One('disc.campo',
        'Campo',
        required = True,
    )
    union = fields.Many2One('disc.union',
        'Union',
        required = True,
    )
    semana = fields.Selection(semanas(_YEAR), 
        'Semana', 
        required=True,
        sort = False, )
    fecha_inicio = fields.Date('Fecha inicio', 
        required=True)
    fecha_fin = fields.Date('Fecha fin', 
        required=True)
    mes = fields.Char('Mes', 
        required=True)
    lineas = fields.One2Many('disc.reporte.linea',
        'reporte','Bautizos',
        )
    notas = fields.Text('Notas')
    total = fields.Function(
        fields.Numeric('Total'), 
        'get_total' 
    )

    @classmethod
    def __setup__(cls):
        super(Reporte, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('report_unique', Unique(t, t.iglesia, t.semana),
                'Reporte repetido. Solo se puede tener un reporte por semana de iglesia. Verifique la SEMANA y/o IGLESIA. '),
            ]

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('iglesia.name',) + tuple(clause[1:]),
            ('mes',) + tuple(clause[1:]),
            ]

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query=False):
        pool = Pool()
        Reporte = pool.get('disc.reporte')
        transaction = Transaction().context 
        mes = transaction.get('mes')
        fecha_inicio = transaction.get('fecha_inicio')
        fecha_fin = transaction.get('fecha_fin')
        iglesia = transaction.get('iglesia')
        distrito = transaction.get('distrito')
        domain = domain[:]
        if fecha_inicio is not None: 
            domain = [domain, ('fecha_inicio','>=',fecha_inicio)]
        if fecha_fin is not None: 
            domain = [domain, ('fecha_fin','<=',fecha_fin)]
        if iglesia is not None:
            domain = [domain, ('iglesia','=',iglesia)]
        if distrito is not None:
            domain = [domain, ('distrito','=',distrito)]
        records = super(Reporte, cls).search(domain, offset=offset, limit=limit,
             order=[('fecha_inicio', 'ASC')], count=count, query=query)
        return records

    def get_rec_name(self, name):
        return self.iglesia.name

    @fields.depends('iglesia','mes','semana','lineas','distrito','fecha_inicio')
    def on_change_iglesia(self):
        #print 'Inicio de ciclo'
        pool = Pool() 
        gp = pool.get('disc.gp')

        if self.lineas:
            lineas = []
            self.lineas = lineas 
        #else: 
        if self.iglesia:
            self.distrito = self.iglesia.distrito.id
            self.zona = self.iglesia.distrito.zona.id 
            self.campo = self.iglesia.distrito.zona.campo.id 
            self.union = self.iglesia.distrito.zona.campo.union.id 
            
            id_iglesia = self.iglesia.id 
            

            gps = gp.search([('iglesia', '=', id_iglesia)])
            #print 'Encontrado'+str(gps) 
            lineas = []
            if gps: 
                for gp in gps:
                    Linea = pool.get('disc.reporte.linea')
                    linea = Linea()
                    linea.gp = gp.id 
                    #linea.lider = gp.lider 
                    #linea.fecha = Pool().get('ir.date').today()
                    #linea.iglesia = id_iglesia
                    linea.cantidad = 0 
                    lineas.append(linea)
                self.lineas = lineas 

    @fields.depends('semana', 'fecha_inicio','fecha_fin')
    def on_change_semana(self):
        self.fecha_inicio = fecha_inicio_semana(self.semana)
        self.fecha_fin =  fecha_fin_semana(self.semana)
        self.mes = mes(self.semana)

    @classmethod
    def default_semana(cls):
        return semana_actual(_NOW)

    @classmethod
    def default_total(cls):
        return 0

    @classmethod
    def default_pastor(cls):
        pool = Pool()
        User = pool.get('res.user')
        cursor = Transaction().connection.cursor()
        user = User(Transaction().user).id
        #print 'USUARIO: ' + str(User(Transaction().user).groups)
        return user 

    @fields.depends('lineas', 'total')
    def on_change_lineas(self):
        total = 0 
        if self.lineas:
            for linea in self.lineas:
                total += getattr(linea, 'cantidad', None) or 0
            self.total = total 

    @classmethod
    def set_total(cls, reportes):
        for reporte in reportes:
            if reporte.lineas:
                total = 0 
                for linea in reporte.lineas:
                    total += getattr(linea, 'cantidad', None) or 0
                cls.write([reporte], {
                        'total': total,
                        })

    def get_total(self, name):
        total = 0 
        if self.lineas:
            for linea in self.lineas:
                total += getattr(linea, 'cantidad', None) or 0
        return total 

class InformeIglesia(ModelSQL, ModelView):
    'Informe por Iglesia'
    __name__ = 'disc.informe.iglesia'

    gp = fields.Many2One('disc.gp',
        'Grupo de Esperanza')
    iglesia = fields.Many2One('disc.iglesia',
        'Iglesia')
    total = fields.Numeric('Total')
 
    @staticmethod
    def table_query():
        pool = Pool()
        context = Transaction().context
        Reporte = pool.get('disc.reporte')
        reporte = Reporte.__table__()
        ReporteLinea = pool.get('disc.reporte.linea')
        reporte_linea = ReporteLinea.__table__()

        where = Literal(True)
        if Transaction().context.get('fecha_inicio'):
            where &= reporte.fecha_inicio >= Transaction().context['fecha_inicio']
        if Transaction().context.get('fecha_fin'):
            where &= reporte.fecha_fin <= Transaction().context['fecha_fin']
        if Transaction().context.get('iglesia'):
            where &= reporte.iglesia == Transaction().context['iglesia']

        return (reporte
            .join(reporte_linea,
                condition=reporte_linea.reporte == reporte.id)
            .select(
                Max(reporte_linea.id * 1000).as_('id'),
                Max(reporte.create_uid).as_('create_uid'),
                Max(reporte.create_date).as_('create_date'),
                Max(reporte.write_uid).as_('write_uid'),
                Max(reporte.write_date).as_('write_date'),
                reporte_linea.gp,
                reporte.iglesia,
                (Sum(reporte_linea.cantidad)).as_('total'),
                where=where,
                group_by=[reporte_linea.gp, reporte.iglesia])
            )

class InformeIglesiaContexto(ModelView):
    'Informe Iglesia Contexto'
    __name__ = 'disc.informe.iglesia.context'

    iglesia = fields.Many2One('disc.iglesia',
        'Iglesia')
    mes = fields.Selection(allmonth(_YEAR), 'Mes', sort=False)
    fecha_inicio = fields.Date('Fecha Inicial')
    fecha_fin = fields.Date('Fecha Fin')

    @classmethod
    def default_mes(cls):
        return mes_actual(_NOW)

    @classmethod
    def default_fecha_inicio(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1)
        return actual

    @classmethod
    def default_fecha_fin(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1) + relativedelta(day=31)
        return actual 

    @fields.depends('mes', 'fecha_inicio','fecha_fin')
    def on_change_mes(self):
        self.fecha_inicio = fecha_inicio_mes(self.mes)
        self.fecha_fin =  fecha_fin_mes(self.mes)

class InformeDistrito(ModelSQL, ModelView):
    'Informe por Distrito'
    __name__ = 'disc.informe.distrito'

    iglesia = fields.Many2One('disc.iglesia',
        'Iglesia')
    mes = fields.Char('Mes')
    total = fields.Numeric('Total')
 
    @staticmethod
    def table_query():
        pool = Pool()
        context = Transaction().context

        Reporte = pool.get('disc.reporte')
        reporte = Reporte.__table__()
        ReporteLinea = pool.get('disc.reporte.linea')
        reporte_linea = ReporteLinea.__table__()

        where = Literal(True)
        if Transaction().context.get('fecha_inicio'):
            where &= reporte.fecha_inicio >= Transaction().context['fecha_inicio']
        if Transaction().context.get('fecha_fin'):
            where &= reporte.fecha_fin <= Transaction().context['fecha_fin']
        if Transaction().context.get('distrito'):
            where &= reporte.distrito == Transaction().context['distrito']

        return (reporte
            .join(reporte_linea,
                condition=reporte_linea.reporte == reporte.id)
            .select(
                Max(reporte.id * 1000).as_('id'),
                Max(reporte.create_uid).as_('create_uid'),
                Max(reporte.create_date).as_('create_date'),
                Max(reporte.write_uid).as_('write_uid'),
                Max(reporte.write_date).as_('write_date'),
                reporte.iglesia,
                reporte.mes,
                (Sum(reporte_linea.cantidad)).as_('total'),
                where=where,
                group_by=[reporte.mes,reporte.iglesia])
            )

class InformeDistritoContexto(ModelView):
    'Informe Distrito Contexto'
    __name__ = 'disc.informe.distrito.context'

    distrito = fields.Many2One('disc.distrito',
        'Distrito')
    mes = fields.Selection(allmonth(_YEAR), 'Mes', sort=False)
    fecha_inicio = fields.Date('Fecha Inicial')
    fecha_fin = fields.Date('Fecha Fin')

    @classmethod
    def default_mes(cls):
        return mes_actual(_NOW)

    @classmethod
    def default_fecha_inicio(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1)
        return actual

    @classmethod
    def default_fecha_fin(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1) + relativedelta(day=31)
        return actual 

    @fields.depends('mes', 'fecha_inicio','fecha_fin')
    def on_change_mes(self):
        self.fecha_inicio = fecha_inicio_mes(self.mes)
        self.fecha_fin =  fecha_fin_mes(self.mes)

class InformeZona(ModelSQL, ModelView):
    'Informe por Zona'
    __name__ = 'disc.informe.zona'

    distrito = fields.Many2One('disc.distrito',
        'Distrito')
    mes = fields.Char('Mes')
    total = fields.Numeric('Total')
 
    @staticmethod
    def table_query():
        pool = Pool()
        context = Transaction().context
        Reporte = pool.get('disc.reporte')
        reporte = Reporte.__table__()
        ReporteLinea = pool.get('disc.reporte.linea')
        reporte_linea = ReporteLinea.__table__()

        where = Literal(True)
        if Transaction().context.get('fecha_inicio'):
            where &= reporte.fecha_inicio >= Transaction().context['fecha_inicio']
        if Transaction().context.get('fecha_fin'):
            where &= reporte.fecha_fin <= Transaction().context['fecha_fin']
        if Transaction().context.get('zona'):
            where &= reporte.zona == Transaction().context['zona']

        return (reporte
            .join(reporte_linea,
                condition=reporte_linea.reporte == reporte.id)
            .select(
                Max(reporte.id * 1000).as_('id'),
                Max(reporte.create_uid).as_('create_uid'),
                Max(reporte.create_date).as_('create_date'),
                Max(reporte.write_uid).as_('write_uid'),
                Max(reporte.write_date).as_('write_date'),
                reporte.distrito,
                reporte.mes,
                (Sum(reporte_linea.cantidad)).as_('total'),
                where=where,
                group_by=[reporte.mes,reporte.distrito])
        )

class InformeZonaContexto(ModelView):
    'Informe Zona Contexto'
    __name__ = 'disc.informe.zona.context'

    zona = fields.Many2One('disc.zona',
        'Zona')
    mes = fields.Selection(allmonth(_YEAR), 'Mes', sort=False)
    fecha_inicio = fields.Date('Fecha Inicial')
    fecha_fin = fields.Date('Fecha Fin')

    @classmethod
    def default_mes(cls):
        return mes_actual(_NOW)

    @classmethod
    def default_fecha_inicio(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1)
        return actual

    @classmethod
    def default_fecha_fin(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1) + relativedelta(day=31)
        return actual 

    @fields.depends('mes', 'fecha_inicio','fecha_fin')
    def on_change_mes(self):
        self.fecha_inicio = fecha_inicio_mes(self.mes)
        self.fecha_fin =  fecha_fin_mes(self.mes)

class InformeCampo(ModelSQL, ModelView):
    'Informe por Campo'
    __name__ = 'disc.informe.campo'

    zona = fields.Many2One('disc.zona',
        'Zona')
    mes = fields.Char('Mes')
    total = fields.Numeric('Total')
 
    @staticmethod
    def table_query():
        pool = Pool()
        context = Transaction().context
        Reporte = pool.get('disc.reporte')
        reporte = Reporte.__table__()
        ReporteLinea = pool.get('disc.reporte.linea')
        reporte_linea = ReporteLinea.__table__()

        where = Literal(True)
        if Transaction().context.get('fecha_inicio'):
            where &= reporte.fecha_inicio >= Transaction().context['fecha_inicio']
        if Transaction().context.get('fecha_fin'):
            where &= reporte.fecha_fin <= Transaction().context['fecha_fin']
        if Transaction().context.get('campo'):
            where &= reporte.campo == Transaction().context['campo']

        return (reporte
            .join(reporte_linea,
                condition=reporte_linea.reporte == reporte.id)
            .select(
                Max(reporte.id * 1000).as_('id'),
                Max(reporte.create_uid).as_('create_uid'),
                Max(reporte.create_date).as_('create_date'),
                Max(reporte.write_uid).as_('write_uid'),
                Max(reporte.write_date).as_('write_date'),
                reporte.zona,
                reporte.mes,
                (Sum(reporte_linea.cantidad)).as_('total'),
                where=where,
                group_by=[reporte.mes,reporte.zona])
            )

class InformeCampoContexto(ModelView):
    'Informe Campo Contexto'
    __name__ = 'disc.informe.campo.context'

    campo = fields.Many2One('disc.campo',
        'Campo')
    mes = fields.Selection(allmonth(_YEAR), 'Mes', sort=False)
    fecha_inicio = fields.Date('Fecha Inicial')
    fecha_fin = fields.Date('Fecha Fin')

    @classmethod
    def default_mes(cls):
        return mes_actual(_NOW)

    @classmethod
    def default_fecha_inicio(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1)
        return actual

    @classmethod
    def default_fecha_fin(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1) + relativedelta(day=31)
        return actual 

    @fields.depends('mes', 'fecha_inicio','fecha_fin')
    def on_change_mes(self):
        self.fecha_inicio = fecha_inicio_mes(self.mes)
        self.fecha_fin =  fecha_fin_mes(self.mes)

class InformeUnion(ModelSQL, ModelView):
    'Informe por Union'
    __name__ = 'disc.informe.union'

    campo = fields.Many2One('disc.campo',
        'Campo')
    mes = fields.Char('Mes')
    total = fields.Numeric('Total')
 
    @staticmethod
    def table_query():
        pool = Pool()
        context = Transaction().context
        Reporte = pool.get('disc.reporte')
        reporte = Reporte.__table__()
        ReporteLinea = pool.get('disc.reporte.linea')
        reporte_linea = ReporteLinea.__table__()

        where = Literal(True)
        if Transaction().context.get('fecha_inicio'):
            where &= reporte.fecha_inicio >= Transaction().context['fecha_inicio']
        if Transaction().context.get('fecha_fin'):
            where &= reporte.fecha_fin <= Transaction().context['fecha_fin']
        if Transaction().context.get('union'):
            where &= reporte.union == Transaction().context['union']

        return (reporte
            .join(reporte_linea,
                condition=reporte_linea.reporte == reporte.id)
            .select(
                Max(reporte.id * 1000).as_('id'),
                Max(reporte.create_uid).as_('create_uid'),
                Max(reporte.create_date).as_('create_date'),
                Max(reporte.write_uid).as_('write_uid'),
                Max(reporte.write_date).as_('write_date'),
                reporte.campo,
                reporte.mes,
                (Sum(reporte_linea.cantidad)).as_('total'),
                where=where,
                group_by=[reporte.mes,reporte.campo])
            )

class InformeUnionContexto(ModelView):
    'Informe Union Contexto'
    __name__ = 'disc.informe.union.context'

    union = fields.Many2One('disc.union',
        'Union')
    mes = fields.Selection(allmonth(_YEAR), 'Mes', sort=False)
    fecha_inicio = fields.Date('Fecha Inicial')
    fecha_fin = fields.Date('Fecha Fin')

    @classmethod
    def default_mes(cls):
        return mes_actual(_NOW)

    @classmethod
    def default_fecha_inicio(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1)
        return actual

    @classmethod
    def default_fecha_fin(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1) + relativedelta(day=31)
        return actual 

    @fields.depends('mes', 'fecha_inicio','fecha_fin')
    def on_change_mes(self):
        self.fecha_inicio = fecha_inicio_mes(self.mes)
        self.fecha_fin =  fecha_fin_mes(self.mes)

### REPORTES ###

class ImprimirReporteIglesiaInicio(ModelView):
    'Imprimir Reporte General Iglesia'
    __name__ = 'disc.reporte.iglesia.imprimir.inicio'
    
    fecha = fields.Date('Fecha actual', required=True,
        readonly=True)
    
    usuario = fields.Many2One('res.user','Usuario',
        required=True, 
        readonly=True, 
        )

    iglesia = fields.Many2One('disc.iglesia', 'Iglesia', 
        required=True,
        domain = 
            [If(
                Id('party',
                        'group_party_admin').in_(
                        Eval('context', {}).get('groups', [])), 
            [],
            [('pastor', '=', Eval('usuario'))],
            )],
        depends=['usuario'],
    )

    mes = fields.Selection(allmonth(_YEAR),'Mes', required=True,
        sort=False)

    fecha_inicio = fields.Date('Fecha Inicial')
    fecha_fin = fields.Date('Fecha Fin')

    @classmethod
    def default_mes(cls):
        return mes_actual(_NOW)

    @classmethod
    def default_fecha_inicio(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1)
        return actual

    @classmethod
    def default_fecha_fin(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1) + relativedelta(day=31)
        return actual 

    @fields.depends('mes', 'fecha_inicio','fecha_fin')
    def on_change_mes(self):
        self.fecha_inicio = fecha_inicio_mes(self.mes)
        self.fecha_fin =  fecha_fin_mes(self.mes)

    @classmethod
    def default_usuario(cls):
        pool = Pool()
        User = pool.get('res.user')
        cursor = Transaction().connection.cursor()
        user = User(Transaction().user).id
        return user 

    @staticmethod
    def default_fecha():
        Date = Pool().get('ir.date')
        return Date.today()

class ImprimirReporteIglesia(Wizard):
    'Imprimir Reporte Iglesia'
    __name__ = 'disc.reporte.iglesia.imprimir'
    
    start = StateView('disc.reporte.iglesia.imprimir.inicio',
        'discipulado.imprimir_reporte_iglesia_inicio_form', [
            Button('Cancelar', 'end', 'tryton-cancel'),
            Button('Imprimir', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('disc.reporte.iglesia')

    def do_print_(self, action):
        data = {
            'fecha_inicio': self.start.fecha_inicio,
            'fecha_fin': self.start.fecha_fin,
            'iglesia': self.start.iglesia.name,
            'fecha': self.start.fecha,
            'usuario': self.start.usuario.name,
            'pastor': self.start.iglesia.pastor.name,
            'distrito': self.start.iglesia.distrito.name, 
            }
        return action, data

class ReporteIglesiaTable(ModelSQL, ModelView):
    'Reporte Iglesia Table por GP'
    __name__ = 'disc.reporte.iglesia.table'

    gp = fields.Many2One('disc.gp',
        'Grupo de Esperanza')
    iglesia = fields.Many2One('disc.iglesia',
        'Iglesia')
    total = fields.Numeric('Total')
    fecha_inicio = fields.Date('Fecha Inicio')
    fecha_fin = fields.Date('Fecha Fin')
 
    @staticmethod
    def table_query():
        pool = Pool()
        context = Transaction().context
        Reporte = pool.get('disc.reporte')
        reporte = Reporte.__table__()
        ReporteLinea = pool.get('disc.reporte.linea')
        reporte_linea = ReporteLinea.__table__()
        Lider = pool.get('party.party')
        lider = Lider.__table__()

        where = Literal(True)
        if Transaction().context.get('fecha_inicio'):
            where &= reporte.fecha_inicio >= Transaction().context['fecha_inicio']
        if Transaction().context.get('fecha_fin'):
            where &= reporte.fecha_fin <= Transaction().context['fecha_fin']
        if Transaction().context.get('iglesia'):
            where &= reporte.iglesia == Transaction().context['iglesia']

        return (reporte
            .join(reporte_linea,
                condition=reporte_linea.reporte == reporte.id)
            #.join(reporte_linea,
            #    condition=reporte_linea.gp == lider.id)
            .select(
                Max(reporte_linea.id * 1000).as_('id'),
                Max(reporte.create_uid).as_('create_uid'),
                Max(reporte.create_date).as_('create_date'),
                Max(reporte.write_uid).as_('write_uid'),
                Max(reporte.write_date).as_('write_date'),
                reporte_linea.gp,
                reporte.fecha_inicio,
                reporte.fecha_fin,
                reporte.iglesia,
                (Sum(reporte_linea.cantidad)).as_('total'),
                where=where,
                group_by=[reporte_linea.gp, 
                    reporte.fecha_inicio, 
                    reporte.fecha_fin,
                    reporte.iglesia])
            )

class ReporteIglesia(Report):
    'Reporte Iglesia'
    __name__ = 'disc.reporte.iglesia'

    @classmethod
    def _get_records(cls, ids, model, data):
        Reporte = Pool().get('disc.reporte.iglesia.table')

        clause = ''
        clause = clause[:]
        fecha_inicio = data['fecha_inicio']
        fecha_fin = data['fecha_fin']
        iglesia = data['iglesia']

        if fecha_inicio: 
            clause = [clause, 
                ('fecha_inicio','>=',fecha_inicio)
            ]
        if fecha_fin: 
            clause = [clause, 
                ('fecha_fin','<=',fecha_fin)
            ]
        if iglesia:
            clause = [clause, 
                ('iglesia','=',iglesia)
            ]
        
        return Reporte.search(clause,
                order=[('total', 'DESC')])

    @classmethod
    def get_context(cls, records, data):
        report_context = super(ReporteIglesia, cls).get_context(records, data)

        Reporte = Pool().get('disc.reporte.iglesia.table')
        clause = ''
        clause = clause[:]
        fecha_inicio = data['fecha_inicio']
        fecha_fin = data['fecha_fin']
        iglesia = data['iglesia']

        if fecha_inicio: 
            clause = [clause, 
                ('fecha_inicio','>=',fecha_inicio)
            ]
        if fecha_fin: 
            clause = [clause, 
                ('fecha_fin','<=',fecha_fin)
            ]
        if iglesia:
            clause = [clause, 
                ('iglesia','=',iglesia)
            ]
        
        reportes = Reporte.search(clause)


        report_context['fecha_inicio'] = data['fecha_inicio']
        report_context['fecha_fin'] = data['fecha_fin']
        report_context['fecha'] = data['fecha']
        report_context['iglesia'] = data['iglesia']
        report_context['usuario'] = data['usuario']
        report_context['pastor'] = data['pastor']
        report_context['distrito'] = data['distrito']
        
        report_context['total'] = sum((x.total for x in reportes))
        
        return report_context


## Reporte Distrito

class ImprimirReporteDistritoInicio(ModelView):
    'Imprimir Reporte General Distrito'
    __name__ = 'disc.reporte.distrito.imprimir.inicio'
    
    fecha = fields.Date('Fecha actual', required=True,
        readonly=True)
    
    usuario = fields.Many2One('res.user','Usuario',
        required=True, 
        readonly=True, 
        )

    distrito = fields.Many2One('disc.distrito', 'Distrito', 
        required=True,
        domain = 
            [If(
                Id('party',
                        'group_party_admin').in_(
                        Eval('context', {}).get('groups', [])), 
            [],
            [('pastor', '=', Eval('usuario'))],
            )],
        depends=['usuario'],
    )

    mes = fields.Selection(allmonth(_YEAR),'Mes', required=True,
        sort=False)

    fecha_inicio = fields.Date('Fecha Inicial')
    fecha_fin = fields.Date('Fecha Fin')

    @classmethod
    def default_mes(cls):
        return mes_actual(_NOW)

    @classmethod
    def default_fecha_inicio(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1)
        return actual

    @classmethod
    def default_fecha_fin(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1) + relativedelta(day=31)
        return actual 

    @fields.depends('mes', 'fecha_inicio','fecha_fin')
    def on_change_mes(self):
        self.fecha_inicio = fecha_inicio_mes(self.mes)
        self.fecha_fin =  fecha_fin_mes(self.mes)

    @classmethod
    def default_usuario(cls):
        pool = Pool()
        User = pool.get('res.user')
        cursor = Transaction().connection.cursor()
        user = User(Transaction().user).id
        #print 'USUARIO: ' + str(User(Transaction().user).groups)
        return user 

    @staticmethod
    def default_fecha():
        Date = Pool().get('ir.date')
        return Date.today()

class ImprimirReporteDistrito(Wizard):
    'Imprimir Reporte Distrito'
    __name__ = 'disc.reporte.distrito.imprimir'
    
    start = StateView('disc.reporte.distrito.imprimir.inicio',
        'discipulado.imprimir_reporte_distrito_inicio_form', [
            Button('Cancelar', 'end', 'tryton-cancel'),
            Button('Imprimir', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('disc.reporte.distrito')

    def do_print_(self, action):
        data = {
            'fecha_inicio': self.start.fecha_inicio,
            'fecha_fin': self.start.fecha_fin,
            'distrito': self.start.distrito.name,
            'zona': self.start.distrito.zona.name, 
            'fecha': self.start.fecha,
            'usuario': self.start.usuario.name,
            'pastor': self.start.distrito.pastor.name,
            }
        return action, data

class ReporteDistritoTable(ModelSQL, ModelView):
    'Reporte Distrito Table por GP'
    __name__ = 'disc.reporte.distrito.table'

    iglesia = fields.Many2One('disc.iglesia',
        'Iglesia')
    distrito = fields.Many2One('disc.distrito',
        'Distrito')
    total = fields.Numeric('Total')
    fecha_inicio = fields.Date('Fecha Inicio')
    fecha_fin = fields.Date('Fecha Fin')
 
    @staticmethod
    def table_query():
        pool = Pool()
        context = Transaction().context
        Reporte = pool.get('disc.reporte')
        reporte = Reporte.__table__()
        ReporteLinea = pool.get('disc.reporte.linea')
        reporte_linea = ReporteLinea.__table__()
        
        where = Literal(True)
        if Transaction().context.get('fecha_inicio'):
            where &= reporte.fecha_inicio >= Transaction().context['fecha_inicio']
        if Transaction().context.get('fecha_fin'):
            where &= reporte.fecha_fin <= Transaction().context['fecha_fin']
        if Transaction().context.get('distrito'):
            where &= reporte.distrito == Transaction().context['distrito']

        return (reporte
            .join(reporte_linea,
                condition=reporte_linea.reporte == reporte.id)
            .select(
                Max(reporte_linea.id * 1000).as_('id'),
                Max(reporte.create_uid).as_('create_uid'),
                Max(reporte.create_date).as_('create_date'),
                Max(reporte.write_uid).as_('write_uid'),
                Max(reporte.write_date).as_('write_date'),
                reporte.iglesia,
                reporte.fecha_inicio,
                reporte.fecha_fin,
                reporte.distrito,
                (Sum(reporte_linea.cantidad)).as_('total'),
                where=where,
                group_by=[reporte.iglesia, 
                    reporte.fecha_inicio, 
                    reporte.fecha_fin,
                    reporte.distrito])
            )

class ReporteDistrito(Report):
    'Reporte Distrito'
    __name__ = 'disc.reporte.distrito'

    @classmethod
    def _get_records(cls, ids, model, data):
        Reporte = Pool().get('disc.reporte.distrito.table')

        clause = ''
        clause = clause[:]
        fecha_inicio = data['fecha_inicio']
        fecha_fin = data['fecha_fin']
        distrito = data['distrito']

        if fecha_inicio: 
            clause = [clause, 
                ('fecha_inicio','>=',fecha_inicio)
            ]
        if fecha_fin: 
            clause = [clause, 
                ('fecha_fin','<=',fecha_fin)
            ]
        if distrito:
            clause = [clause, 
                ('distrito','=',distrito)
            ]
        
        return Reporte.search(clause,
                order=[('total', 'DESC')])

    @classmethod
    def get_context(cls, records, data):
        report_context = super(ReporteDistrito, cls).get_context(records, data)

        Reporte = Pool().get('disc.reporte.distrito.table')
        clause = ''
        clause = clause[:]
        fecha_inicio = data['fecha_inicio']
        fecha_fin = data['fecha_fin']
        distrito = data['distrito']

        if fecha_inicio: 
            clause = [clause, 
                ('fecha_inicio','>=',fecha_inicio)
            ]
        if fecha_fin: 
            clause = [clause, 
                ('fecha_fin','<=',fecha_fin)
            ]
        if distrito:
            clause = [clause, 
                ('distrito','=',distrito)
            ]
        
        reportes = Reporte.search(clause)


        report_context['fecha_inicio'] = data['fecha_inicio']
        report_context['fecha_fin'] = data['fecha_fin']
        report_context['fecha'] = data['fecha']
        report_context['distrito'] = data['distrito']
        report_context['zona'] = data['zona']
        report_context['usuario'] = data['usuario']
        report_context['pastor'] = data['pastor']
        
        report_context['total'] = sum((x.total for x in reportes))
        
        return report_context

## Reporte Zona

class ImprimirReporteZonaInicio(ModelView):
    'Imprimir Reporte General Zona'
    __name__ = 'disc.reporte.zona.imprimir.inicio'
    
    fecha = fields.Date('Fecha actual', required=True,
        readonly=True)
    
    usuario = fields.Many2One('res.user','Usuario',
        required=True, 
        readonly=True, 
        )

    zona = fields.Many2One('disc.zona', 'Zona', 
        required=True,
        domain = 
            [If(
                Id('party',
                        'group_party_admin').in_(
                        Eval('context', {}).get('groups', [])), 
            [],
            [('pastor', '=', Eval('usuario'))],
            )],
        depends=['usuario'],
    )

    mes = fields.Selection(allmonth(_YEAR),'Mes', required=True,
        sort=False)

    fecha_inicio = fields.Date('Fecha Inicial')
    fecha_fin = fields.Date('Fecha Fin')

    @classmethod
    def default_mes(cls):
        return mes_actual(_NOW)

    @classmethod
    def default_fecha_inicio(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1)
        return actual

    @classmethod
    def default_fecha_fin(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1) + relativedelta(day=31)
        return actual 

    @fields.depends('mes', 'fecha_inicio','fecha_fin')
    def on_change_mes(self):
        self.fecha_inicio = fecha_inicio_mes(self.mes)
        self.fecha_fin =  fecha_fin_mes(self.mes)

    @classmethod
    def default_usuario(cls):
        pool = Pool()
        User = pool.get('res.user')
        cursor = Transaction().connection.cursor()
        user = User(Transaction().user).id
        #print 'USUARIO: ' + str(User(Transaction().user).groups)
        return user 

    @staticmethod
    def default_fecha():
        Date = Pool().get('ir.date')
        return Date.today()

class ImprimirReporteZona(Wizard):
    'Imprimir Reporte Zona'
    __name__ = 'disc.reporte.zona.imprimir'
    
    start = StateView('disc.reporte.zona.imprimir.inicio',
        'discipulado.imprimir_reporte_zona_inicio_form', [
            Button('Cancelar', 'end', 'tryton-cancel'),
            Button('Imprimir', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('disc.reporte.zona')

    def do_print_(self, action):
        data = {
            'fecha_inicio': self.start.fecha_inicio,
            'fecha_fin': self.start.fecha_fin,
            'zona': self.start.zona.name,
            'campo': self.start.zona.campo.name, 
            'fecha': self.start.fecha,
            'usuario': self.start.usuario.name,
            'pastor': self.start.zona.pastor.name,
            }
        return action, data

class ReporteZonaTable(ModelSQL, ModelView):
    'Reporte Zona Table'
    __name__ = 'disc.reporte.zona.table'

    distrito = fields.Many2One('disc.distrito',
        'Distrito')
    zona = fields.Many2One('disc.zona',
        'Zona')
    total = fields.Numeric('Total')
    fecha_inicio = fields.Date('Fecha Inicio')
    fecha_fin = fields.Date('Fecha Fin')
 
    @staticmethod
    def table_query():
        pool = Pool()
        context = Transaction().context
        Reporte = pool.get('disc.reporte')
        reporte = Reporte.__table__()
        ReporteLinea = pool.get('disc.reporte.linea')
        reporte_linea = ReporteLinea.__table__()
        
        where = Literal(True)
        if Transaction().context.get('fecha_inicio'):
            where &= reporte.fecha_inicio >= Transaction().context['fecha_inicio']
        if Transaction().context.get('fecha_fin'):
            where &= reporte.fecha_fin <= Transaction().context['fecha_fin']
        if Transaction().context.get('zona'):
            where &= reporte.zona == Transaction().context['zona']

        return (reporte
            .join(reporte_linea,
                condition=reporte_linea.reporte == reporte.id)
            .select(
                Max(reporte_linea.id * 1000).as_('id'),
                Max(reporte.create_uid).as_('create_uid'),
                Max(reporte.create_date).as_('create_date'),
                Max(reporte.write_uid).as_('write_uid'),
                Max(reporte.write_date).as_('write_date'),
                reporte.distrito,
                reporte.zona,
                reporte.fecha_inicio,
                reporte.fecha_fin,
                (Sum(reporte_linea.cantidad)).as_('total'),
                where=where,
                group_by=[reporte.distrito, 
                    reporte.zona,
                    reporte.fecha_inicio, 
                    reporte.fecha_fin,
                    ])
            )

class ReporteZona(Report):
    'Reporte Zona'
    __name__ = 'disc.reporte.zona'

    @classmethod
    def _get_records(cls, ids, model, data):
        Reporte = Pool().get('disc.reporte.zona.table')

        clause = ''
        clause = clause[:]
        fecha_inicio = data['fecha_inicio']
        fecha_fin = data['fecha_fin']
        zona = data['zona']

        if fecha_inicio: 
            clause = [clause, 
                ('fecha_inicio','>=',fecha_inicio)
            ]
        if fecha_fin: 
            clause = [clause, 
                ('fecha_fin','<=',fecha_fin)
            ]
        if zona:
            clause = [clause, 
                ('zona','=',zona)
            ]
        
        return Reporte.search(clause,
                order=[('total', 'DESC')])

    @classmethod
    def get_context(cls, records, data):
        report_context = super(ReporteZona, cls).get_context(records, data)

        Reporte = Pool().get('disc.reporte.zona.table')
        clause = ''
        clause = clause[:]
        fecha_inicio = data['fecha_inicio']
        fecha_fin = data['fecha_fin']
        zona = data['zona']

        if fecha_inicio: 
            clause = [clause, 
                ('fecha_inicio','>=',fecha_inicio)
            ]
        if fecha_fin: 
            clause = [clause, 
                ('fecha_fin','<=',fecha_fin)
            ]
        if zona:
            clause = [clause, 
                ('zona','=',zona)
            ]
        
        reportes = Reporte.search(clause)


        report_context['fecha_inicio'] = data['fecha_inicio']
        report_context['fecha_fin'] = data['fecha_fin']
        report_context['fecha'] = data['fecha']
        report_context['zona'] = data['zona']
        report_context['campo'] = data['campo']
        report_context['usuario'] = data['usuario']
        report_context['pastor'] = data['pastor']
        
        report_context['total'] = sum((x.total for x in reportes))
        
        return report_context

## Reporte Campo

class ImprimirReporteCampoInicio(ModelView):
    'Imprimir Reporte General Campo'
    __name__ = 'disc.reporte.campo.imprimir.inicio'
    
    fecha = fields.Date('Fecha actual', required=True,
        readonly=True)
    
    usuario = fields.Many2One('res.user','Usuario',
        required=True, 
        readonly=True, 
        )

    campo = fields.Many2One('disc.campo', 'Campo', 
        required=True,
        domain = 
            [If(
                Id('party',
                        'group_party_admin').in_(
                        Eval('context', {}).get('groups', [])), 
            [],
            [('pastor', '=', Eval('usuario'))],
            )],
        depends=['usuario'],
    )

    mes = fields.Selection(allmonth(_YEAR),'Mes', required=True,
        sort=False)

    fecha_inicio = fields.Date('Fecha Inicial')
    fecha_fin = fields.Date('Fecha Fin')

    @classmethod
    def default_mes(cls):
        return mes_actual(_NOW)

    @classmethod
    def default_fecha_inicio(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1)
        return actual

    @classmethod
    def default_fecha_fin(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1) + relativedelta(day=31)
        return actual 

    @fields.depends('mes', 'fecha_inicio','fecha_fin')
    def on_change_mes(self):
        self.fecha_inicio = fecha_inicio_mes(self.mes)
        self.fecha_fin =  fecha_fin_mes(self.mes)

    @classmethod
    def default_usuario(cls):
        pool = Pool()
        User = pool.get('res.user')
        cursor = Transaction().connection.cursor()
        user = User(Transaction().user).id
        #print 'USUARIO: ' + str(User(Transaction().user).groups)
        return user 

    @staticmethod
    def default_fecha():
        Date = Pool().get('ir.date')
        return Date.today()

class ImprimirReporteCampo(Wizard):
    'Imprimir Reporte Campo'
    __name__ = 'disc.reporte.campo.imprimir'
    
    start = StateView('disc.reporte.campo.imprimir.inicio',
        'discipulado.imprimir_reporte_campo_inicio_form', [
            Button('Cancelar', 'end', 'tryton-cancel'),
            Button('Imprimir', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('disc.reporte.campo')

    def do_print_(self, action):
        data = {
            'fecha_inicio': self.start.fecha_inicio,
            'fecha_fin': self.start.fecha_fin,
            'campo': self.start.campo.name,
            'union': self.start.campo.union.name, 
            'pastor': self.start.campo.pastor.name,
            'fecha': self.start.fecha,
            'usuario': self.start.usuario.name,
            }
        return action, data

class ReporteCampoTable(ModelSQL, ModelView):
    'Reporte Campo Table'
    __name__ = 'disc.reporte.campo.table'

    campo = fields.Many2One('disc.campo',
        'Campo')
    zona = fields.Many2One('disc.zona',
        'Zona')
    total = fields.Numeric('Total')
    fecha_inicio = fields.Date('Fecha Inicio')
    fecha_fin = fields.Date('Fecha Fin')
 
    @staticmethod
    def table_query():
        pool = Pool()
        context = Transaction().context
        Reporte = pool.get('disc.reporte')
        reporte = Reporte.__table__()
        ReporteLinea = pool.get('disc.reporte.linea')
        reporte_linea = ReporteLinea.__table__()
        
        where = Literal(True)
        if Transaction().context.get('fecha_inicio'):
            where &= reporte.fecha_inicio >= Transaction().context['fecha_inicio']
        if Transaction().context.get('fecha_fin'):
            where &= reporte.fecha_fin <= Transaction().context['fecha_fin']
        if Transaction().context.get('campo'):
            where &= reporte.campo == Transaction().context['campo']

        return (reporte
            .join(reporte_linea,
                condition=reporte_linea.reporte == reporte.id)
            .select(
                Max(reporte_linea.id * 1000).as_('id'),
                Max(reporte.create_uid).as_('create_uid'),
                Max(reporte.create_date).as_('create_date'),
                Max(reporte.write_uid).as_('write_uid'),
                Max(reporte.write_date).as_('write_date'),
                reporte.campo,
                reporte.zona,
                reporte.fecha_inicio,
                reporte.fecha_fin,
                (Sum(reporte_linea.cantidad)).as_('total'),
                where=where,
                group_by=[
                    reporte.campo, 
                    reporte.zona,
                    reporte.fecha_inicio, 
                    reporte.fecha_fin,
                    ])
            )

class ReporteCampo(Report):
    'Reporte Campo'
    __name__ = 'disc.reporte.campo'

    @classmethod
    def _get_records(cls, ids, model, data):
        Reporte = Pool().get('disc.reporte.campo.table')

        clause = ''
        clause = clause[:]
        fecha_inicio = data['fecha_inicio']
        fecha_fin = data['fecha_fin']
        campo = data['campo']

        if fecha_inicio: 
            clause = [clause, 
                ('fecha_inicio','>=',fecha_inicio)
            ]
        if fecha_fin: 
            clause = [clause, 
                ('fecha_fin','<=',fecha_fin)
            ]
        if campo:
            clause = [clause, 
                ('campo','=',campo)
            ]
        
        return Reporte.search(clause,
                order=[('total', 'DESC')])

    @classmethod
    def get_context(cls, records, data):
        report_context = super(ReporteCampo, cls).get_context(records, data)

        Reporte = Pool().get('disc.reporte.campo.table')
        clause = ''
        clause = clause[:]
        fecha_inicio = data['fecha_inicio']
        fecha_fin = data['fecha_fin']
        campo = data['campo']

        if fecha_inicio: 
            clause = [clause, 
                ('fecha_inicio','>=',fecha_inicio)
            ]
        if fecha_fin: 
            clause = [clause, 
                ('fecha_fin','<=',fecha_fin)
            ]
        if campo:
            clause = [clause, 
                ('campo','=',campo)
            ]
        
        reportes = Reporte.search(clause)


        report_context['fecha_inicio'] = data['fecha_inicio']
        report_context['fecha_fin'] = data['fecha_fin']
        report_context['fecha'] = data['fecha']
        report_context['campo'] = data['campo']
        report_context['union'] = data['union']
        report_context['usuario'] = data['usuario']
        report_context['pastor'] = data['pastor']
        
        report_context['total'] = sum((x.total for x in reportes))
        
        return report_context

## Reporte Union

class ImprimirReporteUnionInicio(ModelView):
    'Imprimir Reporte General Union'
    __name__ = 'disc.reporte.union.imprimir.inicio'
    
    fecha = fields.Date('Fecha actual', required=True,
        readonly=True)
    
    usuario = fields.Many2One('res.user','Usuario',
        required=True, 
        readonly=True, 
        )

    union = fields.Many2One('disc.union', 'Union', 
        required=True,
        domain = 
            [If(
                Id('party',
                        'group_party_admin').in_(
                        Eval('context', {}).get('groups', [])), 
            [],
            [('pastor', '=', Eval('usuario'))],
            )],
        depends=['usuario'],
    )

    mes = fields.Selection(allmonth(_YEAR),'Mes', required=True,
        sort=False)

    fecha_inicio = fields.Date('Fecha Inicial')
    fecha_fin = fields.Date('Fecha Fin')

    @classmethod
    def default_mes(cls):
        return mes_actual(_NOW)

    @classmethod
    def default_fecha_inicio(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1)
        return actual

    @classmethod
    def default_fecha_fin(cls):
        hoy = _NOW
        actual = datetime.date(hoy.year, hoy.month, 1) + relativedelta(day=31)
        return actual 

    @fields.depends('mes', 'fecha_inicio','fecha_fin')
    def on_change_mes(self):
        self.fecha_inicio = fecha_inicio_mes(self.mes)
        self.fecha_fin =  fecha_fin_mes(self.mes)

    @classmethod
    def default_usuario(cls):
        pool = Pool()
        User = pool.get('res.user')
        cursor = Transaction().connection.cursor()
        user = User(Transaction().user).id
        #print 'USUARIO: ' + str(User(Transaction().user).groups)
        return user 

    @staticmethod
    def default_fecha():
        Date = Pool().get('ir.date')
        return Date.today()

class ImprimirReporteUnion(Wizard):
    'Imprimir Reporte Union'
    __name__ = 'disc.reporte.union.imprimir'
    
    start = StateView('disc.reporte.union.imprimir.inicio',
        'discipulado.imprimir_reporte_union_inicio_form', [
            Button('Cancelar', 'end', 'tryton-cancel'),
            Button('Imprimir', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('disc.reporte.union')

    def do_print_(self, action):
        data = {
            'fecha_inicio': self.start.fecha_inicio,
            'fecha_fin': self.start.fecha_fin,
            'union': self.start.union.name, 
            'pastor': self.start.union.pastor.name,
            'fecha': self.start.fecha,
            'usuario': self.start.usuario.name,
            }
        return action, data

class ReporteUnionTable(ModelSQL, ModelView):
    'Reporte Union Table'
    __name__ = 'disc.reporte.union.table'

    campo = fields.Many2One('disc.campo',
        'Campo')
    union = fields.Many2One('disc.union',
        'Union')
    total = fields.Numeric('Total')
    fecha_inicio = fields.Date('Fecha Inicio')
    fecha_fin = fields.Date('Fecha Fin')
 
    @staticmethod
    def table_query():
        pool = Pool()
        context = Transaction().context
        Reporte = pool.get('disc.reporte')
        reporte = Reporte.__table__()
        ReporteLinea = pool.get('disc.reporte.linea')
        reporte_linea = ReporteLinea.__table__()
        
        where = Literal(True)
        if Transaction().context.get('fecha_inicio'):
            where &= reporte.fecha_inicio >= Transaction().context['fecha_inicio']
        if Transaction().context.get('fecha_fin'):
            where &= reporte.fecha_fin <= Transaction().context['fecha_fin']
        if Transaction().context.get('union'):
            where &= reporte.union == Transaction().context['union']

        return (reporte
            .join(reporte_linea,
                condition=reporte_linea.reporte == reporte.id)
            .select(
                Max(reporte_linea.id * 1000).as_('id'),
                Max(reporte.create_uid).as_('create_uid'),
                Max(reporte.create_date).as_('create_date'),
                Max(reporte.write_uid).as_('write_uid'),
                Max(reporte.write_date).as_('write_date'),
                reporte.union,
                reporte.campo,
                reporte.fecha_inicio,
                reporte.fecha_fin,
                (Sum(reporte_linea.cantidad)).as_('total'),
                where=where,
                group_by=[
                    reporte.union, 
                    reporte.campo,
                    reporte.fecha_inicio, 
                    reporte.fecha_fin,
                    ])
            )

class ReporteUnion(Report):
    'Reporte Union'
    __name__ = 'disc.reporte.union'

    @classmethod
    def _get_records(cls, ids, model, data):
        Reporte = Pool().get('disc.reporte.union.table')

        clause = ''
        clause = clause[:]
        fecha_inicio = data['fecha_inicio']
        fecha_fin = data['fecha_fin']
        union = data['union']

        if fecha_inicio: 
            clause = [clause, 
                ('fecha_inicio','>=',fecha_inicio)
            ]
        if fecha_fin: 
            clause = [clause, 
                ('fecha_fin','<=',fecha_fin)
            ]
        if union:
            clause = [clause, 
                ('union','=',union)
            ]
        
        #orden descendente
        return Reporte.search(clause,
                order=[('total', 'DESC')])

    @classmethod
    def get_context(cls, records, data):
        report_context = super(ReporteUnion, cls).get_context(records, data)

        Reporte = Pool().get('disc.reporte.union.table')
        clause = ''
        clause = clause[:]
        fecha_inicio = data['fecha_inicio']
        fecha_fin = data['fecha_fin']
        union = data['union']

        if fecha_inicio: 
            clause = [clause, 
                ('fecha_inicio','>=',fecha_inicio)
            ]
        if fecha_fin: 
            clause = [clause, 
                ('fecha_fin','<=',fecha_fin)
            ]
        if union:
            clause = [clause, 
                ('union','=',union)
            ]
        
        reportes = Reporte.search(clause)


        report_context['fecha_inicio'] = data['fecha_inicio']
        report_context['fecha_fin'] = data['fecha_fin']
        report_context['fecha'] = data['fecha']
        report_context['union'] = data['union']
        report_context['usuario'] = data['usuario']
        report_context['pastor'] = data['pastor']
        
        report_context['total'] = sum((x.total for x in reportes))
        
        return report_context