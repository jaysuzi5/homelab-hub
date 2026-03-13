from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Max
from django.core.serializers.json import DjangoJSONEncoder
from datetime import datetime, timedelta
import json
from .forms import RetirementForm, PortfolioAccountForm, PortfolioSnapshotForm, ElectricityUsageForm, NetWorthForm
from .models import PortfolioAccount, PortfolioSnapshot, ElectricityUsage, NetWorth
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

