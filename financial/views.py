from django.shortcuts import render
from .forms import RetirementForm
from .calculator import monte_carlo_simulation, find_max_withdrawal, generate_balance_over_time, generate_balance_constant_return

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

            years = end_age - current_age
            four_percent_rule = round(balance * 0.04 / 12,2)

            if mode == "fixed":
                withdrawal = form.cleaned_data["withdrawal"]
                success_rate = monte_carlo_simulation(
                    balance, annual_return, annual_volatility,
                    inflation, years, withdrawal,
                    n_simulations=n_simulations, freq=freq
                )
                result = {
                    "mode": "fixed",
                    "withdrawal": withdrawal,
                    "success_rate": round(success_rate * 100, 1),
                }
            elif mode == "target":
                target_success = form.cleaned_data["target_success"]
                withdrawal = find_max_withdrawal(
                    balance, annual_return, annual_volatility,
                    inflation, years, target_success,
                    n_simulations=n_simulations, freq=freq
                )
                result = {
                    "mode": "target",
                    "target_success": round(target_success * 100, 1),
                    "withdrawal": round(withdrawal, 2),
                }
            balances_average, balances_median, balances_p10, balances_p20, ages = generate_balance_over_time(
                balance, current_age, annual_return, annual_volatility,
                inflation, years, withdrawal, freq
            )
            constant_balances, _ = generate_balance_constant_return(
                balance, current_age, annual_return, inflation, years, withdrawal, freq
            )            
            result['balances_average'] = balances_average
            result['balances_median'] = balances_median
            result['balances_p10'] = balances_p10
            result['balances_p20'] = balances_p20
            result['constant_balances'] = constant_balances
            result['ages'] = ages
            result['four_percent_rule'] = four_percent_rule
    else:
        form = RetirementForm()

    return render(request, "financial/retirement.html", {"form": form, "result": result})

