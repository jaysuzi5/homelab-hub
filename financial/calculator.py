import numpy as np
import statistics

def monte_carlo_simulation(
    balance,
    annual_return,
    annual_volatility,
    inflation,
    years,
    withdrawal,
    current_age,
    n_simulations=1000,
    freq="monthly",
    ss_age = 67,
    ss_amount = 0,
    target_success = 0.85
):
    balances_average = []
    balances_median = []
    balances_p_target = []
    balances_p65 = []
    simulation_balances = {}
    ss_amount_original = ss_amount
    periods_per_year = 12 if freq == "monthly" else 1
    if freq != "monthly":
        ss_amount = ss_amount * 12    # ss amount is always sent in as monthly
    periods = int(round(years * periods_per_year))  # <-- convert to integer
    dt = 1 / periods_per_year

    success_count = 0

    for _ in range(n_simulations):
        ages = []  # Will just return the last list of ages
        portfolio = balance
        for t in range(periods):
            age = round(current_age + t * dt, 2)
            ages.append(age)  # age with two decimals
            if age not in simulation_balances:
                simulation_balances[age] = []

            portfolio = gbm_step(portfolio, annual_return, annual_volatility, dt)
            # withdraw (inflation adjusted)
            withdrawal_adj = withdrawal * ((1 + inflation) ** (t * dt))
            if age >= ss_age:
                ss_amount_adj = ss_amount * ((1 + inflation) ** (t * dt))
                withdrawal_adj -= ss_amount_adj
            portfolio -= withdrawal_adj
            if portfolio < 0:
                portfolio = 0
            simulation_balances[age].append(portfolio)
        if portfolio > 0:
            success_count += 1

    success_percent = success_count / n_simulations
    p_target = 100 - target_success * 100
    for age in ages:
        balances_list = simulation_balances[age]
        balances_average.append(round(sum(balances_list) / n_simulations,0))
        balances_median.append(round(statistics.median(balances_list),0))
        balances_p_target.append(round(float(np.percentile(balances_list, p_target)),0))
        balances_p65.append(round(float(np.percentile(balances_list, 65)),0))
    constant_balances, ages = generate_balance_constant_return(balance, current_age, annual_return, inflation, years, withdrawal, freq, ss_age, ss_amount_original)

    last_values = {
        "balances_average": balances_average[-1], 
        "balances_median": balances_median[-1], 
        "balances_p_target": balances_p_target[-1], 
        "balances_p65": balances_p65[-1], 
        "constant_balances": constant_balances[-1], 
    }

    data = {
        "success_percent": success_percent, 
        "balances_average": balances_average, 
        "balances_median": balances_median, 
        "balances_p_target": balances_p_target, 
        "balances_p65": balances_p65, 
        "constant_balances": constant_balances, 
        "ages": ages,
        "last_values": last_values
    }

    return data


def find_max_withdrawal(
    balance,
    annual_return,
    annual_volatility,
    inflation,
    years,
    target_success,
    current_age,
    n_simulations=1000,
    freq="monthly",
    ss_age = 67,
    ss_amount = 0,
    tol=1.00
):
    return_data = {}
    periods_per_year = 12 if freq == "monthly" else 1
    # Conservative upper bound: total balance spread over horizon
    high = balance / years / periods_per_year * 2
    low = 0
    iterations = 0
    while high - low > tol:
        iterations += 1
        mid = (low + high) / 2
        data = monte_carlo_simulation(
            balance, annual_return, annual_volatility, inflation,
            years, mid, current_age, n_simulations, freq, ss_age, ss_amount, target_success
        )
        if data["success_percent"] >= target_success:
            return_data = data
            return_data["best_withdrawal"] = mid
            low = mid
        else:
            high = mid
    return return_data

def generate_balance_constant_return(
    balance, 
    current_age, 
    annual_return, 
    inflation, 
    years, 
    withdrawal, 
    freq="monthly",
    ss_age = 67,
    ss_amount = 0):
    """
    Return a list of portfolio balances at each period for charting,
    using a constant (deterministic) return, along with corresponding ages.
    """
    periods_per_year = 12 if freq == "monthly" else 1
    if freq != "monthly":
        ss_amount = ss_amount * 12    # ss amount is always sent in as monthly
    periods = int(years * periods_per_year)
    dt = 1 / periods_per_year

    balances = []
    ages = []

    portfolio = balance
    for t in range(periods):
        age = round(current_age + t * dt, 2)
        # Constant return per period
        r = annual_return * dt
        portfolio *= (1 + r)

        # Inflation-adjusted withdrawal
        withdrawal_adj = withdrawal * ((1 + inflation) ** (t * dt))
        if age > ss_age:
            ss_amount_adj = ss_amount * ((1 + inflation) ** (t * dt))
            withdrawal_adj -= ss_amount_adj

        portfolio -= withdrawal_adj
        portfolio = max(portfolio, 0)

        balances.append(portfolio)
        ages.append(round(current_age + t * dt, 2))  # age with two decimals

    return balances, ages

def gbm_step(portfolio, mu, sigma, dt):
    # Z is a random normal
    Z = np.random.normal(0, 1)
    # GBM update
    return float(portfolio * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z))
