from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Max
from django.core.serializers.json import DjangoJSONEncoder
from datetime import datetime, timedelta, date as date_type
import json
from .forms import RetirementForm, PortfolioAccountForm, PortfolioSnapshotForm, ElectricityUsageForm, NetWorthForm, ForecastSettingsForm
from .models import PortfolioAccount, PortfolioSnapshot, ElectricityUsage, NetWorth, ForecastSettings
from .calculator import monte_carlo_simulation, find_max_withdrawal
from config.utils import get_config

SS_BENEFITS_62 = get_config("SS_BENEFITS_62",0)
SS_BENEFITS_65 = get_config("SS_BENEFITS_65",0)
SS_BENEFITS_67 = get_config("SS_BENEFITS_67",0)
SS_BENEFITS_70 = get_config("SS_BENEFITS_70",0)

def retirement(request):
    result = None

    if request.method == "POST":
        form = RetirementForm(request.POST)
        if form.is_valid():
            mode = form.cleaned_data["mode"]
            current_age = form.cleaned_data["current_age"]
            end_age = form.cleaned_data["end_age"]
            balance = form.cleaned_data["balance"]
            annual_return = form.cleaned_data["annual_return"]
            inflation = form.cleaned_data["inflation"]
            annual_volatility = form.cleaned_data["annual_volatility"]
            n_simulations = form.cleaned_data["n_simulations"]
            freq = form.cleaned_data["withdrawal_freq"]
            ss_age = form.cleaned_data["ss_age"] 
            ss_amount = form.cleaned_data["ss_benefits"]

            years = end_age - current_age
            periods_per_year = 12 if freq == "monthly" else 1
            four_percent_rule = round(balance * 0.04 / periods_per_year, 2)
            target_success = form.cleaned_data["target_success"]
            
            if mode == "fixed":
                withdrawal = form.cleaned_data["withdrawal"]
                data = monte_carlo_simulation(
                    balance, annual_return, annual_volatility,
                    inflation, years, withdrawal, current_age,
                    n_simulations=n_simulations, freq=freq,
                    ss_age=ss_age, ss_amount=ss_amount, 
                    target_success=target_success
                )
                result = {
                    "mode": "fixed",
                    "withdrawal": withdrawal,
                    "success_rate": round(data["success_percent"] * 100, 1),
                }
            elif mode == "target":
                data = find_max_withdrawal(
                    balance, annual_return, annual_volatility,
                    inflation, years, target_success, current_age,
                    n_simulations=n_simulations, freq=freq,
                    ss_age=ss_age, ss_amount=ss_amount
                )
                result = {
                    "mode": "target",
                    "withdrawal": round(data["best_withdrawal"], 2),
                }

            result["target_success"] = round(target_success * 100, 1)
            result['balances_average'] = data["balances_average"]
            result['balances_median'] = data["balances_median"]
            result['balances_p_target'] = data["balances_p_target"]
            result['balances_p65'] = data["balances_p65"]
            result['constant_balances'] = data["constant_balances"]
            result['last_values'] = data["last_values"]
            result['ages'] = data["ages"]
            result['four_percent_rule'] = four_percent_rule
    else:
        form = RetirementForm()


    presets = {
        "ss_benefits_62": SS_BENEFITS_62,
        "ss_benefits_65": SS_BENEFITS_65,
        "ss_benefits_67": SS_BENEFITS_67,
        "ss_benefits_70": SS_BENEFITS_70,
    }
    request.otel_page_summary = {
        "page": "retirement",
        "method": request.method,
        "mode": result.get("mode") if result else None,
        "success_rate": result.get("success_rate") if result else None,
        "max_withdrawal": result.get("withdrawal") if result else None,
    }
    return render(request, "financial/retirement.html", {"form": form, "result": result, "presets": presets})


@login_required
def portfolio_overview(request):
    """Portfolio overview dashboard showing all accounts and historical balances."""

    # Get all active accounts
    accounts = PortfolioAccount.objects.filter(is_active=True)

    # Calculate total portfolio value and breakdowns
    total_portfolio = 0
    tax_treatment_totals = {
        'PRE_TAX': 0,
        'ROTH': 0,
        'PENSION': 0,
        'TAXABLE': 0,
        'HSA': 0,
        'CASH': 0,
    }
    account_type_totals = {}

    account_data = []
    for account in accounts:
        latest_snapshot = account.snapshots.order_by('-snapshot_date').first()
        latest_balance = latest_snapshot.balance if latest_snapshot else 0
        snapshot_date = latest_snapshot.snapshot_date if latest_snapshot else None

        total_portfolio += latest_balance

        # Aggregate by tax treatment
        tax_treatment_totals[account.tax_treatment] += float(latest_balance)

        # Aggregate by account type
        account_type = account.get_account_type_display()
        if account_type not in account_type_totals:
            account_type_totals[account_type] = 0
        account_type_totals[account_type] += float(latest_balance)

        account_data.append({
            'id': account.id,
            'name': account.name,
            'type': account_type,
            'institution': account.institution,
            'balance': latest_balance,
            'tax_treatment': account.get_tax_treatment_display_short(),
            'tax_treatment_full': account.get_tax_treatment_display(),
            'as_of_date': snapshot_date
        })

    # Get historical data for portfolio growth chart (last 12 months)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=365)

    # Get all unique dates where any snapshot was recorded
    all_snapshot_dates = PortfolioSnapshot.objects.filter(
        account__is_active=True,
        snapshot_date__gte=start_date,
        snapshot_date__lte=end_date
    ).values_list('snapshot_date', flat=True).distinct().order_by('snapshot_date')

    # For each date, calculate total portfolio value using most recent balance for each account
    chart_data = []
    for snapshot_date in all_snapshot_dates:
        total_value = 0

        # For each active account, get the most recent balance as of this date
        for account in accounts:
            latest_snapshot = PortfolioSnapshot.objects.filter(
                account=account,
                snapshot_date__lte=snapshot_date
            ).order_by('-snapshot_date').first()

            if latest_snapshot:
                total_value += float(latest_snapshot.balance)

        if total_value > 0:
            chart_data.append({
                'date': snapshot_date.strftime('%Y-%m-%d'),
                'balance': total_value
            })

    context = {
        'total_portfolio': total_portfolio,
        'tax_treatment_totals': tax_treatment_totals,
        'account_type_totals': account_type_totals,
        'accounts': account_data,
        'chart_data': json.dumps(chart_data, cls=DjangoJSONEncoder),
    }
    request.otel_page_summary = {
        "page": "portfolio",
        "account_count": len(account_data),
        "total_portfolio": float(total_portfolio),
    }
    return render(request, "financial/portfolio.html", context)


@login_required
def account_list(request):
    """List all portfolio accounts."""
    accounts = PortfolioAccount.objects.all()
    return render(request, "financial/account_list.html", {"accounts": accounts})


@login_required
def account_create(request):
    """Create a new portfolio account."""
    if request.method == "POST":
        form = PortfolioAccountForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('account_list')
    else:
        form = PortfolioAccountForm()

    return render(request, "financial/account_form.html", {"form": form, "action": "Create"})


@login_required
def account_edit(request, pk):
    """Edit an existing portfolio account."""
    account = get_object_or_404(PortfolioAccount, pk=pk)

    if request.method == "POST":
        form = PortfolioAccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            return redirect('account_list')
    else:
        form = PortfolioAccountForm(instance=account)

    return render(request, "financial/account_form.html", {"form": form, "action": "Edit", "account": account})


@login_required
def account_delete(request, pk):
    """Delete a portfolio account."""
    account = get_object_or_404(PortfolioAccount, pk=pk)

    if request.method == "POST":
        account.delete()
        return redirect('account_list')

    return render(request, "financial/account_confirm_delete.html", {"account": account})


@login_required
def snapshot_create(request):
    """Add a new balance snapshot."""
    if request.method == "POST":
        form = PortfolioSnapshotForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                return redirect('portfolio_overview')
            except Exception as e:
                form.add_error(None, f"Error saving snapshot: {str(e)}")
    else:
        # Pre-fill with today's date
        form = PortfolioSnapshotForm(initial={'snapshot_date': datetime.now().date()})

    return render(request, "financial/snapshot_form.html", {"form": form})


@login_required
def account_snapshots(request, pk):
    """View all snapshots for a specific account."""
    account = get_object_or_404(PortfolioAccount, pk=pk)
    snapshots = PortfolioSnapshot.objects.filter(account=account).order_by('-snapshot_date')

    # Prepare chart data
    chart_data = []
    for snapshot in snapshots.order_by('snapshot_date'):
        chart_data.append({
            'date': snapshot.snapshot_date.strftime('%Y-%m-%d'),
            'balance': float(snapshot.balance)
        })

    context = {
        'account': account,
        'snapshots': snapshots,
        'chart_data': json.dumps(chart_data, cls=DjangoJSONEncoder),
    }

    return render(request, "financial/account_snapshots.html", context)


@login_required
def snapshot_edit(request, pk):
    """Edit an existing balance snapshot."""
    snapshot = get_object_or_404(PortfolioSnapshot, pk=pk)

    if request.method == "POST":
        form = PortfolioSnapshotForm(request.POST, instance=snapshot)
        if form.is_valid():
            try:
                form.save()
                return redirect('account_snapshots', pk=snapshot.account.pk)
            except Exception as e:
                form.add_error(None, f"Error updating snapshot: {str(e)}")
    else:
        form = PortfolioSnapshotForm(instance=snapshot)

    return render(request, "financial/snapshot_edit_form.html", {"form": form, "snapshot": snapshot})


@login_required
def snapshot_delete(request, pk):
    """Delete a balance snapshot."""
    snapshot = get_object_or_404(PortfolioSnapshot, pk=pk)
    account_pk = snapshot.account.pk

    if request.method == "POST":
        snapshot.delete()
        return redirect('account_snapshots', pk=account_pk)

    return render(request, "financial/snapshot_confirm_delete.html", {"snapshot": snapshot})


@login_required
def electricity_usage_list(request):
    """List all electricity usage records with charts."""
    records = ElectricityUsage.objects.all().order_by('-date')

    # Prepare chart data
    chart_data = []
    for record in reversed(list(records)):
        chart_data.append({
            'date': record.date.strftime('%Y-%m'),
            'kwh_consumed': float(record.kwh_consumed) if record.kwh_consumed else 0,
            'produced_kwh': float(record.produced_kwh) if record.produced_kwh else 0,
            'net_kwh': float(record.net_kwh) if record.net_kwh else 0,
            'total_cost': float(record.total_cost) if record.total_cost else 0,
        })

    # Calculate summary stats
    latest_record = records.first()
    total_records = records.count()

    # Annual totals for current year
    current_year = datetime.now().year
    year_records = records.filter(date__year=current_year)
    year_kwh = sum(r.kwh_consumed or 0 for r in year_records)
    year_produced = sum(r.produced_kwh or 0 for r in year_records)
    year_cost = sum(r.total_cost or 0 for r in year_records)

    context = {
        'records': records,
        'chart_data': json.dumps(chart_data, cls=DjangoJSONEncoder),
        'latest_record': latest_record,
        'total_records': total_records,
        'current_year': current_year,
        'year_kwh': year_kwh,
        'year_produced': year_produced,
        'year_cost': year_cost,
    }

    return render(request, "financial/electricity_usage_list.html", context)


@login_required
def electricity_usage_create(request):
    """Add a new electricity usage record."""
    if request.method == "POST":
        form = ElectricityUsageForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                return redirect('electricity_usage_list')
            except Exception as e:
                form.add_error(None, f"Error saving record: {str(e)}")
    else:
        # Pre-fill with first day of current month
        today = datetime.now().date()
        initial_date = today.replace(day=1)
        form = ElectricityUsageForm(initial={'date': initial_date})

    return render(request, "financial/electricity_usage_form.html", {"form": form, "action": "Add"})


@login_required
def electricity_usage_edit(request, pk):
    """Edit an existing electricity usage record."""
    record = get_object_or_404(ElectricityUsage, pk=pk)

    if request.method == "POST":
        form = ElectricityUsageForm(request.POST, instance=record)
        if form.is_valid():
            try:
                form.save()
                return redirect('electricity_usage_list')
            except Exception as e:
                form.add_error(None, f"Error updating record: {str(e)}")
    else:
        form = ElectricityUsageForm(instance=record)

    return render(request, "financial/electricity_usage_form.html", {"form": form, "action": "Edit", "record": record})


@login_required
def electricity_usage_delete(request, pk):
    """Delete an electricity usage record."""
    record = get_object_or_404(ElectricityUsage, pk=pk)

    if request.method == "POST":
        record.delete()
        return redirect('electricity_usage_list')

    return render(request, "financial/electricity_usage_confirm_delete.html", {"record": record})


@login_required
def networth_list(request):
    """List all net worth records with charts."""
    records = NetWorth.objects.all().order_by('-date')

    # Add calculated percent for display
    records_with_percent = []
    for record in records:
        percent_display = None
        if record.percent_change:
            percent_display = (float(record.percent_change) - 1) * 100
        records_with_percent.append({
            'record': record,
            'percent_display': percent_display
        })

    # Prepare chart data
    chart_data = []
    for record in reversed(list(records)):
        chart_data.append({
            'date': record.date.strftime('%Y-%m'),
            'net_worth': float(record.net_worth),
            'change': float(record.change_from_previous) if record.change_from_previous else 0,
        })

    # Calculate summary stats
    latest_record = records.first()
    total_records = records.count()

    # Calculate year-to-date change
    current_year = datetime.now().year
    year_start = records.filter(date__year=current_year).order_by('date').first()
    year_end = records.filter(date__year=current_year).order_by('-date').first()

    ytd_change = 0
    ytd_percent = 0
    if year_start and year_end:
        ytd_change = year_end.net_worth - year_start.net_worth
        ytd_percent = (ytd_change / year_start.net_worth * 100) if year_start.net_worth else 0

    # Calculate all-time stats
    oldest_record = records.last()
    total_change = 0
    total_percent = 0
    if oldest_record and latest_record:
        total_change = latest_record.net_worth - oldest_record.net_worth
        total_percent = (total_change / oldest_record.net_worth * 100) if oldest_record.net_worth else 0

    context = {
        'records_with_percent': records_with_percent,
        'chart_data': json.dumps(chart_data, cls=DjangoJSONEncoder),
        'latest_record': latest_record,
        'total_records': total_records,
        'current_year': current_year,
        'ytd_change': ytd_change,
        'ytd_percent': ytd_percent,
        'oldest_record': oldest_record,
        'total_change': total_change,
        'total_percent': total_percent,
    }

    return render(request, "financial/networth_list.html", context)


@login_required
def networth_create(request):
    """Add a new net worth record."""
    if request.method == "POST":
        form = NetWorthForm(request.POST)
        if form.is_valid():
            try:
                # Calculate change from previous month
                new_record = form.save(commit=False)

                # Find the most recent record before this date
                previous_record = NetWorth.objects.filter(
                    date__lt=new_record.date
                ).order_by('-date').first()

                if previous_record:
                    new_record.change_from_previous = new_record.net_worth - previous_record.net_worth
                    new_record.percent_change = new_record.net_worth / previous_record.net_worth

                new_record.save()
                return redirect('networth_list')
            except Exception as e:
                form.add_error(None, f"Error saving record: {str(e)}")
    else:
        # Pre-fill with first day of current month
        today = datetime.now().date()
        initial_date = today.replace(day=1)
        form = NetWorthForm(initial={'date': initial_date})

    return render(request, "financial/networth_form.html", {"form": form, "action": "Add"})


@login_required
def networth_edit(request, pk):
    """Edit an existing net worth record."""
    record = get_object_or_404(NetWorth, pk=pk)

    if request.method == "POST":
        form = NetWorthForm(request.POST, instance=record)
        if form.is_valid():
            try:
                # Recalculate change from previous month
                updated_record = form.save(commit=False)

                # Find the most recent record before this date
                previous_record = NetWorth.objects.filter(
                    date__lt=updated_record.date
                ).order_by('-date').first()

                if previous_record:
                    updated_record.change_from_previous = updated_record.net_worth - previous_record.net_worth
                    updated_record.percent_change = updated_record.net_worth / previous_record.net_worth

                updated_record.save()
                return redirect('networth_list')
            except Exception as e:
                form.add_error(None, f"Error updating record: {str(e)}")
    else:
        form = NetWorthForm(instance=record)

    return render(request, "financial/networth_form.html", {"form": form, "action": "Edit", "record": record})


@login_required
def networth_delete(request, pk):
    """Delete a net worth record."""
    record = get_object_or_404(NetWorth, pk=pk)

    if request.method == "POST":
        record.delete()
        return redirect('networth_list')

    return render(request, "financial/networth_confirm_delete.html", {"record": record})


DEFAULT_WITHDRAWAL_ORDER = ['CASH', 'ROTH_IRA', 'ROTH_401K', 'TRADITIONAL_IRA', '401K', 'HSA', 'BROKERAGE', 'OTHER']
ACCOUNT_TYPE_LABELS = dict(PortfolioAccount.ACCOUNT_TYPE_CHOICES)


@login_required
def portfolio_forecast(request):
    settings_obj = ForecastSettings.objects.first()
    if not settings_obj:
        settings_obj = ForecastSettings.objects.create(withdrawal_order=DEFAULT_WITHDRAWAL_ORDER)

    if request.method == 'POST':
        form = ForecastSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            settings_obj = form.save(commit=False)
            withdrawal_order_raw = request.POST.get('withdrawal_order_json', '')
            try:
                parsed = json.loads(withdrawal_order_raw)
                settings_obj.withdrawal_order = parsed if isinstance(parsed, list) else DEFAULT_WITHDRAWAL_ORDER
            except (json.JSONDecodeError, ValueError):
                settings_obj.withdrawal_order = DEFAULT_WITHDRAWAL_ORDER
            settings_obj.save()
    else:
        form = ForecastSettingsForm(instance=settings_obj)

    accounts = PortfolioAccount.objects.filter(is_active=True).prefetch_related('snapshots')
    investment_accounts = []
    pension_accounts = []

    for account in accounts:
        latest = account.snapshots.order_by('-snapshot_date').first()
        balance = float(latest.balance) if latest else 0.0
        acct_data = {
            'id': account.id,
            'name': account.name,
            'account_type': account.account_type,
            'account_type_label': ACCOUNT_TYPE_LABELS.get(account.account_type, account.account_type),
            'tax_treatment': account.tax_treatment,
            'balance': balance,
            'annual_growth_rate': float(account.annual_growth_rate),
            'pension_benefit_age': account.pension_benefit_age,
            'pension_monthly_benefit': float(account.pension_monthly_benefit) if account.pension_monthly_benefit else 0.0,
        }
        if account.tax_treatment == 'PENSION':
            pension_accounts.append(acct_data)
        else:
            investment_accounts.append(acct_data)

    withdrawal_order = settings_obj.withdrawal_order or DEFAULT_WITHDRAWAL_ORDER

    # Ensure all account types present in accounts are covered
    existing_types = {a['account_type'] for a in investment_accounts}
    for t in existing_types:
        if t not in withdrawal_order:
            withdrawal_order.append(t)

    # Calculate current age dynamically from DOB
    current_age = None
    current_age_display = None
    if settings_obj.date_of_birth:
        today_date = date_type.today()
        current_age = (today_date - settings_obj.date_of_birth).days / 365.25
        current_age_display = round(current_age, 1)

    forecast_rows = _run_forecast(investment_accounts, pension_accounts, settings_obj, withdrawal_order, current_age)

    # Build the ordered list of account types that actually have accounts (for table columns)
    ordered_types_with_accounts = [t for t in withdrawal_order if t in existing_types]

    # Annotate each annual row with withdrawal columns list
    annual_rows = []
    for i, row in enumerate(forecast_rows):
        if i == 0 or row['month_of_year'] == 1 or i == len(forecast_rows) - 1:
            row['withdrawal_columns'] = [row['withdrawal_by_type'].get(t, 0.0) for t in ordered_types_with_accounts]
            annual_rows.append(row)

    chart_data = [{'date': r['date'], 'balance': r['total_balance']} for r in forecast_rows]

    withdrawal_order_display = [
        {
            'code': t,
            'label': ACCOUNT_TYPE_LABELS.get(t, t),
            'has_accounts': t in existing_types,
        }
        for t in withdrawal_order
    ]

    context = {
        'form': form,
        'settings': settings_obj,
        'current_age_display': current_age_display,
        'investment_accounts': investment_accounts,
        'pension_accounts': pension_accounts,
        'annual_rows': annual_rows,
        'ordered_withdrawal_types': ordered_types_with_accounts,
        'ordered_type_labels': [ACCOUNT_TYPE_LABELS.get(t, t) for t in ordered_types_with_accounts],
        'withdrawal_order_display': withdrawal_order_display,
        'chart_data': json.dumps(chart_data, cls=DjangoJSONEncoder),
        'withdrawal_order_json': json.dumps(withdrawal_order),
    }
    request.otel_page_summary = {"page": "portfolio_forecast"}
    return render(request, 'financial/portfolio_forecast.html', context)


# Account tax treatments that require grossing up withdrawals
_TAXABLE_TREATMENTS = frozenset(['PRE_TAX', 'TAXABLE'])


def _run_forecast(investment_accounts, pension_accounts, settings, withdrawal_order, current_age=None):
    if current_age is None:
        if settings.date_of_birth:
            current_age = (date_type.today() - settings.date_of_birth).days / 365.25
        else:
            return []

    max_age = settings.max_age
    base_spending = float(settings.monthly_spending)
    spending_inflation = float(settings.spending_inflation_rate)
    ss_benefit_today = float(settings.ss_monthly_benefit)
    ss_inflation = float(settings.ss_inflation_rate)
    ss_start_age = float(settings.ss_start_age)
    tax_rate = float(settings.effective_tax_rate)
    tax_net = 1.0 - tax_rate  # net multiplier after tax

    balances = {a['id']: a['balance'] for a in investment_accounts}
    total_months = max(0, int((max_age - current_age) * 12))

    accounts_by_type = {}
    for acct in investment_accounts:
        accounts_by_type.setdefault(acct['account_type'], []).append(acct)
    for t in accounts_by_type:
        accounts_by_type[t].sort(key=lambda x: x['name'])

    today = date_type.today()
    rows = []

    for m in range(total_months):
        age = current_age + m / 12.0
        year_offset = m / 12.0
        year = today.year + (today.month - 1 + m) // 12
        month = (today.month - 1 + m) % 12 + 1

        monthly_spending = base_spending * ((1 + spending_inflation) ** year_offset)

        # Gross income — SS and pension are taxable ordinary income
        ss_gross = 0.0
        if age >= ss_start_age:
            ss_gross = ss_benefit_today * ((1 + ss_inflation) ** year_offset)

        pension_gross = 0.0
        for pa in pension_accounts:
            if pa['pension_benefit_age'] and age >= pa['pension_benefit_age']:
                pension_gross += pa['pension_monthly_benefit'] * ((1 + ss_inflation) ** year_offset)

        # Net income after estimated tax on SS + pension
        ss_net = ss_gross * tax_net
        pension_net = pension_gross * tax_net
        taxes_on_income = (ss_gross + pension_gross) * tax_rate

        # Apply monthly growth before withdrawal
        for acct in investment_accounts:
            monthly_rate = (1 + acct['annual_growth_rate']) ** (1 / 12) - 1
            balances[acct['id']] = balances[acct['id']] * (1 + monthly_rate)

        # Net spending still needed from accounts after income
        remaining_net = max(0.0, monthly_spending - ss_net - pension_net)
        withdrawal_by_type = {}
        taxes_on_withdrawals = 0.0

        for acct_type in withdrawal_order:
            if remaining_net <= 0:
                break
            for acct in accounts_by_type.get(acct_type, []):
                if remaining_net <= 0:
                    break
                available = max(0.0, balances[acct['id']])
                is_taxable = acct['tax_treatment'] in _TAXABLE_TREATMENTS

                if is_taxable and tax_rate > 0:
                    # Gross up: need remaining_net / tax_net gross to receive remaining_net net
                    gross_needed = remaining_net / tax_net
                    gross_withdraw = min(available, gross_needed)
                    net_received = gross_withdraw * tax_net
                    taxes_on_withdrawals += gross_withdraw * tax_rate
                else:
                    gross_withdraw = min(available, remaining_net)
                    net_received = gross_withdraw

                balances[acct['id']] -= gross_withdraw
                remaining_net -= net_received
                if gross_withdraw > 0:
                    withdrawal_by_type[acct_type] = withdrawal_by_type.get(acct_type, 0.0) + gross_withdraw

        shortfall = max(0.0, remaining_net)
        monthly_taxes = taxes_on_income + taxes_on_withdrawals
        total_balance = max(0.0, sum(balances.values()))

        rows.append({
            'date': f"{year}-{month:02d}",
            'month_num': m,
            'month_of_year': month,
            'age': round(age, 1),
            'monthly_spending': round(monthly_spending, 2),
            'ss_income': round(ss_gross, 2),
            'pension_income': round(pension_gross, 2),
            'net_need': round(max(0.0, monthly_spending - ss_net - pension_net), 2),
            'monthly_taxes': round(monthly_taxes, 2),
            'total_balance': round(total_balance, 2),
            'withdrawal_by_type': {k: round(v, 2) for k, v in withdrawal_by_type.items()},
            'shortfall': round(shortfall, 2),
        })

        if total_balance <= 0 and remaining_net > 0:
            break

    return rows

