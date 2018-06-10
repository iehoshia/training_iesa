import datetime
from datetime import timedelta, date 
from dateutil.relativedelta import relativedelta

_YEAR = datetime.datetime.now().year
_NOW = datetime.datetime.now()
 
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

def allsundays(year):
    list = []
    for i in range(0,-2,-1):
        #print str(i)
        d = date(year-i, 1, 1)                    # January 1st
        f = date(year-i, 1, 1)                    # January 1st
        d += timedelta( (5 - d.weekday() + 7) % 7)  # First Sunday
        f += timedelta( f.weekday() + 6)  # First Friday
        while d.year == year-i:
            #print str(d.year) + ' - ' + str(year-i)
            s = d.isocalendar()[1]            
            semana = str(s) + ' - ' +str(year-i)
            etiqueta = 'Semana # '+str(s) + ' - '+ str(year - i) #+ ' del '+ unicode(d)+' al ' +unicode(f)
            #print 'SEMANA: ' + semana + ' - ' + etiqueta
            list.append((semana, etiqueta )) 
            d += timedelta(days = 7)
            f += timedelta(days = 7)
        list.append(('',''))
    return list 

#lista = allsundays(_YEAR)
#print lista

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

#print ':::MESES:::'

#lista = allmonth(_YEAR)
#print lista

def semanas(year):
    list = []
    d = date(year, 1, 1)                    # January 1st
    d += timedelta( (5 - d.weekday() + 7) % 7)  # First Sunday
    
    while d.year == year:
        s = d.isocalendar()[1]
        semana = str(s) + ' - ' +str(year)
        etiqueta = 'Semana #: '+str(s) #+ ' del '+ unicode(d)+' al ' +unicode(f)
        list.append((semana, etiqueta )) 
        d += timedelta(days = 7)
    return list 

def semana_actual(date):
    """This code was provided in the previous answer! It's not mine!"""
    s = date.isocalendar()[1]
    year = date.year
    semana = str(s) + ' - ' + str(year)
    return semana 

def mes_actual(fecha):
    mes = numero_mes(fecha.month)
    year = fecha.year
    semana = str(mes) + ' - ' + str(year)
    return semana 

mes = mes_actual(date.today())
print str(mes)

def semana(semana):
    digit = ''

    for char in str(semana):
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
    anhio = int(anhio)

    actual = datetime.date(anhio, mes, 1)
    return actual

fecha = fecha_inicio_mes('Septiembre - 2017')
#print str(fecha)

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

fecha = fecha_fin_mes('Octubre - 2017')
#print str(fecha)


def fecha_fin_semana(semana, year):
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
    anhio = str(year)
    return mes + ' - ' + anhio


#lista = semanas(_YEAR)
#print lista

#semana = semana(semana_actual(_NOW))
#print 'Semana '+semana 

#fecha_inicio = fecha_inicio_semana(float(semana), _YEAR)
#fecha_fin = fecha_fin_semana(float(semana), _YEAR)
#mes = mes(float(semana), _YEAR)
#print 'Fecha inicio: '+ str(fecha_inicio)
#print 'Fecha fin: '+ str(fecha_fin)
#print 'Mes: ' + str(mes)