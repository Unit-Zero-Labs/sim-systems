"""
VE Emissions UI Components for Scenario Analysis Tab
Handles parameter inputs and visualization for Voted-Escrow emissions modeling
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from logic.ve_emissions_model import VEEmissionsModel, VEEmissionsConfig, create_ve_emissions_config_from_params
from logic.parameter_registry import parameter_registry, ParameterCategory
from visualization.charts import plot_ve_emissions_comprehensive, plot_ve_emissions_monte_carlo


def display_ve_emissions_parameter_inputs() -> Dict[str, Any]:
    """
    Display parameter input controls for VE emissions model.
    Automatically adapts to parameters found in the CSV or provides manual inputs.
    
    Returns:
        Dictionary of parameter values
    """
    st.subheader("🎛️ VE Emissions Model Parameters")
    
    # Get VE emissions parameters from registry if available
    ve_params = parameter_registry.get_parameters_by_category(ParameterCategory.VE_EMISSIONS)
    
    # Create two columns for parameter organization
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📊 Protocol Metrics**")
        
        # TVL parameters
        initial_tvl = st.number_input(
            "Initial TVL ($)",
            min_value=1_000_000.0,
            max_value=10_000_000_000.0,
            value=float(ve_params.get('tvl', {}).get('value', 150_000_000)) if 'tvl' in ve_params else 150_000_000.0,
            step=1_000_000.0,
            format="%.0f",
            help="Total Value Locked at protocol launch"
        )
        
        final_tvl = st.number_input(
            "Target TVL ($)",
            min_value=initial_tvl,
            max_value=50_000_000_000.0,
            value=float(ve_params.get('final_tvl', {}).get('value', 1_000_000_000)) if 'final_tvl' in ve_params else 1_000_000_000.0,
            step=10_000_000.0,
            format="%.0f",
            help="Target TVL to reach over time"
        )
        
        # Borrowing parameters
        initial_borrow = st.number_input(
            "Initial Borrow Amount ($)",
            min_value=1_000_000.0,
            max_value=initial_tvl * 0.9,
            value=float(ve_params.get('borrow', {}).get('value', 40_000_000)) if 'borrow' in ve_params else 40_000_000.0,
            step=1_000_000.0,
            format="%.0f",
            help="Initial borrowing volume"
        )
        
        final_borrow = st.number_input(
            "Target Borrow Amount ($)",
            min_value=initial_borrow,
            max_value=final_tvl * 0.9,
            value=float(ve_params.get('final_borrowed', {}).get('value', 400_000_000)) if 'final_borrowed' in ve_params else 400_000_000.0,
            step=10_000_000.0,
            format="%.0f",
            help="Target borrowing volume"
        )
        
        # Growth rates
        monthly_tvl_growth = st.slider(
            "Monthly TVL Growth Rate",
            min_value=0.01,
            max_value=0.20,
            value=float(ve_params.get('mom_tvl_growth', {}).get('value', 0.05)) if 'mom_tvl_growth' in ve_params else 0.05,
            step=0.01,
            format="%.2f",
            help="Expected monthly TVL growth rate"
        )
        
        monthly_borrow_growth = st.slider(
            "Monthly Borrow Growth Rate",
            min_value=0.01,
            max_value=0.20,
            value=float(ve_params.get('mom_borrow_growth', {}).get('value', 0.05)) if 'mom_borrow_growth' in ve_params else 0.05,
            step=0.01,
            format="%.2f",
            help="Expected monthly borrowing growth rate"
        )
    
    with col2:
        st.markdown("**🎯 Emissions Configuration**")
        
        # Emissions budget
        total_emissions_budget = st.number_input(
            "Total Emissions Budget",
            min_value=1_000_000.0,
            max_value=10_000_000_000.0,
            value=float(ve_params.get('total_ion_emitted', {}).get('value', 300_000_000)) if 'total_ion_emitted' in ve_params else 300_000_000.0,
            step=1_000_000.0,
            format="%.0f",
            help="Total token emissions budget"
        )
        
        # Emission rates
        base_monthly_rate = st.slider(
            "Base Monthly Emission Rate",
            min_value=0.001,
            max_value=0.05,
            value=float(ve_params.get('base_monthly_emissions_rate', {}).get('value', 0.01)) if 'base_monthly_emissions_rate' in ve_params else 0.01,
            step=0.001,
            format="%.3f",
            help="Base monthly emission rate as % of total budget"
        )
        
        # Step configuration
        borrowed_step_size = st.slider(
            "Borrowing Step Size",
            min_value=0.05,
            max_value=0.50,
            value=float(ve_params.get('borrowed_step_size', {}).get('value', 0.15)) if 'borrowed_step_size' in ve_params else 0.15,
            step=0.05,
            format="%.2f",
            help="Borrowing volume increase required to trigger next emission step"
        )
        
        emissions_step_up = st.slider(
            "Emissions Step-Up Rate",
            min_value=0.05,
            max_value=0.50,
            value=float(ve_params.get('emissions_step_up', {}).get('value', 0.10)) if 'emissions_step_up' in ve_params else 0.10,
            step=0.05,
            format="%.2f",
            help="Emission rate increase per step"
        )
        
        # Revenue sharing
        protocol_fee = st.slider(
            "Protocol Fee Share",
            min_value=0.05,
            max_value=0.50,
            value=float(ve_params.get('protocol_fee', {}).get('value', 0.20)) if 'protocol_fee' in ve_params else 0.20,
            step=0.05,
            format="%.2f",
            help="Protocol's share of interest revenue"
        )
        
        # Token price
        token_price = st.number_input(
            "Token Price ($)",
            min_value=0.001,
            max_value=100.0,
            value=float(ve_params.get('token_price', {}).get('value', 0.05)) if 'token_price' in ve_params else 0.05,
            step=0.001,
            format="%.3f",
            help="Current token price for emissions cost calculation"
        )
        
        # Target utilization
        target_utilization_rate = st.slider(
            "Target Utilization Rate",
            min_value=0.20,
            max_value=0.80,
            value=float(ve_params.get('target_utilization_rate', {}).get('value', 0.40)) if 'target_utilization_rate' in ve_params else 0.40,
            step=0.05,
            format="%.2f",
            help="Target utilization rate for interest rate model"
        )
    
    # Return parameter dictionary
    return {
        'total_emissions_budget': total_emissions_budget,
        'base_monthly_rate': base_monthly_rate,
        'base_weekly_rate': base_monthly_rate / 4,  # Approximate weekly rate
        'borrowed_step_size': borrowed_step_size,
        'emissions_step_up': emissions_step_up,
        'target_utilization_rate': target_utilization_rate,
        'initial_tvl': initial_tvl,
        'final_tvl': final_tvl,
        'initial_borrow': initial_borrow,
        'final_borrow': final_borrow,
        'lender_share': 0.70,  # Default
        'protocol_fee': protocol_fee,
        'admin_fee': 0.00,  # Default
        'reserve_fee': 0.00,  # Default
        'liquidation_fee': 0.10,  # Default
        've_token_fee': 0.10,  # Default
        'monthly_tvl_growth': monthly_tvl_growth,
        'monthly_borrow_growth': monthly_borrow_growth,
        'token_price': token_price
    }


def display_ve_emissions_monte_carlo_controls() -> Dict[str, Any]:
    """
    Display Monte Carlo simulation controls for VE emissions model.
    
    Returns:
        Dictionary of Monte Carlo configuration
    """
    st.subheader("🎲 Monte Carlo Simulation Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        num_runs = st.slider(
            "Number of Simulation Runs",
            min_value=10,
            max_value=500,
            value=100,
            step=10,
            help="Number of Monte Carlo simulation runs"
        )
        
        show_confidence_intervals = st.checkbox(
            "Show Confidence Intervals",
            value=True,
            help="Display 95% confidence intervals"
        )
    
    with col2:
        show_percentiles = st.checkbox(
            "Show Percentile Bands",
            value=True,
            help="Display 25th-75th percentile bands"
        )
        
        show_secondary_metrics = st.checkbox(
            "Show Secondary Metrics",
            value=True,
            help="Display utilization rates and emission steps"
        )
    
    # Uncertainty parameters
    st.markdown("**📊 Parameter Uncertainty Ranges**")
    uncertainty_col1, uncertainty_col2 = st.columns(2)
    
    with uncertainty_col1:
        tvl_uncertainty = st.slider(
            "TVL Growth Uncertainty (±%)",
            min_value=0.05,
            max_value=0.50,
            value=0.20,
            step=0.05,
            format="%.2f",
            help="Uncertainty range for TVL growth rate"
        )
        
        borrow_uncertainty = st.slider(
            "Borrow Growth Uncertainty (±%)",
            min_value=0.05,
            max_value=0.50,
            value=0.25,
            step=0.05,
            format="%.2f",
            help="Uncertainty range for borrowing growth rate"
        )
    
    with uncertainty_col2:
        price_uncertainty = st.slider(
            "Token Price Uncertainty (±%)",
            min_value=0.10,
            max_value=0.50,
            value=0.30,
            step=0.05,
            format="%.2f",
            help="Uncertainty range for token price"
        )
        
        fee_uncertainty = st.slider(
            "Protocol Fee Uncertainty (±%)",
            min_value=0.05,
            max_value=0.30,
            value=0.10,
            step=0.05,
            format="%.2f",
            help="Uncertainty range for protocol fee"
        )
    
    return {
        'num_runs': num_runs,
        'show_confidence_intervals': show_confidence_intervals,
        'show_percentiles': show_percentiles,
        'show_secondary_metrics': show_secondary_metrics,
        'uncertainty_params': {
            'monthly_tvl_growth': tvl_uncertainty,
            'monthly_borrow_growth': borrow_uncertainty,
            'token_price': price_uncertainty,
            'protocol_fee': fee_uncertainty
        }
    }


def display_ve_emissions_results(
    ve_model: VEEmissionsModel,
    mc_config: Dict[str, Any],
    run_monte_carlo: bool = False
) -> None:
    """
    Display VE emissions model results with optional Monte Carlo analysis.
    
    Args:
        ve_model: VE emissions model instance
        mc_config: Monte Carlo configuration
        run_monte_carlo: Whether to run Monte Carlo simulation
    """
    # Generate base time series
    time_series_data = ve_model.generate_time_series()
    
    if run_monte_carlo:
        st.subheader("🎲 Monte Carlo Analysis Results")
        
        # Run Monte Carlo simulation
        with st.spinner("Running Monte Carlo simulation..."):
            mc_results = ve_model.run_monte_carlo_simulation(
                num_runs=mc_config['num_runs'],
                uncertainty_params=mc_config['uncertainty_params']
            )
        
        # Display Monte Carlo chart
        mc_fig = plot_ve_emissions_monte_carlo(
            mc_results,
            variable='revenue_to_emissions_ratio',
            show_confidence_intervals=mc_config['show_confidence_intervals'],
            show_percentiles=mc_config['show_percentiles']
        )
        st.plotly_chart(mc_fig, use_container_width=True)
        
        # Display summary statistics
        col1, col2, col3, col4 = st.columns(4)
        
        # Calculate final period statistics
        try:
            final_data = mc_results['raw_data'].groupby('run').last()
            
            with col1:
                if 'revenue_to_emissions_ratio' in final_data.columns:
                    final_ratio = final_data['revenue_to_emissions_ratio']
                    st.metric(
                        "Final Rev/Emissions Ratio",
                        f"{final_ratio.mean():.2f}",
                        delta=f"±{final_ratio.std():.2f}"
                    )
                else:
                    st.metric("Final Rev/Emissions Ratio", "N/A")
            
            with col2:
                if 'cumulative_emissions' in final_data.columns:
                    final_emissions = final_data['cumulative_emissions']
                    st.metric(
                        "Total Emissions",
                        f"{final_emissions.mean():,.0f}",
                        delta=f"±{final_emissions.std():,.0f}"
                    )
                else:
                    st.metric("Total Emissions", "N/A")
            
            with col3:
                if 'protocol_revenue' in final_data.columns:
                    final_revenue = final_data['protocol_revenue']
                    st.metric(
                        "Final Monthly Revenue",
                        f"${final_revenue.mean():,.0f}",
                        delta=f"±${final_revenue.std():,.0f}"
                    )
                else:
                    st.metric("Final Monthly Revenue", "N/A")
            
            with col4:
                if 'tvl' in final_data.columns:
                    final_tvl = final_data['tvl']
                    st.metric(
                        "Final TVL",
                        f"${final_tvl.mean():,.0f}",
                        delta=f"±${final_tvl.std():,.0f}"
                    )
                else:
                    st.metric("Final TVL", "N/A")
                    
        except Exception as e:
            st.error(f"Error calculating summary statistics: {str(e)}")
            # Show simplified metrics
            with col1:
                st.metric("Final Rev/Emissions Ratio", "Error")
            with col2:
                st.metric("Total Emissions", "Error")
            with col3:
                st.metric("Final Monthly Revenue", "Error")
            with col4:
                st.metric("Final TVL", "Error")
    
    else:
        st.subheader("📈 Base Case Analysis")
        
        # Display base case metrics
        col1, col2, col3, col4 = st.columns(4)
        
        final_idx = len(time_series_data) - 1
        
        with col1:
            st.metric(
                "Final Rev/Emissions Ratio",
                f"{time_series_data.iloc[final_idx]['revenue_to_emissions_ratio']:.2f}"
            )
        
        with col2:
            st.metric(
                "Total Emissions",
                f"{time_series_data.iloc[final_idx]['cumulative_emissions']:,.0f}"
            )
        
        with col3:
            st.metric(
                "Final Monthly Revenue",
                f"${time_series_data.iloc[final_idx]['protocol_revenue']:,.0f}"
            )
        
        with col4:
            st.metric(
                "Final TVL",
                f"${time_series_data.iloc[final_idx]['tvl']:,.0f}"
            )
    
    # Always show the comprehensive chart
    st.subheader("📊 Comprehensive VE Emissions Model")
    
    comprehensive_fig = plot_ve_emissions_comprehensive(
        time_series_data,
        show_secondary_metrics=mc_config.get('show_secondary_metrics', True),
        height=800
    )
    st.plotly_chart(comprehensive_fig, use_container_width=True)
    
    # Display key insights
    st.subheader("🔍 Key Insights")
    
    # Calculate insights from the data
    avg_ratio = time_series_data['revenue_to_emissions_ratio'].mean()
    min_ratio = time_series_data['revenue_to_emissions_ratio'].min()
    max_utilization = time_series_data['utilization_rate'].max()
    total_emissions_pct = (time_series_data.iloc[-1]['cumulative_emissions'] / ve_model.config.total_emissions_budget) * 100
    
    insights = [
        f"**Average Revenue-to-Emissions Ratio:** {avg_ratio:.2f}",
        f"**Minimum Revenue-to-Emissions Ratio:** {min_ratio:.2f}",
        f"**Peak Utilization Rate:** {max_utilization:.1%}",
        f"**Emissions Budget Utilized:** {total_emissions_pct:.1f}%"
    ]
    
    for insight in insights:
        st.write(f"• {insight}")


def create_ve_emissions_model_from_inputs(params: Dict[str, Any]) -> VEEmissionsModel:
    """
    Create VE emissions model from parameter inputs.
    
    Args:
        params: Parameter dictionary
        
    Returns:
        VEEmissionsModel instance
    """
    config = VEEmissionsConfig(**params)
    return VEEmissionsModel(config) 