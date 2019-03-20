from trytond.pool import Pool
from . import opportunity
from . import account
from . import party
from . import product
from . import subscription
from . import service

def register():
    Pool.register(
        account.CreateChartProperties, 
        party.Party,
        subscription.Subscription,
        subscription.Line, 
        subscription.LineConsumption, 
        subscription.SubscriptionContext, 
        opportunity.SaleOpportunity,
        opportunity.SaleOpportunityLine,
        opportunity.SaleMeeting, 
        service.Service, 
        product.Template, 
        product.Category, 
        account.Invoice, 
        account.Configuration, 
        account.ConfigurationDefaultAccount,
        subscription.PrintOverdueReportStart,
        subscription.OverdueReportTable,
        subscription.PrintGradeOverdueReportStart,
        subscription.GradeOverdueReportTable, 
        subscription.CreateSubscriptionInvoiceStart,
        account.PayInvoiceStart,
        module='training', type_='model')
    Pool.register(
        account.PayInvoice,
        subscription.PrintOverdueReport,
        subscription.PrintGradeOverdueReport,
        subscription.CreateLineConsumption, 
        subscription.CreateSubscriptionInvoice, 
        account.CreateChart,
        module='training', type_='wizard')
    Pool.register(
        account.InvoiceReportReceipt,
        subscription.OverdueReport,
        subscription.GradeOverdueReport, 
        party.PartyStatementReport, 
        module='training', type_='report') 