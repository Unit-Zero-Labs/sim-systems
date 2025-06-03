"""
Voted-Escrow (VE) Token Emissions Model
Handles step-based emissions tied to protocol KPIs (TVL, utilization, borrowing)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import streamlit as st


class EmissionTrigger(Enum):
    """Types of triggers that can activate emission step-ups."""
    TVL_GROWTH = "tvl_growth"
    UTILIZATION_RATE = "utilization_rate"
    BORROW_VOLUME = "borrow_volume"
    REVENUE_THRESHOLD = "revenue_threshold"
    TIME_BASED = "time_based"


@dataclass
class EmissionStep:
    """Definition of an emission step with trigger conditions."""
    step_number: int
    trigger_type: EmissionTrigger
    trigger_value: float
    emission_rate_multiplier: float
    base_emission_amount: float
    duration_months: int = 3  # Default 3-month cycles


@dataclass
class VEEmissionsConfig:
    """Configuration for Voted-Escrow emissions model."""
    total_emissions_budget: float
    base_monthly_rate: float
    base_weekly_rate: float
    borrowed_step_size: float
    emissions_step_up: float
    target_utilization_rate: float
    
    # Protocol metrics
    initial_tvl: float
    final_tvl: float
    initial_borrow: float
    final_borrow: float
    
    # Revenue sharing
    lender_share: float
    protocol_fee: float
    admin_fee: float
    reserve_fee: float
    liquidation_fee: float
    ve_token_fee: float
    
    # Growth assumptions
    monthly_tvl_growth: float
    monthly_borrow_growth: float
    token_price: float


class VEEmissionsModel:
    """
    Voted-Escrow Token Emissions Model
    Calculates emissions based on protocol KPIs and step-based triggers
    """
    
    def __init__(self, config: VEEmissionsConfig):
        self.config = config
        self.emission_steps: List[EmissionStep] = []
        self.time_series_data: Optional[pd.DataFrame] = None
        self.setup_emission_steps()
    
    def setup_emission_steps(self) -> None:
        """Setup emission steps based on configuration."""
        # Calculate step thresholds based on growth assumptions
        borrowing_steps = self._calculate_borrowing_steps()
        
        for i, threshold in enumerate(borrowing_steps):
            step = EmissionStep(
                step_number=i,
                trigger_type=EmissionTrigger.BORROW_VOLUME,
                trigger_value=threshold,
                emission_rate_multiplier=1 + (i * self.config.emissions_step_up),
                base_emission_amount=self.config.total_emissions_budget * self.config.base_monthly_rate,
                duration_months=3
            )
            self.emission_steps.append(step)
    
    def _calculate_borrowing_steps(self) -> List[float]:
        """Calculate borrowing volume thresholds for emission steps."""
        steps = []
        current_borrow = self.config.initial_borrow
        
        while current_borrow < self.config.final_borrow:
            steps.append(current_borrow)
            current_borrow *= (1 + self.config.borrowed_step_size)
        
        return steps
    
    def generate_time_series(self, months: int = 120) -> pd.DataFrame:
        """Generate time series data for emissions model."""
        dates = pd.date_range(start='2024-07-01', periods=months, freq='M')
        
        # Initialize arrays
        tvl_values = np.zeros(months)
        borrow_values = np.zeros(months)
        utilization_rates = np.zeros(months)
        emission_steps = np.zeros(months)
        emissions_per_month = np.zeros(months)
        cumulative_emissions = np.zeros(months)
        protocol_revenue = np.zeros(months)
        revenue_to_emissions_ratio = np.zeros(months)
        
        # Calculate progressive values
        for i in range(months):
            # TVL progression
            if i == 0:
                tvl_values[i] = self.config.initial_tvl
                borrow_values[i] = self.config.initial_borrow
            else:
                # Growth with caps
                if tvl_values[i-1] < self.config.final_tvl:
                    tvl_values[i] = min(
                        tvl_values[i-1] * (1 + self.config.monthly_tvl_growth),
                        self.config.final_tvl
                    )
                else:
                    tvl_values[i] = self.config.final_tvl
                
                if borrow_values[i-1] < self.config.final_borrow:
                    borrow_values[i] = min(
                        borrow_values[i-1] * (1 + self.config.monthly_borrow_growth),
                        self.config.final_borrow
                    )
                else:
                    borrow_values[i] = self.config.final_borrow
            
            # Utilization rate
            utilization_rates[i] = borrow_values[i] / tvl_values[i] if tvl_values[i] > 0 else 0
            
            # Determine emission step
            current_step = self._get_emission_step(borrow_values[i], i)
            emission_steps[i] = current_step
            
            # Calculate emissions for this month
            if current_step < len(self.emission_steps):
                step_config = self.emission_steps[int(current_step)]
                emissions_per_month[i] = step_config.base_emission_amount * step_config.emission_rate_multiplier
            else:
                emissions_per_month[i] = 0  # Emissions ended
            
            # Cumulative emissions
            cumulative_emissions[i] = np.sum(emissions_per_month[:i+1])
            
            # Cap cumulative emissions at budget
            if cumulative_emissions[i] > self.config.total_emissions_budget:
                excess = cumulative_emissions[i] - self.config.total_emissions_budget
                emissions_per_month[i] = max(0, emissions_per_month[i] - excess)
                cumulative_emissions[i] = self.config.total_emissions_budget
            
            # Protocol revenue calculation
            borrow_apr = self._calculate_borrow_apr(utilization_rates[i])
            monthly_interest = borrow_values[i] * (borrow_apr / 12)
            protocol_revenue[i] = monthly_interest * self.config.protocol_fee
            
            # Revenue to emissions ratio
            emissions_cost = emissions_per_month[i] * self.config.token_price
            if emissions_cost > 0:
                revenue_to_emissions_ratio[i] = protocol_revenue[i] / emissions_cost
            else:
                revenue_to_emissions_ratio[i] = float('inf')
        
        # Create DataFrame
        self.time_series_data = pd.DataFrame({
            'month': range(months),
            'date': dates,
            'tvl': tvl_values,
            'borrow_amount': borrow_values,
            'utilization_rate': utilization_rates,
            'emission_step': emission_steps,
            'emissions_per_month': emissions_per_month,
            'cumulative_emissions': cumulative_emissions,
            'protocol_revenue': protocol_revenue,
            'revenue_to_emissions_ratio': revenue_to_emissions_ratio,
            'emission_margin': 1 - (1 / revenue_to_emissions_ratio),
            'emissions_cost_usd': emissions_per_month * self.config.token_price
        })
        
        return self.time_series_data
    
    def _get_emission_step(self, current_borrow: float, month: int) -> int:
        """Determine which emission step should be active."""
        # Find the appropriate step based on borrowing threshold
        for i, step in enumerate(self.emission_steps):
            if current_borrow >= step.trigger_value:
                continue
            else:
                return max(0, i - 1)
        return len(self.emission_steps) - 1
    
    def _calculate_borrow_apr(self, utilization_rate: float) -> float:
        """Calculate borrowing APR based on utilization rate using interest rate model."""
        # Simple interest rate model (can be enhanced)
        base_rate = 0.02  # 2% base
        multiplier = 0.15  # 15% multiplier
        kink = self.config.target_utilization_rate
        jump_multiplier = 2.0
        
        if utilization_rate <= kink:
            return base_rate + (utilization_rate * multiplier)
        else:
            excess_utilization = utilization_rate - kink
            return base_rate + (kink * multiplier) + (excess_utilization * jump_multiplier)
    
    def run_monte_carlo_simulation(
        self, 
        num_runs: int = 100,
        uncertainty_params: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation with parameter uncertainty.
        
        Args:
            num_runs: Number of simulation runs
            uncertainty_params: Dictionary of parameter names and their uncertainty ranges (as percentages)
        """
        if uncertainty_params is None:
            uncertainty_params = {
                'monthly_tvl_growth': 0.20,  # ±20% uncertainty
                'monthly_borrow_growth': 0.25,  # ±25% uncertainty
                'token_price': 0.30,  # ±30% uncertainty
                'protocol_fee': 0.10  # ±10% uncertainty
            }
        
        # Store original config
        original_config = self.config
        
        # Arrays to store results from all runs
        all_results = []
        
        for run in range(num_runs):
            # Create perturbed config
            perturbed_config = self._create_perturbed_config(original_config, uncertainty_params)
            
            # Temporarily update config
            self.config = perturbed_config
            self.setup_emission_steps()  # Recalculate steps with new config
            
            # Generate time series for this run
            result_df = self.generate_time_series()
            result_df['run'] = run
            all_results.append(result_df)
        
        # Restore original config
        self.config = original_config
        self.setup_emission_steps()
        
        # Combine all results
        combined_df = pd.concat(all_results, ignore_index=True)
        
        # Calculate statistics
        variables = ['tvl', 'borrow_amount', 'utilization_rate', 'emissions_per_month',
                    'cumulative_emissions', 'protocol_revenue', 'revenue_to_emissions_ratio']
        
        mc_results = {
            'raw_data': combined_df,
            'mean': {},
            'std_dev': {},
            'conf_intervals': {},
            'percentiles': {}
        }
        
        months = sorted(combined_df['month'].unique())
        
        for var in variables:
            # Initialize storage for this variable
            mean_values = []
            std_values = []
            conf_lower = []
            conf_upper = []
            percentile_values = []
            
            for month in months:
                month_data = combined_df[combined_df['month'] == month][var]
                
                if len(month_data) > 0:
                    mean_val = month_data.mean()
                    std_val = month_data.std()
                    
                    # Calculate confidence interval
                    conf_interval = 1.96 * std_val / np.sqrt(num_runs) if num_runs > 0 else 0
                    
                    # Calculate percentiles
                    percentiles = month_data.quantile([0.05, 0.25, 0.5, 0.75, 0.95]).values
                    
                    mean_values.append(mean_val)
                    std_values.append(std_val)
                    conf_lower.append(mean_val - conf_interval)
                    conf_upper.append(mean_val + conf_interval)
                    percentile_values.append(percentiles)
                else:
                    # Handle missing data
                    mean_values.append(0)
                    std_values.append(0)
                    conf_lower.append(0)
                    conf_upper.append(0)
                    percentile_values.append([0, 0, 0, 0, 0])
            
            # Store as pandas Series indexed by month
            mc_results['mean'][var] = pd.Series(mean_values, index=months)
            mc_results['std_dev'][var] = pd.Series(std_values, index=months)
            
            # Store confidence intervals as DataFrame with lower/upper columns
            mc_results['conf_intervals'][var] = pd.DataFrame({
                'lower': conf_lower,
                'upper': conf_upper
            }, index=months)
            
            # Store percentiles as DataFrame
            percentile_df = pd.DataFrame(
                percentile_values,
                index=months,
                columns=[5, 25, 50, 75, 95]
            )
            mc_results['percentiles'][var] = percentile_df
        
        return mc_results
    
    def _create_perturbed_config(
        self, 
        base_config: VEEmissionsConfig, 
        uncertainty_params: Dict[str, float]
    ) -> VEEmissionsConfig:
        """Create a perturbed configuration for Monte Carlo simulation."""
        perturbed_config = VEEmissionsConfig(
            total_emissions_budget=base_config.total_emissions_budget,
            base_monthly_rate=base_config.base_monthly_rate,
            base_weekly_rate=base_config.base_weekly_rate,
            borrowed_step_size=base_config.borrowed_step_size,
            emissions_step_up=base_config.emissions_step_up,
            target_utilization_rate=base_config.target_utilization_rate,
            initial_tvl=base_config.initial_tvl,
            final_tvl=base_config.final_tvl,
            initial_borrow=base_config.initial_borrow,
            final_borrow=base_config.final_borrow,
            lender_share=base_config.lender_share,
            protocol_fee=base_config.protocol_fee,
            admin_fee=base_config.admin_fee,
            reserve_fee=base_config.reserve_fee,
            liquidation_fee=base_config.liquidation_fee,
            ve_token_fee=base_config.ve_token_fee,
            monthly_tvl_growth=base_config.monthly_tvl_growth,
            monthly_borrow_growth=base_config.monthly_borrow_growth,
            token_price=base_config.token_price
        )
        
        # Apply random perturbations
        for param, uncertainty in uncertainty_params.items():
            if hasattr(perturbed_config, param):
                current_value = getattr(perturbed_config, param)
                # Generate random factor between (1 - uncertainty) and (1 + uncertainty)
                random_factor = np.random.uniform(1 - uncertainty, 1 + uncertainty)
                new_value = current_value * random_factor
                setattr(perturbed_config, param, new_value)
        
        return perturbed_config


def create_ve_emissions_config_from_params(params: Dict[str, Any]) -> VEEmissionsConfig:
    """Create VE emissions configuration from parameter registry parameters."""
    return VEEmissionsConfig(
        total_emissions_budget=params.get('total_ion_emitted', 300_000_000),
        base_monthly_rate=params.get('base_monthly_emissions_rate', 0.01),
        base_weekly_rate=params.get('base_weekly_emissions_rate', 0.0025),
        borrowed_step_size=params.get('borrowed_step_size', 0.15),
        emissions_step_up=params.get('emissions_step_up', 0.10),
        target_utilization_rate=params.get('target_utilization_rate', 0.40),
        initial_tvl=params.get('tvl', 150_000_000),
        final_tvl=params.get('final_tvl', 1_000_000_000),
        initial_borrow=params.get('borrow', 40_000_000),
        final_borrow=params.get('final_borrowed', 400_000_000),
        lender_share=params.get('lender', 0.70),
        protocol_fee=params.get('protocol_fee', 0.20),
        admin_fee=params.get('admin_fee', 0.00),
        reserve_fee=params.get('reserve_fee', 0.00),
        liquidation_fee=params.get('liquidation_fee', 0.10),
        ve_token_fee=params.get('vetoken_fee', 0.10),
        monthly_tvl_growth=params.get('mom_tvl_growth', 0.05),
        monthly_borrow_growth=params.get('mom_borrow_growth', 0.05),
        token_price=params.get('token_price', 0.05)
    ) 