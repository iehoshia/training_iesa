from trytond.pool import Pool
from .party import *
from .subscription import * 
from .opportunity import * 
from .service import * 
#from .move import * 
from .product import * 
from .account import * 

def register():
    Pool.register(
        CreateChartProperties, 
        Party,
        Subscription,
        Line, 
        LineConsumption, 
        SubscriptionContext, 
        SaleOpportunity,
        SaleOpportunityLine,
        SaleMeeting, 
        Service, 
        #Move, 
        Template, 
        Invoice, 
        Configuration, 
        ConfigurationDefaultAccount,
        PrintOverdueReportStart,
        OverdueReportTable,
        PrintGradeOverdueReportStart,
        GradeOverdueReportTable, 
        CreateSubscriptionInvoiceStart,
        PayInvoiceStart,
        MoveLine, 
        module='training', type_='model')

    Pool.register(
        PayInvoice,
        PrintOverdueReport,
        PrintGradeOverdueReport,
        CreateLineConsumption, 
        CreateSubscriptionInvoice, 
        CreateChart,
#        ImprimirReporteDistrito,
#        ImprimirReporteZona,
#        ImprimirReporteCampo,
#        ImprimirReporteUnion,
        module='training', type_='wizard')

    Pool.register(
        InvoiceReportReceipt,
        OverdueReport,
        GradeOverdueReport, 
#        ReporteDistrito,
#        ReporteZona,
#        ReporteCampo,
#        ReporteUnion,
        module='training', type_='report') 