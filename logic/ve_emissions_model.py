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
from scipy.optimize import minimize_scalar, minimize, differential_evolution
import warnings
warnings.filterwarnings('ignore')


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
class EmissionScenario:
    """Represents a single emissions scenario for comparison."""
    name: str
    base_monthly_rate: float
    emissions_step_up: float
    target_ratio: float
    description: str = ""


@dataclass
class OptimizationTarget:
    """Target constraints for emissions optimization."""
    min_revenue_ratio: float = 1.0  # Minimum revenue/emissions ratio
    target_revenue_ratio: float = 2.0  # Target revenue/emissions ratio
    max_emissions_budget_pct: float = 0.8  # Max % of budget to use
    min_emission_duration_months: int = 24  # Minimum emission duration
    max_emission_duration_months: int = 60  # Maximum emission duration


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
        # Clear any existing emission steps
        self.emission_steps = []
        
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
            prev_cumulative = cumulative_emissions[i-1] if i > 0 else 0
            if current_step < len(self.emission_steps) and prev_cumulative < self.config.total_emissions_budget:
                step_config = self.emission_steps[int(current_step)]
                proposed_emissions = step_config.base_emission_amount * step_config.emission_rate_multiplier
                
                # Ensure minimum viable emissions (avoid division by zero scenarios)
                proposed_emissions = max(proposed_emissions, 1.0)  # At least 1 token per month
                
                # Check if this would exceed the budget
                if prev_cumulative + proposed_emissions > self.config.total_emissions_budget:
                    # Calculate remaining budget and distribute more gradually
                    remaining_budget = self.config.total_emissions_budget - prev_cumulative
                    remaining_months = max(1, months - i)  # At least 1 month
                    # Use the smaller of: remaining budget per month or proposed emissions
                    emissions_per_month[i] = max(1.0, min(proposed_emissions, remaining_budget / remaining_months))
                else:
                    emissions_per_month[i] = proposed_emissions
            else:
                # Either no more steps or budget exhausted
                if prev_cumulative < self.config.total_emissions_budget:
                    # Still have budget, distribute remaining evenly
                    remaining_budget = self.config.total_emissions_budget - prev_cumulative
                    remaining_months = max(1, months - i)
                    emissions_per_month[i] = max(1.0, remaining_budget / remaining_months)
                else:
                    emissions_per_month[i] = 0  # Budget exhausted
            
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
                # When emissions are 0, handle ratio calculation more sensibly
                if protocol_revenue[i] > 0:
                    # If there's revenue but no emissions cost, this is highly profitable
                    # Use a large but finite number instead of infinity
                    revenue_to_emissions_ratio[i] = 1000.0  # Very high ratio but finite
                else:
                    # No revenue and no emissions cost
                    revenue_to_emissions_ratio[i] = 0.0
        
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
                'protocol_fee': 0.10,  # ±10% uncertainty
                'total_emissions_budget': 0.15,  # ±15% uncertainty in emissions budget
                'base_monthly_rate': 0.20,  # ±20% uncertainty in emission rate
                'emissions_step_up': 0.25  # ±25% uncertainty in step-up rate
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
                    # Handle special cases for revenue_to_emissions_ratio
                    if var == 'revenue_to_emissions_ratio':
                        # Filter out extreme values for more robust statistics
                        filtered_data = month_data[(month_data >= 0) & (month_data <= 1000)]
                        if len(filtered_data) == 0:
                            filtered_data = month_data  # Fall back to original if all filtered out
                        
                        mean_val = filtered_data.mean()
                        std_val = filtered_data.std()
                        
                        # Use more robust percentile calculation
                        try:
                            percentiles = filtered_data.quantile([0.05, 0.25, 0.5, 0.75, 0.95]).values
                        except:
                            percentiles = np.array([mean_val] * 5)
                    else:
                        mean_val = month_data.mean()
                        std_val = month_data.std()
                        
                        # Calculate percentiles
                        try:
                            percentiles = month_data.quantile([0.05, 0.25, 0.5, 0.75, 0.95]).values
                        except:
                            percentiles = np.array([mean_val] * 5)
                    
                    # Handle NaN/inf values
                    if np.isnan(mean_val) or np.isinf(mean_val):
                        mean_val = 0.0
                    if np.isnan(std_val) or np.isinf(std_val):
                        std_val = 0.0
                    
                    # Calculate confidence interval
                    conf_interval = 1.96 * std_val / np.sqrt(num_runs) if num_runs > 0 and std_val > 0 else 0
                    
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
        
        # Apply random perturbations with bounds checking
        for param, uncertainty in uncertainty_params.items():
            if hasattr(perturbed_config, param):
                current_value = getattr(perturbed_config, param)
                # Generate random factor between (1 - uncertainty) and (1 + uncertainty)
                random_factor = np.random.uniform(1 - uncertainty, 1 + uncertainty)
                new_value = current_value * random_factor
                
                # Apply parameter-specific bounds
                if param in ['monthly_tvl_growth', 'monthly_borrow_growth']:
                    # Growth rates should stay positive and reasonable
                    new_value = max(0.001, min(new_value, 0.5))  # Between 0.1% and 50%
                elif param == 'protocol_fee':
                    # Protocol fee should stay between 5% and 50%
                    new_value = max(0.05, min(new_value, 0.50))
                elif param == 'token_price':
                    # Token price should stay positive
                    new_value = max(0.001, new_value)
                elif param == 'base_monthly_rate':
                    # Base emission rate should stay positive and reasonable
                    new_value = max(0.001, min(new_value, 0.1))  # Between 0.1% and 10%
                elif param == 'emissions_step_up':
                    # Step-up rate should stay positive and reasonable
                    new_value = max(0.01, min(new_value, 1.0))  # Between 1% and 100%
                elif param == 'total_emissions_budget':
                    # Emissions budget should stay positive
                    new_value = max(100_000, new_value)  # At least 100K tokens
                elif param == 'target_utilization_rate':
                    # Utilization rate should stay between 10% and 90%
                    new_value = max(0.1, min(new_value, 0.9))
                
                setattr(perturbed_config, param, new_value)
        
        # Update weekly rate to match monthly rate
        perturbed_config.base_weekly_rate = perturbed_config.base_monthly_rate / 4
        
        return perturbed_config
    
    def optimize_emissions_rate(
        self,
        target: OptimizationTarget,
        months: int = 120,
        method: str = 'differential_evolution'
    ) -> Dict[str, Any]:
        """
        Optimize emissions rate to meet target revenue/emissions ratio.
        
        Args:
            target: Optimization target constraints
            months: Time horizon for optimization
            method: Optimization method ('differential_evolution', 'minimize', 'grid_search')
            
        Returns:
            Dictionary with optimization results
        """
        original_config = self.config
        
        def objective_function(params):
            """Objective function to minimize: distance from target ratio."""
            try:
                base_rate, step_up = params if isinstance(params, (list, tuple, np.ndarray)) else (params, self.config.emissions_step_up)
                
                # Update config with new parameters
                new_config = VEEmissionsConfig(
                    total_emissions_budget=original_config.total_emissions_budget,
                    base_monthly_rate=float(base_rate),
                    base_weekly_rate=float(base_rate) / 4,
                    borrowed_step_size=original_config.borrowed_step_size,
                    emissions_step_up=float(step_up),
                    target_utilization_rate=original_config.target_utilization_rate,
                    initial_tvl=original_config.initial_tvl,
                    final_tvl=original_config.final_tvl,
                    initial_borrow=original_config.initial_borrow,
                    final_borrow=original_config.final_borrow,
                    lender_share=original_config.lender_share,
                    protocol_fee=original_config.protocol_fee,
                    admin_fee=original_config.admin_fee,
                    reserve_fee=original_config.reserve_fee,
                    liquidation_fee=original_config.liquidation_fee,
                    ve_token_fee=original_config.ve_token_fee,
                    monthly_tvl_growth=original_config.monthly_tvl_growth,
                    monthly_borrow_growth=original_config.monthly_borrow_growth,
                    token_price=original_config.token_price
                )
                
                # Temporarily update model config
                self.config = new_config
                self.setup_emission_steps()
                
                # Generate time series
                ts_data = self.generate_time_series(months)
                
                # Calculate key metrics
                # Filter out extreme ratios for robust optimization
                valid_ratios = ts_data['revenue_to_emissions_ratio'][
                    (ts_data['revenue_to_emissions_ratio'] >= 0) & 
                    (ts_data['revenue_to_emissions_ratio'] <= 1000)
                ]
                
                if len(valid_ratios) == 0:
                    return 1000.0  # Penalty for invalid scenarios
                
                avg_ratio = valid_ratios.mean()
                min_ratio = valid_ratios.min()
                
                # Check constraints
                budget_used_pct = ts_data.iloc[-1]['cumulative_emissions'] / original_config.total_emissions_budget
                emission_months = len(ts_data[ts_data['emissions_per_month'] > 0])
                
                # Penalty system
                penalty = 0
                
                # Revenue ratio constraints
                if min_ratio < target.min_revenue_ratio:
                    penalty += (target.min_revenue_ratio - min_ratio) * 10
                
                # Budget constraint
                if budget_used_pct > target.max_emissions_budget_pct:
                    penalty += (budget_used_pct - target.max_emissions_budget_pct) * 50
                
                # Duration constraints
                if emission_months < target.min_emission_duration_months:
                    penalty += (target.min_emission_duration_months - emission_months) * 0.5
                elif emission_months > target.max_emission_duration_months:
                    penalty += (emission_months - target.max_emission_duration_months) * 0.5
                
                # Primary objective: minimize distance from target ratio
                distance_from_target = abs(avg_ratio - target.target_revenue_ratio)
                
                return distance_from_target + penalty
                
            except Exception as e:
                return 1000.0  # Penalty for failed simulations
        
        # Run optimization based on method
        try:
            if method == 'differential_evolution':
                # Optimize both base_rate and step_up
                bounds = [(0.0001, 0.02), (0.01, 0.5)]  # (base_rate, step_up)
                result = differential_evolution(
                    objective_function,
                    bounds,
                    seed=42,
                    maxiter=50,
                    atol=1e-6
                )
                optimal_base_rate = result.x[0]
                optimal_step_up = result.x[1]
                success = result.success
                
            elif method == 'grid_search':
                # Grid search for more interpretable results
                base_rates = np.linspace(0.0001, 0.02, 20)
                step_ups = np.linspace(0.01, 0.5, 18)
                
                best_score = float('inf')
                optimal_base_rate = None
                optimal_step_up = None
                
                for base_rate in base_rates:
                    for step_up in step_ups:
                        score = objective_function([base_rate, step_up])
                        if score < best_score:
                            best_score = score
                            optimal_base_rate = base_rate
                            optimal_step_up = step_up
                
                success = optimal_base_rate is not None
                
            else:  # minimize (single parameter)
                # Only optimize base_rate, keep step_up fixed
                result = minimize_scalar(
                    lambda x: objective_function([x, original_config.emissions_step_up]),
                    bounds=(0.0001, 0.02),
                    method='bounded'
                )
                optimal_base_rate = result.x
                optimal_step_up = original_config.emissions_step_up
                success = result.success
            
            # Generate final results with optimal parameters
            optimal_config = VEEmissionsConfig(
                total_emissions_budget=original_config.total_emissions_budget,
                base_monthly_rate=optimal_base_rate,
                base_weekly_rate=optimal_base_rate / 4,
                borrowed_step_size=original_config.borrowed_step_size,
                emissions_step_up=optimal_step_up,
                target_utilization_rate=original_config.target_utilization_rate,
                initial_tvl=original_config.initial_tvl,
                final_tvl=original_config.final_tvl,
                initial_borrow=original_config.initial_borrow,
                final_borrow=original_config.final_borrow,
                lender_share=original_config.lender_share,
                protocol_fee=original_config.protocol_fee,
                admin_fee=original_config.admin_fee,
                reserve_fee=original_config.reserve_fee,
                liquidation_fee=original_config.liquidation_fee,
                ve_token_fee=original_config.ve_token_fee,
                monthly_tvl_growth=original_config.monthly_tvl_growth,
                monthly_borrow_growth=original_config.monthly_borrow_growth,
                token_price=original_config.token_price
            )
            
            # Generate final time series with optimal config
            self.config = optimal_config
            self.setup_emission_steps()
            optimal_ts = self.generate_time_series(months)
            
            # Calculate final metrics
            valid_ratios = optimal_ts['revenue_to_emissions_ratio'][
                (optimal_ts['revenue_to_emissions_ratio'] >= 0) & 
                (optimal_ts['revenue_to_emissions_ratio'] <= 1000)
            ]
            
            if len(valid_ratios) > 0:
                final_avg_ratio = valid_ratios.mean()
                final_min_ratio = valid_ratios.min()
                final_max_ratio = valid_ratios.max()
            else:
                final_avg_ratio = 0
                final_min_ratio = 0
                final_max_ratio = 0
            
            budget_used_pct = optimal_ts.iloc[-1]['cumulative_emissions'] / original_config.total_emissions_budget
            emission_months = len(optimal_ts[optimal_ts['emissions_per_month'] > 0])
            
            optimization_results = {
                'success': success,
                'optimal_base_rate': optimal_base_rate,
                'optimal_step_up': optimal_step_up,
                'optimal_config': optimal_config,
                'optimal_time_series': optimal_ts,
                'final_avg_ratio': final_avg_ratio,
                'final_min_ratio': final_min_ratio,
                'final_max_ratio': final_max_ratio,
                'budget_used_pct': budget_used_pct,
                'emission_duration_months': emission_months,
                'target_achievement': {
                    'target_ratio': target.target_revenue_ratio,
                    'achieved_ratio': final_avg_ratio,
                    'ratio_error': abs(final_avg_ratio - target.target_revenue_ratio),
                    'min_ratio_met': final_min_ratio >= target.min_revenue_ratio,
                    'budget_constraint_met': budget_used_pct <= target.max_emissions_budget_pct,
                    'duration_constraint_met': target.min_emission_duration_months <= emission_months <= target.max_emission_duration_months
                }
            }
            
        except Exception as e:
            optimization_results = {
                'success': False,
                'error': str(e),
                'optimal_base_rate': original_config.base_monthly_rate,
                'optimal_step_up': original_config.emissions_step_up,
                'optimal_config': original_config
            }
        
        finally:
            # Restore original config
            self.config = original_config
            self.setup_emission_steps()
        
        return optimization_results
    
    def compare_emission_scenarios(
        self,
        scenarios: List[EmissionScenario],
        months: int = 120
    ) -> Dict[str, Any]:
        """
        Compare multiple emission scenarios side-by-side.
        
        Args:
            scenarios: List of emission scenarios to compare
            months: Time horizon for comparison
            
        Returns:
            Dictionary with comparison results
        """
        original_config = self.config
        comparison_results = {
            'scenarios': [],
            'summary_comparison': pd.DataFrame(),
            'time_series_comparison': {}
        }
        
        try:
            for scenario in scenarios:
                # Create config for this scenario
                scenario_config = VEEmissionsConfig(
                    total_emissions_budget=original_config.total_emissions_budget,
                    base_monthly_rate=scenario.base_monthly_rate,
                    base_weekly_rate=scenario.base_monthly_rate / 4,
                    borrowed_step_size=original_config.borrowed_step_size,
                    emissions_step_up=scenario.emissions_step_up,
                    target_utilization_rate=original_config.target_utilization_rate,
                    initial_tvl=original_config.initial_tvl,
                    final_tvl=original_config.final_tvl,
                    initial_borrow=original_config.initial_borrow,
                    final_borrow=original_config.final_borrow,
                    lender_share=original_config.lender_share,
                    protocol_fee=original_config.protocol_fee,
                    admin_fee=original_config.admin_fee,
                    reserve_fee=original_config.reserve_fee,
                    liquidation_fee=original_config.liquidation_fee,
                    ve_token_fee=original_config.ve_token_fee,
                    monthly_tvl_growth=original_config.monthly_tvl_growth,
                    monthly_borrow_growth=original_config.monthly_borrow_growth,
                    token_price=original_config.token_price
                )
                
                # Run simulation for this scenario
                self.config = scenario_config
                self.setup_emission_steps()
                ts_data = self.generate_time_series(months)
                
                # Calculate metrics
                valid_ratios = ts_data['revenue_to_emissions_ratio'][
                    (ts_data['revenue_to_emissions_ratio'] >= 0) & 
                    (ts_data['revenue_to_emissions_ratio'] <= 1000)
                ]
                
                if len(valid_ratios) > 0:
                    avg_ratio = valid_ratios.mean()
                    min_ratio = valid_ratios.min()
                    max_ratio = valid_ratios.max()
                else:
                    avg_ratio = min_ratio = max_ratio = 0
                
                budget_used_pct = ts_data.iloc[-1]['cumulative_emissions'] / original_config.total_emissions_budget
                emission_months = len(ts_data[ts_data['emissions_per_month'] > 0])
                total_revenue = ts_data['protocol_revenue'].sum()
                total_emissions_cost = ts_data['emissions_cost_usd'].sum()
                
                scenario_result = {
                    'name': scenario.name,
                    'description': scenario.description,
                    'base_monthly_rate': scenario.base_monthly_rate,
                    'emissions_step_up': scenario.emissions_step_up,
                    'target_ratio': scenario.target_ratio,
                    'achieved_avg_ratio': avg_ratio,
                    'achieved_min_ratio': min_ratio,
                    'achieved_max_ratio': max_ratio,
                    'budget_used_pct': budget_used_pct,
                    'emission_duration_months': emission_months,
                    'total_revenue': total_revenue,
                    'total_emissions_cost': total_emissions_cost,
                    'net_profit': total_revenue - total_emissions_cost,
                    'time_series': ts_data,
                    'ratio_vs_target': avg_ratio / scenario.target_ratio if scenario.target_ratio > 0 else 0
                }
                
                comparison_results['scenarios'].append(scenario_result)
                comparison_results['time_series_comparison'][scenario.name] = ts_data
            
            # Create summary comparison DataFrame
            summary_data = []
            for result in comparison_results['scenarios']:
                summary_data.append({
                    'Scenario': result['name'],
                    'Base Rate': f"{result['base_monthly_rate']:.1%}",
                    'Step Up': f"{result['emissions_step_up']:.1%}",
                    'Target Ratio': f"{result['target_ratio']:.2f}",
                    'Achieved Ratio': f"{result['achieved_avg_ratio']:.2f}",
                    'Min Ratio': f"{result['achieved_min_ratio']:.2f}",
                    'Budget Used': f"{result['budget_used_pct']:.1%}",
                    'Duration (Months)': result['emission_duration_months'],
                    'Net Profit': f"${result['net_profit']:,.0f}",
                    'Target Achievement': f"{result['ratio_vs_target']:.1%}"
                })
            
            comparison_results['summary_comparison'] = pd.DataFrame(summary_data)
            
        finally:
            # Restore original config
            self.config = original_config
            self.setup_emission_steps()
        
        return comparison_results


def create_predefined_scenarios() -> List[EmissionScenario]:
    """Create predefined emission scenarios for comparison."""
    return [
        EmissionScenario(
            name="Conservative",
            base_monthly_rate=0.002,
            emissions_step_up=0.05,
            target_ratio=3.0,
            description="Low emissions, high sustainability"
        ),
        EmissionScenario(
            name="Balanced",
            base_monthly_rate=0.005,
            emissions_step_up=0.10,
            target_ratio=2.0,
            description="Moderate emissions, balanced growth"
        ),
        EmissionScenario(
            name="Aggressive",
            base_monthly_rate=0.010,
            emissions_step_up=0.20,
            target_ratio=1.5,
            description="High emissions, rapid adoption"
        ),
        EmissionScenario(
            name="Front-Loaded",
            base_monthly_rate=0.015,
            emissions_step_up=0.05,
            target_ratio=1.2,
            description="High initial emissions, low step-ups"
        ),
        EmissionScenario(
            name="Back-Loaded",
            base_monthly_rate=0.001,
            emissions_step_up=0.30,
            target_ratio=2.5,
            description="Low initial emissions, high step-ups"
        )
    ]


def create_ve_emissions_config_from_params(params: Dict[str, Any]) -> VEEmissionsConfig:
    """Create VE emissions configuration from parameter registry parameters."""
    return VEEmissionsConfig(
        total_emissions_budget=params.get('total_ion_emitted', 10_000_000),
        base_monthly_rate=params.get('base_monthly_emissions_rate', 0.005),
        base_weekly_rate=params.get('base_weekly_emissions_rate', 0.00125),
        borrowed_step_size=params.get('borrowed_step_size', 0.15),
        emissions_step_up=params.get('emissions_step_up', 0.10),
        target_utilization_rate=params.get('target_utilization_rate', 0.40),
        initial_tvl=params.get('tvl', 500_000),
        final_tvl=params.get('final_tvl', 50_000_000),
        initial_borrow=params.get('borrow', 100_000),
        final_borrow=params.get('final_borrowed', 20_000_000),
        lender_share=params.get('lender', 0.70),
        protocol_fee=params.get('protocol_fee', 0.20),
        admin_fee=params.get('admin_fee', 0.00),
        reserve_fee=params.get('reserve_fee', 0.00),
        liquidation_fee=params.get('liquidation_fee', 0.10),
        ve_token_fee=params.get('vetoken_fee', 0.10),
        monthly_tvl_growth=params.get('mom_tvl_growth', 0.05),
        monthly_borrow_growth=params.get('mom_borrow_growth', 0.05),
        token_price=params.get('token_price', 0.10)
    )


def create_optimization_target_from_inputs(
    min_ratio: float = 1.0,
    target_ratio: float = 2.0,
    max_budget_pct: float = 0.8,
    min_duration: int = 24,
    max_duration: int = 60
) -> OptimizationTarget:
    """Create optimization target from user inputs."""
    return OptimizationTarget(
        min_revenue_ratio=min_ratio,
        target_revenue_ratio=target_ratio,
        max_emissions_budget_pct=max_budget_pct,
        min_emission_duration_months=min_duration,
        max_emission_duration_months=max_duration
    ) 