from django import forms
from config.utils import get_config
from .models import PortfolioAccount, PortfolioSnapshot, ElectricityUsage, NetWorth

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


class PortfolioAccountForm(forms.ModelForm):
    """Form for creating and editing portfolio accounts."""

    class Meta:
        model = PortfolioAccount
        fields = ['name', 'account_type', 'institution', 'tax_treatment', 'is_active', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full'}),
            'account_type': forms.Select(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full'}),
            'institution': forms.TextInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full'}),
            'tax_treatment': forms.Select(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'bg-gray-700 text-white'}),
            'notes': forms.Textarea(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'rows': 3}),
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
            'date', 'kwh_consumed', 'kwh_sent', 'net_kwh', 'total_cost',
            'produced_kwh', 'kwh_combined', 'ev_mileage', 'comments'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'type': 'date'}),
            'kwh_consumed': forms.NumberInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'step': '0.01'}),
            'kwh_sent': forms.NumberInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'step': '0.01'}),
            'net_kwh': forms.NumberInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'step': '0.01'}),
            'total_cost': forms.NumberInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'step': '0.01'}),
            'produced_kwh': forms.NumberInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'step': '0.01'}),
            'kwh_combined': forms.NumberInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'step': '0.01'}),
            'ev_mileage': forms.NumberInput(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'step': '0.01'}),
            'comments': forms.Textarea(attrs={'class': 'bg-gray-700 text-white px-3 py-2 rounded w-full', 'rows': 2}),
        }
        labels = {
            'kwh_consumed': 'kWh Consumed',
            'kwh_sent': 'kWh Sent to Grid',
            'net_kwh': 'Net kWh',
            'total_cost': 'Total Cost ($)',
            'produced_kwh': 'Solar Produced (kWh)',
            'kwh_combined': 'Total Combined (kWh)',
            'ev_mileage': 'EV Mileage (miles)',
        }


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
