import json

from django import forms
from config.utils import get_config
from .models import PortfolioAccount, PortfolioSnapshot, ElectricityUsage, NetWorth, ForecastSettings

SS_BENEFITS_62 = get_config("SS_BENEFITS_62",0)
SS_BENEFITS_65 = get_config("SS_BENEFITS_65",0)
SS_BENEFITS_67 = get_config("SS_BENEFITS_67",0)
SS_BENEFITS_70 = get_config("SS_BENEFITS_70",0)
RETIREMENT_AGE = get_config("RETIREMENT_AGE",65)
PORTFOLIO_BALANCE = get_config("PORTFOLIO_BALANCE",1000000)
SS_AGE = get_config("SS_AGE", 67)

class RetirementForm(forms.Form):
    MODE_CHOICES = [
        ("target", "Target Success Rate → Find Withdrawal"),
        ("fixed", "Fixed Withdrawal → Evaluate Success"),
    ]

    SS_PRESETS = [
        ("", "Custom"),
        ("62", f"Age 62 - ${SS_BENEFITS_62}"),
        ("65", f"Age 65 - ${SS_BENEFITS_65}"),
        ("67", f"Age 67 - ${SS_BENEFITS_67}"),
        ("70", f"Age 70 - ${SS_BENEFITS_70}"),
    ]

    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        initial="target",
        widget=forms.RadioSelect,
        help_text="Choose whether to find the maximum safe withdrawal for a target success rate or test a fixed withdrawal amount."
    )

    current_age = forms.FloatField(
        label="Retirement Age",
        initial=RETIREMENT_AGE,
        help_text="Enter your current age (decimals allowed, e.g., 66.5)."
    )
    end_age = forms.FloatField(
        label="Life Expectancy",
        initial=95,
        help_text="Life expectancy or horizon to plan for (typical range 85–100)."
    )
    balance = forms.FloatField(
        label="Portfolio Balance ($)",
        initial=PORTFOLIO_BALANCE,
        help_text="Your total investable assets at retirement."
    )
    annual_return = forms.FloatField(
        label="Expected Annual Return (0–1)",
        initial=0.05,
        help_text="Expected long-term portfolio return BEFORE inflation. Common range: 0.04–0.07."
    )
    inflation = forms.FloatField(
        label="Expected Inflation (0–1)",
        initial=0.02,
        help_text="Expected annual inflation rate. Common range: 0.02–0.03."
    )
    annual_volatility = forms.FloatField(
        label="Volatility (Std Dev, 0–1)",
        initial=0.12,
        help_text="Standard deviation of annual returns. 0.10–0.20 is typical depending on your stock/bond mix."
    )

    n_simulations = forms.IntegerField(
        label="Monte Carlo Simulations",
        initial=1000,
        help_text="Number of scenarios to simulate. More simulations = smoother results but slower performance."
    )

    withdrawal_freq = forms.ChoiceField(
        label="Withdrawal Frequency",
        choices=[("monthly", "Monthly"), ("yearly", "Yearly")],
        initial="monthly",
        help_text="How often you withdraw money."
    )

    # Inputs depending on mode
    withdrawal = forms.FloatField(
        label="Withdrawal Amount ($)",
        required=False,
        help_text="(Fixed mode only) Enter a monthly or yearly withdrawal amount to test."
    )

    ss_preset = forms.ChoiceField(
        choices=SS_PRESETS,
        required=False,
        label="Social Security Preset",
        help_text="Choose a preset or leave blank for custom"
    )

    ss_age = forms.FloatField(
        label="Social Security Age",
        initial=SS_AGE,
        help_text="Age you plan to start receiving Social Security."
    )

    ss_benefits = forms.FloatField(
        label="Social Security Monthly Benefits ($)",
        initial=SS_BENEFITS_67,
        help_text="Expected monthly benefits (combined with spouse if needed)."
    )

    target_success = forms.FloatField(
        label="Target Success Rate (0–1)",
        required=False,
        initial=0.90,
        help_text="(Target mode only) Desired probability of not running out of money. Typical range: 0.75–0.95."
    )

    def clean(self):
            cleaned_data = super().clean()
            mode = cleaned_data.get("mode")
            withdrawal = cleaned_data.get("withdrawal")
            target_success = cleaned_data.get("target_success")

            if mode == "fixed" and withdrawal in [None, ""]:
                self.add_error("withdrawal", "Withdrawal amount is required when using Fixed Withdrawal mode.")
            elif mode == "target" and target_success in [None, ""]:
                self.add_error("target_success", "Target success rate is required when using Target Success mode.")


INPUT_CLASS = 'bg-gray-700 text-white px-3 py-2 rounded w-full'


class PortfolioAccountForm(forms.ModelForm):
    """Form for creating and editing portfolio accounts."""

    class Meta:
        model = PortfolioAccount
        fields = [
            'name', 'account_type', 'institution', 'tax_treatment',
            'annual_growth_rate', 'pension_benefit_age', 'pension_monthly_benefit',
            'is_active', 'notes',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'account_type': forms.Select(attrs={'class': INPUT_CLASS}),
            'institution': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'tax_treatment': forms.Select(attrs={'class': INPUT_CLASS, 'id': 'id_tax_treatment'}),
            'annual_growth_rate': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.0001'}),
            'pension_benefit_age': forms.NumberInput(attrs={'class': INPUT_CLASS}),
            'pension_monthly_benefit': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'bg-gray-700 text-white'}),
            'notes': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 3}),
        }
        labels = {
            'annual_growth_rate': 'Annual Growth Rate (e.g., 0.07 for 7%)',
            'pension_benefit_age': 'Pension Benefit Start Age',
            'pension_monthly_benefit': 'Monthly Pension Benefit ($)',
        }


class PortfolioSnapshotForm(forms.ModelForm):
    """Form for adding balance snapshots."""

    class Meta:
        model = PortfolioSnapshot
        fields = ['account', 'snapshot_date', 'balance', 'notes']
        widgets = {
            'account': forms.Select(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full'}),
            'snapshot_date': forms.DateInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'type': 'date'}),
            'balance': forms.NumberInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'rows': 2}),
        }


class ElectricityUsageForm(forms.ModelForm):
    """Form for adding electricity usage records."""

    class Meta:
        model = ElectricityUsage
        fields = [
            'date', 'kwh_consumed', 'kwh_sent', 'total_cost',
            'received_per_kwh', 'produced_kwh', 'credits',
            'ev_mileage', 'ev_miles_per_kwh', 'comments',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'type': 'date'}),
            'kwh_consumed': forms.NumberInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'step': '0.01'}),
            'kwh_sent': forms.NumberInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'step': '0.01'}),
            'total_cost': forms.NumberInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'step': '0.01'}),
            'received_per_kwh': forms.NumberInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'step': '0.000001'}),
            'produced_kwh': forms.NumberInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'step': '0.01'}),
            'credits': forms.NumberInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'step': '0.01'}),
            'ev_mileage': forms.NumberInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'step': '0.01'}),
            'ev_miles_per_kwh': forms.NumberInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'step': '0.01'}),
            'comments': forms.Textarea(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'rows': 2}),
        }
        labels = {
            'kwh_consumed': 'KwH',
            'kwh_sent': 'Sent',
            'total_cost': 'Total Cost ($)',
            'received_per_kwh': 'Cost Received/KwH ($/kWh)',
            'produced_kwh': 'Produced KwH',
            'credits': 'Credits ($)',
            'ev_mileage': 'EV Mileage (miles)',
            'ev_miles_per_kwh': 'EV M/KwH',
        }

    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date:
            return date.replace(day=1)
        return date


class NetWorthForm(forms.ModelForm):
    """Form for adding net worth records."""

    class Meta:
        model = NetWorth
        fields = ['date', 'net_worth', 'comments']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'type': 'date'}),
            'net_worth': forms.NumberInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'step': '0.01'}),
            'comments': forms.Textarea(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'rows': 2}),
        }
        labels = {
            'net_worth': 'Net Worth ($)',
        }


class ForecastSettingsForm(forms.ModelForm):
    """Form for portfolio forecast parameters."""

    federal_brackets = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full font-mono text-xs',
            'rows': 9,
        }),
        label='Federal Tax Brackets (JSON)',
        help_text='List of [threshold, rate] pairs — taxable income thresholds after standard deduction',
    )

    class Meta:
        model = ForecastSettings
        fields = [
            'date_of_birth', 'max_age',
            'monthly_spending', 'spending_inflation_rate',
            'ss_monthly_benefit', 'ss_inflation_rate', 'ss_start_age',
            'filing_status', 'federal_standard_deduction',
            'pa_flat_rate', 'pa_retirement_age',
            'federal_brackets',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
            'max_age': forms.NumberInput(attrs={'class': INPUT_CLASS}),
            'monthly_spending': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '1'}),
            'spending_inflation_rate': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.001'}),
            'ss_monthly_benefit': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '1'}),
            'ss_inflation_rate': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.001'}),
            'ss_start_age': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.5'}),
            'filing_status': forms.Select(attrs={'class': INPUT_CLASS}),
            'federal_standard_deduction': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '100'}),
            'pa_flat_rate': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.0001'}),
            'pa_retirement_age': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.5'}),
        }
        labels = {
            'date_of_birth': 'Date of Birth',
            'max_age': 'Maximum Age (forecast horizon)',
            'monthly_spending': 'Monthly Spending Today ($)',
            'spending_inflation_rate': 'Spending Inflation Rate (e.g., 0.03)',
            'ss_monthly_benefit': 'Social Security Monthly Benefit Today ($)',
            'ss_inflation_rate': 'SS COLA Rate (e.g., 0.02)',
            'ss_start_age': 'Social Security Start Age',
            'filing_status': 'Filing Status',
            'federal_standard_deduction': 'Federal Standard Deduction ($)',
            'pa_flat_rate': 'PA Flat Tax Rate (e.g., 0.0307)',
            'pa_retirement_age': 'PA Retirement Age for IRA/401k Exemption',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if instance and instance.federal_brackets:
            self.fields['federal_brackets'].initial = json.dumps(instance.federal_brackets, indent=2)

    def clean_federal_brackets(self):
        value = self.cleaned_data.get('federal_brackets', '')
        if isinstance(value, list):
            return value
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            raise forms.ValidationError('Invalid JSON — must be a list like [[0, 0.10], [24800, 0.12], ...]')
        if not isinstance(parsed, list) or not all(
            isinstance(b, (list, tuple)) and len(b) == 2
            and isinstance(b[0], (int, float)) and isinstance(b[1], (int, float))
            for b in parsed
        ):
            raise forms.ValidationError('Each entry must be a [threshold, rate] pair of numbers')
        return parsed
