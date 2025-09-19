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
    ss_amount = 0
):


    balances_average = []
    balances_median = []
    balances_p15 = []
    balances_p85 = []
    simulation_balances = {}
    periods_per_year = 12 if freq == "monthly" else 1
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
            if age > ss_age:
                ss_amount_adj = ss_amount * ((1 + inflation) ** (t * dt))
                withdrawal_adj -= ss_amount_adj
            portfolio -= withdrawal_adj
            if portfolio < 0:
                portfolio = 0
            simulation_balances[age].append(portfolio)
        if portfolio > 0:
            success_count += 1

    success_percent = success_count / n_simulations
    for age in ages:
        balances_list = simulation_balances[age]
        balances_average.append(round(sum(balances_list) / n_simulations,0))
        balances_median.append(round(statistics.median(balances_list),0))
        balances_p15.append(round(float(np.percentile(balances_list, 15)),0))
        balances_p85.append(round(float(np.percentile(balances_list, 85)),0))
    constant_balances, ages = generate_balance_constant_return(balance, current_age, annual_return, inflation, years, withdrawal, freq, ss_age, ss_amount)

    data = {
        "success_percent": success_percent, 
        "balances_average": balances_average, 
        "balances_median": balances_median, 
        "balances_p15": balances_p15, 
        "balances_p85": balances_p85, 
        "constant_balances": constant_balances, 
        "ages": ages
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
            years, mid, current_age, n_simulations, freq, ss_age, ss_amount
        )
        if data["success_percent"] >= target_success:
            return_data = data
            return_data["best_withdrawal"] = mid
            low = mid
        else:
            high = mid

    print(f"success after {iterations} iterations - high: {high} - low: {low} = {high - low} ")
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
