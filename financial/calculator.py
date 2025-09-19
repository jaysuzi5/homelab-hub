import numpy as np
import statistics

def monte_carlo_simulation(
    balance,
    annual_return,
    annual_volatility,
    inflation,
    years,
    withdrawal,
    n_simulations=1000,
    freq="monthly"
):
    periods_per_year = 12 if freq == "monthly" else 1
    periods = int(round(years * periods_per_year))  # <-- convert to integer
    dt = 1 / periods_per_year

    success_count = 0

    for _ in range(n_simulations):
        portfolio = balance
        for t in range(periods):
            # random return
            r = np.random.normal(annual_return * dt, annual_volatility * np.sqrt(dt))
            portfolio *= (1 + r)

            # withdraw (inflation adjusted)
            withdrawal_adj = withdrawal * ((1 + inflation) ** (t * dt))
            portfolio -= withdrawal_adj
            if portfolio <= 0:
                break
        if portfolio > 0:
            success_count += 1

    return success_count / n_simulations


def find_max_withdrawal(
    balance,
    annual_return,
    annual_volatility,
    inflation,
    years,
    target_success,
    n_simulations=1000,
    freq="monthly",
    tol=0.01
):
    periods_per_year = 12 if freq == "monthly" else 1
    # Conservative upper bound: total balance spread over horizon
    high = balance / years / periods_per_year * 2
    low = 0
    best_withdrawal = 0

    while high - low > tol:
        mid = (low + high) / 2
        success = monte_carlo_simulation(
            balance, annual_return, annual_volatility, inflation,
            years, mid, n_simulations, freq
        )
        if success >= target_success:
            best_withdrawal = mid
            low = mid
        else:
            high = mid

    return best_withdrawal

def generate_balance_over_time(balance, current_age, annual_return, annual_volatility, inflation, years, withdrawal, freq="monthly", n_simulations=1000):
    """
    Return a list of portfolio balances at each period for charting,
    along with corresponding ages for the x-axis.
    """
    periods_per_year = 12 if freq == "monthly" else 1
    periods = int(years * periods_per_year)
    dt = 1 / periods_per_year

    balances_average = []
    balances_median = []
    balances_p10 = []
    balances_p20 = []
    simulation_balances = {}

    for _ in range(n_simulations):
        ages = []  # Will just return the last list of ages
        portfolio = balance
        for t in range(periods):
            # Random return per period
            r = np.random.normal(annual_return * dt, annual_volatility * np.sqrt(dt))
            portfolio *= (1 + r)

            # Inflation-adjusted withdrawal
            withdrawal_adj = withdrawal * ((1 + inflation) ** (t * dt))
            portfolio -= withdrawal_adj
            portfolio = max(portfolio, 0)

            age = round(current_age + t * dt, 2)
            ages.append(age)  # age with two decimals
            if age not in simulation_balances:
                simulation_balances[age] = []
            simulation_balances[age].append(portfolio)
        
    for age in ages:
        balances_list = simulation_balances[age]
        balances_average.append(round(sum(balances_list) / n_simulations,0))
        balances_median.append(round(statistics.median(balances_list),0))
        balances_p10.append(round(float(np.percentile(balances_list, 10)),0))
        balances_p20.append(round(float(np.percentile(balances_list, 20)),0))
    
    return balances_average, balances_median, balances_p10, balances_p20, ages

def generate_balance_constant_return(balance, current_age, annual_return, inflation, years, withdrawal, freq="monthly"):
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
        # Constant return per period
        r = annual_return * dt
        portfolio *= (1 + r)

        # Inflation-adjusted withdrawal
        withdrawal_adj = withdrawal * ((1 + inflation) ** (t * dt))
        portfolio -= withdrawal_adj
        portfolio = max(portfolio, 0)

        balances.append(portfolio)
        ages.append(round(current_age + t * dt, 2))  # age with two decimals

    return balances, ages
