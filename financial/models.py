from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


def _default_withdrawal_order():
    return ['CASH', 'ROTH_IRA', 'ROTH_401K', 'TRADITIONAL_IRA', '401K', 'HSA', 'BROKERAGE', 'OTHER']


def _default_federal_brackets():
    return [
        [0, 0.10],
        [24800, 0.12],
        [100800, 0.22],
        [211400, 0.24],
        [403550, 0.32],
        [512450, 0.35],
        [768700, 0.37],
    ]


class PortfolioAccount(models.Model):
    """Represents an investment or savings account."""

    ACCOUNT_TYPE_CHOICES = [
        ('401K', '401(k)'),
        ('ROTH_401K', 'Roth 401(k)'),
        ('TRADITIONAL_IRA', 'Traditional IRA'),
        ('ROTH_IRA', 'Roth IRA'),
        ('BROKERAGE', 'Brokerage/Investment Account'),
        ('CASH', 'Cash/Savings Account'),
        ('HSA', 'Health Savings Account (HSA)'),
        ('OTHER', 'Other'),
    ]

    TAX_TREATMENT_CHOICES = [
        ('PRE_TAX', 'Pre-Tax (Traditional 401k/IRA) - Contributions reduce taxable income, withdrawals taxed as ordinary income'),
        ('ROTH', 'Roth (Roth 401k/IRA) - Post-tax contributions, tax-free qualified withdrawals'),
        ('PENSION', 'Pension/Lump Sum - Retirement fund that can be taken as lump sum or annuity, taxed as ordinary income'),
        ('TAXABLE', 'Taxable Brokerage - Subject to capital gains tax'),
        ('HSA', 'HSA - Triple tax advantaged (pre-tax contributions, tax-free growth, tax-free medical withdrawals)'),
        ('CASH', 'Cash/Savings - Interest taxed as ordinary income'),
    ]

    name = models.CharField(max_length=200, help_text="Account name (e.g., 'Fidelity 401k', 'Vanguard Roth IRA')")
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    institution = models.CharField(max_length=200, blank=True, help_text="Financial institution (e.g., 'Fidelity', 'Vanguard')")

    tax_treatment = models.CharField(
        max_length=20,
        choices=TAX_TREATMENT_CHOICES,
        default='PRE_TAX',
        help_text="Tax treatment of contributions and withdrawals"
    )

    # Keep is_taxable for backwards compatibility, but it will be derived from tax_treatment
    is_taxable = models.BooleanField(
        default=False,
        help_text="Automatically set based on tax treatment (read-only)"
    )

    is_active = models.BooleanField(default=True, help_text="Uncheck to hide this account from portfolio view")
    notes = models.TextField(blank=True, help_text="Optional notes about this account")

    annual_growth_rate = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal('0.0700'),
        help_text="Expected annual growth rate for forecasting (e.g., 0.07 for 7%)"
    )
    pension_benefit_age = models.IntegerField(
        null=True, blank=True,
        help_text="Age when pension benefits begin (pension accounts only)"
    )
    pension_monthly_benefit = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Monthly pension benefit in today's dollars (pension accounts only)"
    )
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['account_type', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()})"

    def save(self, *args, **kwargs):
        """Override save to automatically set is_taxable based on tax_treatment."""
        self.is_taxable = self.tax_treatment in ['TAXABLE', 'CASH']
        super().save(*args, **kwargs)

    def get_latest_balance(self):
        """Returns the most recent balance snapshot for this account."""
        latest = self.snapshots.order_by('-snapshot_date').first()
        return latest.balance if latest else 0

    def get_tax_treatment_display_short(self):
        """Returns a short display name for tax treatment."""
        tax_map = {
            'PRE_TAX': 'Pre-Tax',
            'ROTH': 'Roth',
            'PENSION': 'Pension',
            'TAXABLE': 'Taxable',
            'HSA': 'HSA',
            'CASH': 'Cash',
        }
        return tax_map.get(self.tax_treatment, self.tax_treatment)


class PortfolioSnapshot(models.Model):
    """Represents the balance of an account at a specific point in time."""

    account = models.ForeignKey(PortfolioAccount, on_delete=models.CASCADE, related_name='snapshots')
    snapshot_date = models.DateField(help_text="Date of this balance snapshot")
    balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Account balance on this date"
    )
    notes = models.TextField(blank=True, help_text="Optional notes about this snapshot")
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-snapshot_date', 'account__name']
        unique_together = ['account', 'snapshot_date']  # One balance per account per day

    def __str__(self):
        return f"{self.account.name} - {self.snapshot_date}: ${self.balance:,.2f}"


class ElectricityUsage(models.Model):
    """Represents monthly electricity usage and costs."""

    date = models.DateField(unique=True, help_text="First day of the month for this record")
    kwh_consumed = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Electricity consumed from grid (kWh)"
    )
    kwh_sent = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Electricity sent back to grid (kWh)"
    )
    net_kwh = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Net electricity from grid (kWh)"
    )
    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total bill cost ($)"
    )
    cost_per_kwh = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Cost per kWh ($/kWh)"
    )
    received_per_kwh = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Credit received per kWh sent ($/kWh)"
    )
    produced_kwh = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Solar electricity produced (kWh)"
    )
    kwh_combined = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total electricity used (grid + solar)"
    )
    percent_from_solar = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Percentage of usage from solar (%)"
    )
    savings = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Savings from solar production ($)"
    )
    credits = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Credits from excess solar production ($)"
    )
    savings_plus_credits = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total savings + credits ($)"
    )
    ev_mileage = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="EV mileage driven (miles)"
    )
    ev_miles_per_kwh = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="EV efficiency (miles/kWh)"
    )
    ev_usage_kwh = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Electricity used by EV (kWh)"
    )
    produced_minus_ev = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Solar production minus EV usage (kWh)"
    )
    net_bill_minus_credits = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Net bill after credits ($)"
    )
    comments = models.TextField(blank=True, help_text="Optional comments")
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        ZERO = Decimal('0')

        kwh = self.kwh_consumed
        sent = self.kwh_sent or ZERO
        total = self.total_cost
        recv = self.received_per_kwh
        produced = self.produced_kwh
        cred = self.credits
        ev_mi = self.ev_mileage
        ev_mpk = self.ev_miles_per_kwh

        self.net_kwh = (kwh - sent) if kwh is not None else None
        self.cost_per_kwh = (total / self.net_kwh) if (total is not None and self.net_kwh) else None
        self.kwh_combined = (kwh + produced) if (kwh is not None and produced is not None) else kwh
        self.percent_from_solar = (produced / self.kwh_combined) if (produced is not None and self.kwh_combined) else None
        self.savings = (recv * produced) if (recv is not None and produced is not None) else None
        self.savings_plus_credits = (
            (self.savings + cred) if (self.savings is not None and cred is not None)
            else self.savings
        )
        self.ev_usage_kwh = (ev_mi / ev_mpk) if (ev_mi is not None and ev_mpk and ev_mpk != ZERO) else None
        self.produced_minus_ev = (produced - self.ev_usage_kwh) if (produced is not None and self.ev_usage_kwh is not None) else None
        self.net_bill_minus_credits = (
            (total - cred) if (total is not None and cred is not None)
            else total
        )

        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-date']
        verbose_name = "Electricity Usage"
        verbose_name_plural = "Electricity Usage"

    def __str__(self):
        return f"{self.date.strftime('%B %Y')} - {self.net_kwh} kWh"


class NetWorth(models.Model):
    """Represents monthly net worth tracking."""

    date = models.DateField(unique=True, help_text="First day of the month for this record")
    net_worth = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Total net worth ($)"
    )
    change_from_previous = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Dollar change from previous month ($)"
    )
    percent_change = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Percent change from previous month (as decimal, e.g., 1.05 = 5% increase)"
    )
    comments = models.TextField(blank=True, help_text="Optional comments")
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name = "Net Worth"
        verbose_name_plural = "Net Worth"

    def __str__(self):
        return f"{self.date.strftime('%B %Y')} - ${self.net_worth:,.2f}"


class ForecastSettings(models.Model):
    """Singleton settings for the Portfolio Forecast page."""

    monthly_spending = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('5000.00'),
        help_text="Target monthly spending in today's dollars"
    )
    spending_inflation_rate = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal('0.0300'),
        help_text="Annual inflation rate applied to spending (e.g., 0.03)"
    )
    ss_monthly_benefit = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text="Expected Social Security monthly benefit in today's dollars"
    )
    ss_inflation_rate = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal('0.0200'),
        help_text="Annual COLA adjustment for Social Security (e.g., 0.02)"
    )
    ss_start_age = models.DecimalField(
        max_digits=4, decimal_places=1, default=Decimal('67.0'),
        help_text="Age to start receiving Social Security"
    )
    date_of_birth = models.DateField(
        null=True, blank=True,
        help_text="Your date of birth — current age is calculated dynamically"
    )
    max_age = models.IntegerField(default=95, help_text="Maximum age for forecast horizon")

    filing_status = models.CharField(
        max_length=10,
        choices=[('MFJ', 'Married Filing Jointly'), ('SINGLE', 'Single')],
        default='MFJ',
    )
    federal_standard_deduction = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('32200.00'),
        help_text="Standard deduction (2026 MFJ default: $32,200)"
    )
    federal_brackets = models.JSONField(
        default=_default_federal_brackets,
        help_text="List of [threshold, rate] pairs for federal income tax brackets (taxable income thresholds)"
    )
    pa_flat_rate = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal('0.0307'),
        help_text="Pennsylvania flat income tax rate (default 3.07%)"
    )
    pa_retirement_age = models.DecimalField(
        max_digits=4, decimal_places=1, default=Decimal('59.5'),
        help_text="Age at which PA exempts traditional IRA/401k withdrawals"
    )

    withdrawal_order = models.JSONField(
        default=_default_withdrawal_order,
        help_text="Ordered list of account type codes for portfolio withdrawals"
    )
    roth_conversions = models.JSONField(
        default=list,
        help_text='List of Roth conversion periods: [{"label":"...", "start_year":2026, "end_year":2030, "annual_amount":30000}]',
    )
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Forecast Settings"

    def __str__(self):
        return "Forecast Settings"
