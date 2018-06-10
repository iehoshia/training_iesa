=======================
Account Budget Scenario
=======================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts

Install account_budget::

    >>> config = activate_modules('account_budget')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> cash = accounts['cash']

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create a budget::

    >>> Budget = Model.get('account.budget')
    >>> budget = Budget()
    >>> budget.name = 'Budget'
    >>> budget.fiscalyear = fiscalyear
    >>> budget.amount = Decimal(100)
    >>> revenue_budget = budget.children.new(name='Revenue')
    >>> revenue_budget.fiscalyear = fiscalyear
    >>> revenue_budget.accounts.append(revenue)
    >>> revenue_budget.amount = Decimal(150)
    >>> expense_budget = budget.children.new(name='Expense')
    >>> expense_budget.fiscalyear = fiscalyear
    >>> expense_budget.accounts.append(expense)
    >>> expense_budget.amount = Decimal(-50)
    >>> budget.save()

Create Moves for checking with budget::

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])
    >>> journal_expense, = Journal.find([
    ...         ('code', '=', 'EXP'),
    ...         ])
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(120)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(120)
    >>> line.party = customer
    >>> move.click('post')
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_expense
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = expense
    >>> line.debit = Decimal(50)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.credit = Decimal(50)
    >>> line.party = customer
    >>> move.click('post')

Test budget balance and difference::

    >>> budget.balance
    Decimal('70.00')
    >>> budget.difference
    Decimal('30.00')
    >>> revenue_budget, expense_budget = budget.children
    >>> revenue_budget.balance
    Decimal('120.00')
    >>> revenue_budget.difference
    Decimal('30.00')
    >>> expense_budget.balance
    Decimal('-50.00')
    >>> expense_budget.difference
    Decimal('0.00')

Create a distribution for the periods::

    >>> distribute = Wizard('account.budget.distribute_period', [budget])
    >>> distribute.execute('distribute')
    >>> revenue_budget, expense_budget = budget.children
    >>> len(budget.periods)
    12
    >>> all(p.amount == Decimal('8.33') for p in budget.periods)
    True
    >>> len(revenue_budget.periods)
    12
    >>> all(p.amount == Decimal('12.50') for p in revenue_budget.periods)
    True
    >>> len(expense_budget.periods)
    12
    >>> all(p.amount == Decimal('-4.16') for p in expense_budget.periods)
    True

Test period balance balance and difference::

    >>> budget.periods[0].balance
    Decimal('70.00')
    >>> budget.periods[0].difference
    Decimal('-61.67')
    >>> budget.periods[1].balance
    Decimal('0.00')
    >>> budget.periods[1].difference
    Decimal('8.33')
    >>> revenue_budget, expense_budget = budget.children
    >>> revenue_budget.periods[0].balance
    Decimal('120.00')
    >>> revenue_budget.periods[0].difference
    Decimal('-107.50')
    >>> revenue_budget.periods[1].balance
    Decimal('0.00')
    >>> revenue_budget.periods[1].difference
    Decimal('12.50')
    >>> expense_budget.periods[0].balance
    Decimal('-50.00')
    >>> expense_budget.periods[0].difference
    Decimal('45.84')
    >>> expense_budget.periods[1].balance
    Decimal('0.00')
    >>> expense_budget.periods[1].difference
    Decimal('-4.16')

Copy the budget with zeroed amounts::

    >>> copy_budget = Wizard('account.budget.copy', [budget])
    >>> copy_budget.form.name
    u'Budget'
    >>> copy_budget.form.name = 'New Budget'
    >>> copy_budget.form.fiscalyear = fiscalyear
    >>> copy_budget.form.zero_amounts = True
    >>> copy_budget.execute('copy')
    >>> new_budget, = copy_budget.actions[0]
    >>> new_budget.name
    u'New Budget'
    >>> new_budget.amount
    Decimal('0')
    >>> len(budget.children)
    2
    >>> all(p.amount == Decimal(0) for p in new_budget.children)
    True
    >>> len(new_budget.periods)
    0
