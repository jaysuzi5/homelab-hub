# IRS Uniform Lifetime Table (2022 final regs, Treas. Reg. §1.401(a)(9)-9)
# Keys are integer ages; values are distribution period (divisor).
IRS_UNIFORM_LIFETIME_TABLE = {
    72: 27.4, 73: 26.5, 74: 25.5,
    75: 24.6, 76: 23.7, 77: 22.9, 78: 22.0, 79: 21.1,
    80: 20.2, 81: 19.4, 82: 18.5, 83: 17.7, 84: 16.8,
    85: 16.0, 86: 15.2, 87: 14.4, 88: 13.7, 89: 12.9,
    90: 12.2, 91: 11.5, 92: 10.8, 93: 10.1, 94: 9.5,
    95: 8.9,  96: 8.4,  97: 7.8,  98: 7.3,  99: 6.8,
    100: 6.4, 101: 6.0, 102: 5.6, 103: 5.2, 104: 4.9,
    105: 4.6, 106: 4.3, 107: 4.1, 108: 3.9, 109: 3.7,
    110: 3.5, 111: 3.4, 112: 3.3, 113: 3.1, 114: 3.0,
    115: 2.9, 116: 2.8, 117: 2.7, 118: 2.5, 119: 2.3,
    120: 2.0,
}

RMD_START_AGE = 75  # SECURE 2.0: born after 1960


def get_rmd_factor(age: int) -> float:
    """Return IRS Uniform Lifetime Table distribution period for integer age.
    Ages below 72 return 0 (no RMD factor). Ages above 120 use 2.0."""
    if age < 72:
        return 0.0
    return IRS_UNIFORM_LIFETIME_TABLE.get(age, 2.0)


DEFAULT_BRACKETS_MFJ_2026 = [
    [0, 0.10],
    [24800, 0.12],
    [100800, 0.22],
    [211400, 0.24],
    [403550, 0.32],
    [512450, 0.35],
    [768700, 0.37],
]

# Provisional income thresholds for SS taxation (lower, upper)
_SS_THRESHOLDS = {
    'MFJ': (32000, 44000),
    'SINGLE': (25000, 34000),
}


def compute_taxable_ss(ss_annual: float, provisional_income: float, filing_status: str = 'MFJ') -> float:
    """Return the portion of annual SS income that is federally taxable (0, 50%, or 85%)."""
    lower, upper = _SS_THRESHOLDS.get(filing_status, _SS_THRESHOLDS['MFJ'])
    if provisional_income <= lower:
        return 0.0
    elif provisional_income <= upper:
        return min(0.5 * ss_annual, 0.5 * (provisional_income - lower))
    else:
        tier1 = 0.5 * (upper - lower)
        tier2 = 0.85 * (provisional_income - upper)
        return min(0.85 * ss_annual, tier1 + tier2)


def apply_brackets(taxable_income: float, brackets: list) -> float:
    """Compute federal income tax using progressive brackets.

    brackets: [[threshold, rate], ...] sorted ascending by threshold.
    Each entry means: income at or above `threshold` is taxed at `rate`.
    """
    if taxable_income <= 0:
        return 0.0
    tax = 0.0
    for i, (threshold, rate) in enumerate(brackets):
        if taxable_income <= threshold:
            break
        next_threshold = brackets[i + 1][0] if i + 1 < len(brackets) else taxable_income
        band_top = min(taxable_income, next_threshold)
        band = band_top - threshold
        if band > 0:
            tax += band * rate
    return tax


def get_marginal_rate(taxable_income: float, brackets: list) -> float:
    """Return the marginal federal rate at the given taxable income level."""
    marginal = brackets[0][1]
    for threshold, rate in brackets:
        if taxable_income >= threshold:
            marginal = rate
        else:
            break
    return marginal


def compute_annual_tax(
    ss_annual: float,
    pension_annual: float,
    pre_tax_annual: float,
    taxable_annual: float,
    filing_status: str,
    standard_deduction: float,
    brackets: list,
    pa_flat_rate: float,
    pa_retirement_age: float,
    age: float,
) -> dict:
    """Compute annual federal + PA state tax on retirement income components.

    Income sources and their treatment:
    - ss_annual: SS benefits (0/50/85% federally taxable via provisional income; PA exempt)
    - pension_annual: defined-benefit pension (fully federal taxable; PA exempt)
    - pre_tax_annual: traditional IRA / 401k withdrawals (fully federal taxable;
                      PA exempt after pa_retirement_age)
    - taxable_annual: taxable brokerage / interest / dividends (federal ordinary income;
                      PA taxable at flat rate)

    Returns dict: federal_tax, pa_tax, total_tax, effective_rate, federal_taxable_income
    """
    # Provisional income: non-SS income + half of SS (tax-exempt interest assumed 0)
    provisional = pension_annual + pre_tax_annual + taxable_annual + 0.5 * ss_annual
    taxable_ss = compute_taxable_ss(ss_annual, provisional, filing_status)

    federal_agi = taxable_ss + pension_annual + pre_tax_annual + taxable_annual
    federal_taxable = max(0.0, federal_agi - standard_deduction)
    federal_tax = apply_brackets(federal_taxable, brackets)

    # PA state tax: exempt SS always, pension always; pre-tax IRA/401k exempt after retirement age
    pa_taxable = taxable_annual
    if age < pa_retirement_age:
        pa_taxable += pre_tax_annual
    pa_tax = pa_taxable * pa_flat_rate

    total_tax = federal_tax + pa_tax
    total_income = ss_annual + pension_annual + pre_tax_annual + taxable_annual

    return {
        'federal_tax': federal_tax,
        'pa_tax': pa_tax,
        'total_tax': total_tax,
        'effective_rate': total_tax / total_income if total_income > 0 else 0.0,
        'federal_taxable_income': federal_taxable,
        'taxable_ss': taxable_ss,
    }


# ACA Marketplace premium estimates for a Gold plan (2026 est., MFJ, PA)
# Based on household MAGI vs FPL thresholds. Midpoints of user-provided ranges.
# Breakpoints: (annual_magi, estimated_monthly_premium_midpoint)
_ACA_BREAKPOINTS = [
    (21000, 0),      # Medicaid/gap — no premium
    (25000, 168),    # ~$85–$250
    (35000, 270),    # ~$165–$375
    (45000, 438),    # ~$335–$540
    (55000, 625),    # ~$500–$750
    (65000, 790),    # ~$665–$915
    (75000, 918),    # ~$750–$1,085
    (84000, 1043),   # ~$835–$1,250
    (84600, 2325),   # >$84,600 — no subsidy, ~$2,000–$2,650
]

ACA_MEDICARE_AGE = 65.0


def get_aca_monthly_premium(annual_magi: float) -> float:
    """Estimate monthly ACA Gold plan premium based on annual household MAGI.

    ACA MAGI for marketplace purposes includes SS (gross), pension, traditional
    IRA/401k distributions, and Roth conversions. Cash and Roth withdrawals
    do not count toward ACA MAGI.
    """
    if annual_magi <= _ACA_BREAKPOINTS[0][0]:
        return 0.0
    if annual_magi >= _ACA_BREAKPOINTS[-1][0]:
        return float(_ACA_BREAKPOINTS[-1][1])
    for i in range(len(_ACA_BREAKPOINTS) - 1):
        m1, p1 = _ACA_BREAKPOINTS[i]
        m2, p2 = _ACA_BREAKPOINTS[i + 1]
        if m1 <= annual_magi <= m2:
            frac = (annual_magi - m1) / (m2 - m1)
            return p1 + frac * (p2 - p1)
    return float(_ACA_BREAKPOINTS[-1][1])
