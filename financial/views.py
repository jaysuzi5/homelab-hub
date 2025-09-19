import os
from django.shortcuts import render
from .forms import RetirementForm
from .calculator import monte_carlo_simulation, find_max_withdrawal

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
                    "target_success": round(target_success * 100, 1),
                    "withdrawal": round(data["best_withdrawal"], 2),
                }
        
            result['balances_average'] = data["balances_average"]
            result['balances_median'] = data["balances_median"]
            result['balances_p_target'] = data["balances_p_target"]
            result['balances_p65'] = data["balances_p65"]
            result['constant_balances'] = data["constant_balances"]
            result['ages'] = data["ages"]
            result['four_percent_rule'] = four_percent_rule
    else:
        form = RetirementForm()


    presets = {
        "ss_benefits_62": os.getenv("SS_BENEFITS_62", 0),
        "ss_benefits_65": os.getenv("SS_BENEFITS_65", 0),
        "ss_benefits_67": os.getenv("SS_BENEFITS_67", 0),
    }
    return render(request, "financial/retirement.html", {"form": form, "result": result, "presets": presets})

