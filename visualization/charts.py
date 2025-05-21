"""
Visualization module for the Unit Zero Labs Tokenomics Engine.
Contains all plotting functions used throughout the application.
"""

import plotly.graph_objects as go
import plotly.figure_factory as ff
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional, Union
import streamlit as st


def apply_chart_styling(fig: go.Figure) -> go.Figure:
    """
    Apply consistent styling to a Plotly figure.
    
    Args:
        fig: Plotly figure object
        
    Returns:
        Styled Plotly figure object
    """
    # Update paper and plot backgrounds
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white")
    )
    
    # Update axes
    fig.update_xaxes(
        showgrid=True, 
        gridwidth=1, 
        gridcolor="rgba(255,255,255,0.1)",
        showline=True,
        linewidth=1,
        linecolor="rgba(255,255,255,0.5)"
    )
    
    fig.update_yaxes(
        showgrid=True, 
        gridwidth=1, 
        gridcolor="rgba(255,255,255,0.1)",
        showline=True,
        linewidth=1,
        linecolor="rgba(255,255,255,0.5)"
    )
    
    return fig


def plot_token_buckets(data: Any) -> go.Figure:
    """
    Plot the token buckets and circulating supply over time.
    
    Args:
        data: TokenomicsData object containing vesting data
        
    Returns:
        Plotly figure object
    """
    fig = go.Figure()
    
    # Debug info
    st.info(f"Vesting series buckets: {data.vesting_series.index.tolist() if not data.vesting_series.empty else 'Empty'}")
    st.info(f"Vesting cumulative buckets: {data.vesting_cumulative.index.tolist() if not data.vesting_cumulative.empty else 'Empty'}")
    
    # Check if we have buckets to plot
    if data.vesting_cumulative.empty:
        # Fall back to showing just the total supply as a flat line
        if hasattr(data, 'static_params') and 'initial_total_supply' in data.static_params:
            initial_total_supply = data.static_params['initial_total_supply']
            fig.add_trace(go.Scatter(
                x=data.dates, 
                y=[initial_total_supply] * len(data.dates), 
                mode='lines', 
                name='Total Supply'
            ))
            st.warning("No vesting schedules found. Showing only total supply as a flat line.")
        else:
            st.error("No vesting schedules or total supply data found. Cannot create token buckets chart.")
        
        fig.update_layout(
            title="Project Token Buckets & Token Supply",
            xaxis_title="Date",
            yaxis_title="Tokens",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        
        return apply_chart_styling(fig)
    
    # Count the actual number of added traces to track if we added anything
    trace_count = 0
    
    # Add traces for each token bucket
    for bucket in data.vesting_series.index:
        if bucket and bucket != "SUM":  # Skip empty or summary rows
            fig.add_trace(go.Scatter(
                x=data.dates, 
                y=data.vesting_cumulative.loc[bucket], 
                mode='lines', 
                name=bucket
            ))
            trace_count += 1
    
    # Add circulating supply and unvested supply
    initial_total_supply = data.static_params.get('initial_total_supply', 0)
    
    if trace_count > 0:  # Only if we have at least one bucket
        # Add circulating supply (sum of all buckets except Liquidity Pool)
        has_liquidity_pool = "Liquidity Pool" in data.vesting_cumulative.index
        circulating_supply = data.vesting_cumulative.drop("Liquidity Pool", errors='ignore').sum() if has_liquidity_pool else data.vesting_cumulative.sum()
        fig.add_trace(go.Scatter(
            x=data.dates, 
            y=circulating_supply, 
            mode='lines', 
            name='Circulating Supply',
            line=dict(width=3, dash='dash', color='coral')
        ))
        
        # Add unvested supply line
        if initial_total_supply > 0:
            vested_supply = data.vesting_cumulative.sum()
            unvested_supply = [initial_total_supply - v for v in vested_supply]
            fig.add_trace(go.Scatter(
                x=data.dates, 
                y=unvested_supply, 
                mode='lines', 
                name='Unvested Supply',
                line=dict(width=2, dash='dot', color='aqua')
            ))
    else:
        # No buckets found, show the warning
        st.warning("No token buckets found in the data. Chart may be incomplete.")
    
    # Add total supply as a flat line
    if initial_total_supply > 0:
        holding_supply = [initial_total_supply] * len(data.dates)
        fig.add_trace(go.Scatter(
            x=data.dates, 
            y=holding_supply, 
            mode='lines', 
            name='Holding Supply',
            line=dict(width=2, dash='dash', color='gray')
        ))
    
    # Set y-axis range to ensure it's scaled properly
    y_max = max(initial_total_supply * 1.1, data.vesting_cumulative.values.max() * 1.1) if not data.vesting_cumulative.empty else initial_total_supply * 1.1
    
    fig.update_layout(
        title="Project Token Buckets & Token Supply",
        xaxis_title="Date",
        yaxis_title="Tokens",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(range=[0, y_max])
    )
    
    return apply_chart_styling(fig)


def plot_price(data: Any) -> go.Figure:
    """
    Plot the token price over time.
    
    Args:
        data: TokenomicsData object containing price data
        
    Returns:
        Plotly figure object
    """
    fig = go.Figure()
    
    # Use the time-series data
    fig.add_trace(go.Scatter(
        x=data.dates, 
        y=data.token_price_series.loc["Token Price"], 
        mode='lines', 
        name='Price'
    ))
    
    fig.update_layout(
        title="Token Price",
        xaxis_title="Date",
        yaxis_title="USD",
    )
    
    return apply_chart_styling(fig)


def plot_valuations(data: Any) -> go.Figure:
    """
    Plot the token valuations (Market Cap and FDV) over time.
    
    Args:
        data: TokenomicsData object containing valuation data
        
    Returns:
        Plotly figure object
    """
    fig = go.Figure()
    
    # Use the time-series data
    fig.add_trace(go.Scatter(
        x=data.dates, 
        y=data.market_cap_series.loc["Market Cap"], 
        mode='lines', 
        name='Market Cap'
    ))
    
    fig.add_trace(go.Scatter(
        x=data.dates, 
        y=data.fdv_mc_series.loc["FDV MC"], 
        mode='lines', 
        name='FDV MC'
    ))
    
    fig.update_layout(
        title="Token Valuations",
        xaxis_title="Date",
        yaxis_title="USD",
    )
    
    return apply_chart_styling(fig)


def plot_dex_liquidity(data: Any) -> go.Figure:
    """
    Plot the DEX liquidity valuation over time.
    
    Args:
        data: TokenomicsData object containing liquidity data
        
    Returns:
        Plotly figure object
    """
    fig = go.Figure()
    
    # Use the time-series data
    fig.add_trace(go.Scatter(
        x=data.dates, 
        y=data.liquidity_pool_series.loc["LP Valuation"], 
        mode='lines', 
        name='LP Valuation'
    ))
    
    fig.update_layout(
        title="DEX Liquidity Valuation",
        xaxis_title="Date",
        yaxis_title="USD",
    )
    
    return apply_chart_styling(fig)


def plot_utility_allocations(data: Any) -> go.Figure:
    """
    Plot the utility allocations over time.
    
    Args:
        data: TokenomicsData object containing utility allocation data
        
    Returns:
        Plotly figure object
    """
    fig = go.Figure()
    
    # Add traces for each utility allocation
    for utility in data.utility_allocations.index:
        if utility and "CUM" in utility:  # Only include cumulative rows
            fig.add_trace(go.Scatter(
                x=data.dates, 
                y=data.utility_allocations.loc[utility], 
                mode='lines', 
                name=utility.replace(" CUM.", "")
            ))
    
    fig.update_layout(
        title="Utility Allocations",
        xaxis_title="Date",
        yaxis_title="Tokens",
    )
    
    return apply_chart_styling(fig)


def plot_monthly_utility(data: Any) -> go.Figure:
    """
    Plot the monthly utility incentives/burnings/transfers.
    
    Args:
        data: TokenomicsData object containing monthly utility data
        
    Returns:
        Plotly figure object
    """
    fig = go.Figure()
    
    # Add traces for each utility
    for utility in data.monthly_utility.index:
        if utility and utility not in ["SUM", "0", 0]:
            fig.add_trace(go.Scatter(
                x=data.dates, 
                y=data.monthly_utility.loc[utility], 
                mode='lines', 
                name=utility
            ))
    
    fig.update_layout(
        title="Monthly Utility Incentives / Burnings / Transfers",
        xaxis_title="Date",
        yaxis_title="Tokens",
    )
    
    return apply_chart_styling(fig)


def plot_staking_apr(data: Any) -> go.Figure:
    """
    Plot the staking APR over time.
    
    Args:
        data: TokenomicsData object containing staking APR data
        
    Returns:
        Plotly figure object
    """
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=data.dates, 
        y=data.staking_apr.loc["Staking APR"], 
        mode='lines', 
        name='APR'
    ))
    
    fig.update_layout(
        title="Staking APR",
        xaxis_title="Date",
        yaxis_title="APR (%)",
    )
    
    return apply_chart_styling(fig)


def plot_monte_carlo_results(
    mc_results: Dict[str, Any], 
    variable: str, 
    show_confidence_intervals: bool = True, 
    show_percentiles: bool = True
) -> go.Figure:
    """
    Create a plot for Monte Carlo simulation results with confidence intervals and percentile bands.
    
    Args:
        mc_results: Results from a Monte Carlo simulation
        variable: The state variable to visualize (e.g., 'token_price', 'market_cap')
        show_confidence_intervals: Whether to show 95% confidence intervals
        show_percentiles: Whether to show percentile bands (5th, 25th, 75th, 95th)
        
    Returns:
        Plotly figure object
    """
    # Create the plot
    fig = go.Figure()
    
    # Get x values (dates or timesteps)
    if 'mean' not in mc_results or variable not in mc_results['mean']:
        raise ValueError(f"Variable '{variable}' not found in Monte Carlo results")
        
    x_values = mc_results['mean'][variable].index
    
    # Handle different data formats for mean values
    if isinstance(mc_results['mean'][variable], pd.DataFrame):
        if mc_results['mean'][variable].shape[1] > 0:
            mean_values = mc_results['mean'][variable].iloc[:, 0].values
        else:
            mean_values = mc_results['mean'][variable].values.flatten()
    elif isinstance(mc_results['mean'][variable], pd.Series):
        mean_values = mc_results['mean'][variable].values
    else:
        # Handle other formats
        mean_values = np.array(list(mc_results['mean'][variable]))
    
    # Add mean line
    fig.add_trace(go.Scatter(
        x=x_values,
        y=mean_values,
        mode='lines',
        name='Mean',
        line=dict(color='blue', width=2)
    ))
    
    # Add confidence intervals
    if show_confidence_intervals and 'conf_intervals' in mc_results and variable in mc_results['conf_intervals']:
        conf_intervals = mc_results['conf_intervals'][variable]
        
        # Handle different data formats for confidence intervals
        if isinstance(conf_intervals, pd.DataFrame) and 'lower' in conf_intervals.columns and 'upper' in conf_intervals.columns:
            lower_ci = conf_intervals['lower'].values
            upper_ci = conf_intervals['upper'].values
        elif isinstance(conf_intervals, np.ndarray) and conf_intervals.ndim == 2 and conf_intervals.shape[1] == 2:
            lower_ci = conf_intervals[:, 0]
            upper_ci = conf_intervals[:, 1]
        else:
            # Try to extract confidence intervals from various formats
            try:
                lower_ci = []
                upper_ci = []
                for idx in range(len(conf_intervals)):
                    val = conf_intervals.iloc[idx] if hasattr(conf_intervals, 'iloc') else conf_intervals[idx]
                    if hasattr(val, '__getitem__') and len(val) >= 2:
                        lower_ci.append(val[0])
                        upper_ci.append(val[1])
                    else:
                        # Skip invalid values
                        continue
            except (IndexError, AttributeError, TypeError):
                # Fallback: don't show confidence intervals
                lower_ci = []
                upper_ci = []
        
        if len(lower_ci) > 0 and len(upper_ci) > 0:
            # Ensure we have equal length arrays
            min_len = min(len(lower_ci), len(upper_ci), len(x_values))
            
            fig.add_trace(go.Scatter(
                x=x_values[:min_len],
                y=upper_ci[:min_len],
                mode='lines',
                name='95% CI Upper',
                line=dict(width=0),
                showlegend=False
            ))
            
            fig.add_trace(go.Scatter(
                x=x_values[:min_len],
                y=lower_ci[:min_len],
                mode='lines',
                name='95% CI Lower',
                line=dict(width=0),
                fill='tonexty',
                fillcolor='rgba(0, 0, 255, 0.2)',
                showlegend=False
            ))
    
    # Add percentile bands
    if show_percentiles and 'percentiles' in mc_results and variable in mc_results['percentiles']:
        percentiles = mc_results['percentiles'][variable]
        
        # Check if percentiles is properly structured with 5 percentile values
        if isinstance(percentiles, pd.DataFrame) and percentiles.shape[1] >= 5:
            # Get the column indices for each percentile
            p5_idx, p25_idx, p50_idx, p75_idx, p95_idx = 0, 1, 2, 3, 4
            
            # 5th and 95th percentiles
            fig.add_trace(go.Scatter(
                x=x_values,
                y=percentiles.iloc[:, p95_idx].values,  # 95th percentile
                mode='lines',
                name='95th Percentile',
                line=dict(color='rgba(255, 0, 0, 0.5)', width=1, dash='dot')
            ))
            
            fig.add_trace(go.Scatter(
                x=x_values,
                y=percentiles.iloc[:, p5_idx].values,  # 5th percentile
                mode='lines',
                name='5th Percentile',
                line=dict(color='rgba(255, 0, 0, 0.5)', width=1, dash='dot')
            ))
            
            # 25th and 75th percentiles
            fig.add_trace(go.Scatter(
                x=x_values,
                y=percentiles.iloc[:, p75_idx].values,  # 75th percentile
                mode='lines',
                name='75th Percentile',
                line=dict(color='rgba(0, 255, 0, 0.5)', width=1, dash='dot')
            ))
            
            fig.add_trace(go.Scatter(
                x=x_values,
                y=percentiles.iloc[:, p25_idx].values,  # 25th percentile
                mode='lines',
                name='25th Percentile',
                line=dict(color='rgba(0, 255, 0, 0.5)', width=1, dash='dot')
            ))
        elif isinstance(percentiles, np.ndarray) and percentiles.ndim == 2 and percentiles.shape[1] >= 5:
            # 5th and 95th percentiles
            fig.add_trace(go.Scatter(
                x=x_values,
                y=[p[4] for p in percentiles],  # 95th percentile
                mode='lines',
                name='95th Percentile',
                line=dict(color='rgba(255, 0, 0, 0.5)', width=1, dash='dot')
            ))
            
            fig.add_trace(go.Scatter(
                x=x_values,
                y=[p[0] for p in percentiles],  # 5th percentile
                mode='lines',
                name='5th Percentile',
                line=dict(color='rgba(255, 0, 0, 0.5)', width=1, dash='dot')
            ))
            
            # 25th and 75th percentiles
            fig.add_trace(go.Scatter(
                x=x_values,
                y=[p[3] for p in percentiles],  # 75th percentile
                mode='lines',
                name='75th Percentile',
                line=dict(color='rgba(0, 255, 0, 0.5)', width=1, dash='dot')
            ))
            
            fig.add_trace(go.Scatter(
                x=x_values,
                y=[p[1] for p in percentiles],  # 25th percentile
                mode='lines',
                name='25th Percentile',
                line=dict(color='rgba(0, 255, 0, 0.5)', width=1, dash='dot')
            ))
    
    # Update layout
    fig.update_layout(
        title=f"Monte Carlo Simulation: {variable.replace('_', ' ').title()}",
        xaxis_title="Date",
        yaxis_title=variable.replace('_', ' ').title(),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
    )
    
    return apply_chart_styling(fig)


def plot_distribution_at_timestep(
    mc_results: Dict[str, Any], 
    variable: str, 
    timestep: int
) -> Tuple[go.Figure, Dict[str, Any]]:
    """
    Create a probability distribution plot for a specific variable at a specific timestep.
    
    Args:
        mc_results: Results from a Monte Carlo simulation
        variable: The state variable to analyze (e.g., 'token_price', 'market_cap')
        timestep: The timestep to analyze
        
    Returns:
        Tuple containing:
            - Plotly figure object for the distribution
            - Dictionary of statistics
    """
    # Validate inputs
    if 'raw_data' not in mc_results or not isinstance(mc_results['raw_data'], pd.DataFrame):
        raise ValueError("Monte Carlo results don't contain valid raw data")
    
    # Get distribution data
    raw_data = mc_results['raw_data']
    
    # Check if variable and timestep exist in the data
    if variable not in raw_data.columns:
        raise ValueError(f"Variable '{variable}' not found in Monte Carlo results")
        
    timestep_data = raw_data[raw_data['timestep'] == timestep]
    if len(timestep_data) == 0:
        raise ValueError(f"No data available for timestep {timestep}")
        
    values = timestep_data[variable].values
    if len(values) == 0:
        raise ValueError(f"No values for variable '{variable}' at timestep {timestep}")
    
    # Calculate statistics
    mean = np.mean(values)
    median = np.median(values)
    std_dev = np.std(values)
    
    # Calculate CV (handle division by zero)
    if mean != 0:
        cv = std_dev / mean
    else:
        cv = float('inf')
    
    # Calculate percentiles
    percentiles = np.percentile(values, [5, 25, 50, 75, 95])
    
    # Create histogram with density curve
    hist_fig = ff.create_distplot(
        [values], 
        [variable.replace('_', ' ').title()],
        bin_size=(max(values) - min(values)) / 20 if max(values) > min(values) else 0.01,
        show_rug=False,
        colors=['rgba(0, 0, 255, 0.6)']
    )
    
    # Add vertical lines for statistics
    hist_fig.add_vline(x=mean, line_dash="solid", line_color="blue", annotation_text="Mean")
    hist_fig.add_vline(x=median, line_dash="dash", line_color="green", annotation_text="Median")
    hist_fig.add_vline(x=percentiles[0], line_dash="dot", line_color="red", annotation_text="5th")
    hist_fig.add_vline(x=percentiles[4], line_dash="dot", line_color="red", annotation_text="95th")
    
    # Update layout
    hist_fig.update_layout(
        title=f"Probability Distribution at Timestep {timestep}",
        xaxis_title=variable.replace('_', ' ').title(),
        yaxis_title="Probability Density",
    )
    
    # Apply consistent styling
    hist_fig = apply_chart_styling(hist_fig)
    
    # Create statistics dictionary
    stats = {
        'mean': mean,
        'median': median,
        'std_dev': std_dev,
        'percentiles': percentiles,
        'cv': cv
    }
    
    return hist_fig, stats


def plot_time_series_from_simulator(
    simulator, 
    variable: str, 
    show_confidence_intervals: bool = True, 
    show_percentiles: bool = True
) -> go.Figure:
    """
    Create a plot using time series data directly from a Monte Carlo simulator.
    
    Args:
        simulator: MonteCarloSimulator instance with results
        variable: The state variable to visualize
        show_confidence_intervals: Whether to show 95% confidence intervals
        show_percentiles: Whether to show percentile bands
        
    Returns:
        Plotly figure object
    """
    # Get time series data from simulator
    time_series_data = simulator.get_time_series_data(variable)
    
    # Create plot
    fig = go.Figure()
    
    # Add mean line
    fig.add_trace(go.Scatter(
        x=time_series_data['x_values'],
        y=time_series_data['mean'],
        mode='lines',
        name='Mean',
        line=dict(color='blue', width=2)
    ))
    
    # Add confidence intervals
    if show_confidence_intervals and 'lower_ci' in time_series_data and 'upper_ci' in time_series_data:
        fig.add_trace(go.Scatter(
            x=time_series_data['x_values'],
            y=time_series_data['upper_ci'],
            mode='lines',
            name='95% CI Upper',
            line=dict(width=0),
            showlegend=False
        ))
        
        fig.add_trace(go.Scatter(
            x=time_series_data['x_values'],
            y=time_series_data['lower_ci'],
            mode='lines',
            name='95% CI Lower',
            line=dict(width=0),
            fill='tonexty',
            fillcolor='rgba(0, 0, 255, 0.2)',
            showlegend=False
        ))
    
    # Add percentile bands
    if show_percentiles and 'percentiles' in time_series_data:
        percentiles = time_series_data['percentiles']
        
        # 5th and 95th percentiles
        fig.add_trace(go.Scatter(
            x=time_series_data['x_values'],
            y=[p[4] for p in percentiles],  # 95th percentile
            mode='lines',
            name='95th Percentile',
            line=dict(color='rgba(255, 0, 0, 0.5)', width=1, dash='dot')
        ))
        
        fig.add_trace(go.Scatter(
            x=time_series_data['x_values'],
            y=[p[0] for p in percentiles],  # 5th percentile
            mode='lines',
            name='5th Percentile',
            line=dict(color='rgba(255, 0, 0, 0.5)', width=1, dash='dot')
        ))
        
        # 25th and 75th percentiles
        fig.add_trace(go.Scatter(
            x=time_series_data['x_values'],
            y=[p[3] for p in percentiles],  # 75th percentile
            mode='lines',
            name='75th Percentile',
            line=dict(color='rgba(0, 255, 0, 0.5)', width=1, dash='dot')
        ))
        
        fig.add_trace(go.Scatter(
            x=time_series_data['x_values'],
            y=[p[1] for p in percentiles],  # 25th percentile
            mode='lines',
            name='25th Percentile',
            line=dict(color='rgba(0, 255, 0, 0.5)', width=1, dash='dot')
        ))
    
    # Update layout
    fig.update_layout(
        title=f"Monte Carlo Simulation: {variable.replace('_', ' ').title()}",
        xaxis_title="Date",
        yaxis_title=variable.replace('_', ' ').title(),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
    )
    
    return apply_chart_styling(fig)


def plot_token_supply_simulation(sim_result: pd.DataFrame) -> go.Figure:
    """
    Plot the token supply simulation results.
    
    Args:
        sim_result: DataFrame with simulation results
        
    Returns:
        Plotly figure object
    """
    fig = go.Figure()
    
    # Add trace for circulating supply
    fig.add_trace(go.Scatter(
        x=sim_result['date'], 
        y=sim_result['circulating_supply'], 
        mode='lines', 
        name='Circulating Supply'
    ))
    
    # Add trace for total supply
    fig.add_trace(go.Scatter(
        x=sim_result['date'], 
        y=sim_result['token_supply'], 
        mode='lines', 
        name='Total Supply',
        line=dict(dash='dash')
    ))
    
    # Ensure y-axis starts at zero
    fig.update_layout(
        title="Simulated Token Supply",
        xaxis_title="Date",
        yaxis_title="Tokens",
        yaxis=dict(rangemode="tozero")
    )
    
    return apply_chart_styling(fig)


def plot_token_price_simulation(sim_result: pd.DataFrame) -> go.Figure:
    """
    Plot the token price simulation results.
    
    Args:
        sim_result: DataFrame with simulation results
        
    Returns:
        Plotly figure object
    """
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=sim_result['date'], 
        y=sim_result['token_price'], 
        mode='lines', 
        name='Token Price'
    ))
    
    fig.update_layout(
        title="Simulated Token Price",
        xaxis_title="Date",
        yaxis_title="USD",
    )
    
    return apply_chart_styling(fig)


def plot_market_cap_simulation(sim_result: pd.DataFrame) -> go.Figure:
    """
    Plot the market cap simulation results.
    
    Args:
        sim_result: DataFrame with simulation results
        
    Returns:
        Plotly figure object
    """
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=sim_result['date'], 
        y=sim_result['market_cap'], 
        mode='lines', 
        name='Market Cap'
    ))
    
    fig.update_layout(
        title="Simulated Market Cap",
        xaxis_title="Date",
        yaxis_title="USD",
    )
    
    return apply_chart_styling(fig)


def plot_staking_simulation(sim_result: pd.DataFrame) -> go.Figure:
    """
    Plot the staking simulation results.
    
    Args:
        sim_result: DataFrame with simulation results
        
    Returns:
        Plotly figure object
    """
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=sim_result['date'], 
        y=sim_result['staked_tokens'], 
        mode='lines', 
        name='Staked Tokens'
    ))
    
    fig.update_layout(
        title="Simulated Staked Tokens",
        xaxis_title="Date",
        yaxis_title="Tokens",
    )
    
    return apply_chart_styling(fig)