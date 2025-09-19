from django import forms

class RetirementForm(forms.Form):
    MODE_CHOICES = [
        ("fixed", "Fixed Withdrawal → Evaluate Success"),
        ("target", "Target Success Rate → Find Withdrawal"),
    ]

    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        initial="target",
        widget=forms.RadioSelect,
        help_text="Choose whether to test a fixed withdrawal amount, or to find the maximum safe withdrawal for a target success rate."
    )

    current_age = forms.FloatField(
        label="Current Age",
        initial=65,
        help_text="Enter your current age (decimals allowed, e.g., 66.5)."
    )
    end_age = forms.FloatField(
        label="Planned End Age",
        initial=90,
        help_text="Life expectancy or horizon to plan for (typical range 85–100)."
    )
    balance = forms.FloatField(
        label="Portfolio Balance ($)",
        initial=1_000_000,
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
    target_success = forms.FloatField(
        label="Target Success Rate (0–1)",
        required=False,
        initial=0.9,
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