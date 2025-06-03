"""
Dynamic policy factory for parameter-driven simulation policies.
Automatically creates radCAD policies based on available parameters.
"""

from typing import Dict, Any, List, Callable, Optional, Tuple
import pandas as pd
import random
import streamlit as st
from logic.parameter_registry import ParameterRegistry, ParameterCategory
from logic.ve_emissions_model import create_ve_emissions_config_from_params, VEEmissionsModel


class PolicyFactory:
    """
    Factory for creating radCAD policies dynamically based on available parameters.
    Enables automatic simulation adaptation for new client requirements.
    """
    
    def __init__(self, registry: ParameterRegistry):
        self.registry = registry
        self.policy_creators = self._setup_policy_creators()
        
    def _setup_policy_creators(self) -> Dict[str, Callable]:
        """Setup mapping of policy names to their creator functions."""
        return {
            "points_campaign": self._create_points_campaign_policy,
            "custom_utility": self._create_custom_utility_policy,
            "custom_agent_behavior": self._create_custom_agent_behavior_policy,
            "enhanced_staking": self._create_enhanced_staking_policy,
            "ve_emissions": self._create_ve_emissions_policy
        }
    
    def discover_and_create_policies(self, data) -> Dict[str, Callable]:
        """
        Discover available policies based on parameters and create policy functions.
        
        Args:
            data: TokenomicsData object for accessing baseline data
            
        Returns:
            Dictionary of policy name to policy function mappings
        """
        created_policies = {}
        
        # Always include base policies
        created_policies.update(self._create_base_policies(data))
        
        # Only add advanced policies if we have clear evidence they should be active
        try:
            # Check for points campaign
            points_params = self.registry.get_parameters_by_category(ParameterCategory.POINTS_CAMPAIGN)
            if points_params and len(points_params) > 3:  # Need substantial points parameters
                created_policies["points_campaign"] = self._create_points_campaign_policy(data)
            
            # Check for VE emissions parameters
            ve_params = self.registry.get_parameters_by_category(ParameterCategory.VE_EMISSIONS)
            if ve_params and len(ve_params) > 5:  # Need substantial VE emissions parameters
                created_policies["ve_emissions"] = self._create_ve_emissions_policy(data)
            
            # Check for custom utility mechanisms
            utility_params = self.registry.get_parameters_by_category(ParameterCategory.UTILITY)
            if utility_params and any("utility" in param_name.lower() for param_name in utility_params.keys()):
                created_policies["custom_utility"] = self._create_custom_utility_policy(data)
            
            # Check for agent behavior parameters  
            agent_params = self.registry.get_parameters_by_category(ParameterCategory.AGENT_BEHAVIOR)
            if agent_params and len(agent_params) > 0:
                # Add agent behavior policy for direct effects
                created_policies["agent_behavior"] = self._create_custom_agent_behavior_policy(data)
                
        except Exception as e:
            # If advanced policies fail, just continue with base policies
            st.info(f"Note: Some advanced features were skipped due to configuration issues.")
        
        return created_policies
    
    def _create_base_policies(self, data) -> Dict[str, Callable]:
        """Create base policies that are always available."""
        base_policies = {
            "vesting": self._create_vesting_policy(data),
            "staking": self._create_staking_policy(data),
        }
        
        # Check if we have agent behavior parameters to use enhanced price policy
        agent_params = self.registry.get_parameters_by_category(ParameterCategory.AGENT_BEHAVIOR)
        if agent_params and len(agent_params) > 0:
            # Use agent-influenced price policy instead of basic price policy
            base_policies["price"] = self._create_agent_influenced_price_policy(data)
        else:
            # Use basic price policy
            base_policies["price"] = self._create_price_policy(data)
            
        return base_policies
    
    def _create_vesting_policy(self, data) -> Callable:
        """Create the base vesting schedule policy."""
        def p_vesting_schedule(params, substep, state_history, prev_state):
            """Policy function for token vesting schedule."""
            time_step = prev_state["time_step"]
            
            newly_vested = {}
            
            if not data.vesting_series.empty:
                for bucket in data.vesting_series.index:
                    if bucket != "SUM" and bucket != "Liquidity Pool":
                        if time_step < len(data.vesting_series.columns):
                            bucket_row = data.vesting_series.loc[bucket]
                            if len(bucket_row) > time_step:
                                newly_vested[bucket] = bucket_row.iloc[time_step]
                            else:
                                newly_vested[bucket] = 0
                        else:
                            newly_vested[bucket] = 0
            
            return {"newly_vested": sum(newly_vested.values())}
        
        return p_vesting_schedule
    
    def _create_staking_policy(self, data) -> Callable:
        """Create the base staking policy with parameter-driven behavior."""
        def p_staking(params, substep, state_history, prev_state):
            """Policy function for staking behavior."""
            # Get staking parameters from the parameter registry
            staking_params = self.registry.get_parameters_by_category(ParameterCategory.STAKING)
            
            # Use registered parameters with fallbacks
            staking_share = params.get("staking_share", 0.5)
            
            # Check for staking utility share from CSV
            if "staking_utility_share" in staking_params:
                staking_share = staking_params["staking_utility_share"].value / 100.0
            
            circulating_supply = prev_state["circulating_supply"]
            current_staked = prev_state["staked_tokens"]
            
            target_staked = circulating_supply * staking_share
            staking_delta = target_staked - current_staked
            
            if staking_delta > 0:
                max_new_staking = min(staking_delta, circulating_supply - current_staked)
            else:
                max_new_staking = staking_delta
            
            return {"staking_delta": max_new_staking}
        
        return p_staking
    
    def _create_price_policy(self, data) -> Callable:
        """Create the base price policy with parameter-driven behavior."""
        def p_token_price(params, substep, state_history, prev_state):
            """Policy function for token price dynamics."""
            current_price = prev_state["token_price"]
            
            # Get pricing parameters
            pricing_params = self.registry.get_parameters_by_category(ParameterCategory.PRICING)
            
            market_volatility = params.get("market_volatility", 0.2)
            if "market_volatility" in pricing_params:
                market_volatility = pricing_params["market_volatility"].value
            
            # Enhanced price model using additional parameters
            staked_ratio = prev_state["staked_tokens"] / prev_state["circulating_supply"] if prev_state["circulating_supply"] > 0 else 0
            
            # Check for speculation factor from CSV
            speculation_factor = 0.5  # Default
            if "speculation_factor" in pricing_params:
                speculation_factor = pricing_params["speculation_factor"].value
            
            # Base price movement from staking ratio
            price_multiplier = 1 + (staked_ratio - 0.5) * 0.1
            
            # Add speculation factor influence
            speculation_influence = 1 + (random.random() - 0.5) * speculation_factor * 0.2
            
            # Market volatility
            random_factor = 1 + (random.random() - 0.5) * market_volatility
            
            new_price = current_price * price_multiplier * speculation_influence * random_factor
            new_price = max(new_price, 0.001)  # Price floor
            
            return {"price_delta": new_price - current_price}
        
        return p_token_price
    
    def _create_points_campaign_policy(self, data) -> Callable:
        """Create off-chain points campaign policy based on available parameters."""
        points_params = self.registry.get_parameters_by_category(ParameterCategory.POINTS_CAMPAIGN)
        
        # Extract campaign configuration from parameters
        stages = []
        default_conversion_rate = 0.5  # Default conversion rate
        
        # Parse campaign stages
        num_stages = 1
        if "points_campaign_stages" in points_params:
            raw_value = points_params["points_campaign_stages"].value
            num_stages = int(raw_value) if raw_value is not None else 1
        
        for i in range(1, num_stages + 1):
            stage_name = f"points_campaign_stage_{['one', 'two', 'three'][i-1] if i <= 3 else str(i)}"
            if stage_name in points_params:
                stages.append({
                    "name": points_params[stage_name].value if points_params[stage_name].value is not None else f"Stage {i}",
                    "duration": 4,  # Default 4 weeks
                    "participants": 1000,  # Default
                    "points_per_participant": 100  # Default
                })
        
        def p_points_campaign(params, substep, state_history, prev_state):
            """Policy function for off-chain points campaign."""
            time_step = prev_state["time_step"]
            
            # Get conversion rate from runtime params first, then registry, then default
            conversion_rate = default_conversion_rate
            
            # Try to get from runtime parameters first
            if "point_to_token_conversion_rate" in params:
                runtime_value = params["point_to_token_conversion_rate"]
                if runtime_value is not None and runtime_value > 0:
                    conversion_rate = runtime_value
            # Fallback to registry
            elif "point_to_token_conversion_rate" in points_params:
                registry_value = points_params["point_to_token_conversion_rate"].value
                if registry_value is not None and registry_value > 0:
                    conversion_rate = registry_value
            
            # Ensure conversion_rate is a valid number
            if conversion_rate is None or not isinstance(conversion_rate, (int, float)) or conversion_rate <= 0:
                conversion_rate = default_conversion_rate
            
            # Determine current campaign stage based on time
            current_stage = None
            cumulative_duration = 0
            
            for stage in stages:
                stage_duration_timesteps = stage["duration"]  # Assuming monthly timesteps
                if time_step < cumulative_duration + stage_duration_timesteps:
                    current_stage = stage
                    break
                cumulative_duration += stage_duration_timesteps
            
            points_issued = 0
            tokens_converted = 0
            
            if current_stage:
                # Issue points based on stage configuration
                points_issued = current_stage["participants"] * current_stage["points_per_participant"]
                
                # Check for conversion events (e.g., every few timesteps)
                if time_step % 3 == 0:  # Convert every 3 months
                    # Convert accumulated points to tokens
                    total_points = points_issued * 3  # Simplified accumulation
                    tokens_converted = total_points * conversion_rate
            
            return {
                "points_issued": points_issued,
                "tokens_converted": tokens_converted,
                "campaign_stage": current_stage["name"] if current_stage else "inactive"
            }
        
        return p_points_campaign
    
    def _create_custom_utility_policy(self, data) -> Callable:
        """Create custom utility mechanisms policy."""
        utility_params = self.registry.get_parameters_by_category(ParameterCategory.UTILITY)
        
        def p_custom_utility(params, substep, state_history, prev_state):
            """Policy function for custom utility mechanisms."""
            time_step = prev_state["time_step"]
            
            # Extract utility allocations from parameters with safe access
            burning_share = 0
            holding_share = 0
            transfer_share = 0
            
            # Try runtime parameters first, then registry
            if "burning_utility_share" in params:
                burning_share = params["burning_utility_share"] / 100.0 if params["burning_utility_share"] is not None else 0
            elif "burning_utility_share" in utility_params:
                registry_value = utility_params["burning_utility_share"].value
                burning_share = registry_value / 100.0 if registry_value is not None else 0
            
            if "holding_utility_share" in params:
                holding_share = params["holding_utility_share"] / 100.0 if params["holding_utility_share"] is not None else 0
            elif "holding_utility_share" in utility_params:
                registry_value = utility_params["holding_utility_share"].value
                holding_share = registry_value / 100.0 if registry_value is not None else 0
            
            if "transfer_for_benefit_utility_share" in params:
                transfer_share = params["transfer_for_benefit_utility_share"] / 100.0 if params["transfer_for_benefit_utility_share"] is not None else 0
            elif "transfer_for_benefit_utility_share" in utility_params:
                registry_value = utility_params["transfer_for_benefit_utility_share"].value
                transfer_share = registry_value / 100.0 if registry_value is not None else 0
            
            # Calculate utility actions based on circulating supply
            circulating_supply = prev_state["circulating_supply"]
            monthly_utility_volume = circulating_supply * 0.01  # 1% monthly utility
            
            tokens_burned = monthly_utility_volume * burning_share
            tokens_held_rewards = monthly_utility_volume * holding_share
            tokens_transferred = monthly_utility_volume * transfer_share
            
            return {
                "tokens_burned": tokens_burned,
                "tokens_held_rewards": tokens_held_rewards,
                "tokens_transferred": tokens_transferred
            }
        
        return p_custom_utility
    
    def _create_custom_agent_behavior_policy(self, data) -> Callable:
        """Create custom agent behavior policy."""
        agent_params = self.registry.get_parameters_by_category(ParameterCategory.AGENT_BEHAVIOR)
        
        def p_custom_agent_behavior(params, substep, state_history, prev_state):
            """Policy function for custom agent behaviors."""
            # Extract agent behavior parameters with safe access
            avg_trading_fund_usage = 0.1
            avg_token_lock = 0.3
            
            # Try runtime parameters first, then registry
            if "avg_trading_fund_usage" in params:
                avg_trading_fund_usage = params["avg_trading_fund_usage"] if params["avg_trading_fund_usage"] is not None else 0.1
            elif "avg_trading_fund_usage" in agent_params:
                registry_value = agent_params["avg_trading_fund_usage"].value
                avg_trading_fund_usage = registry_value if registry_value is not None else 0.1
            
            if "avg_token_lock" in params:
                avg_token_lock = params["avg_token_lock"] if params["avg_token_lock"] is not None else 0.3
            elif "avg_token_lock" in agent_params:
                registry_value = agent_params["avg_token_lock"].value
                avg_token_lock = registry_value if registry_value is not None else 0.3
            
            # Simulate custom agent behavior effects
            circulating_supply = prev_state["circulating_supply"]
            
            # Trading pressure from fund usage
            trading_volume = circulating_supply * avg_trading_fund_usage
            
            # Token locking behavior
            tokens_locked = circulating_supply * avg_token_lock * 0.1  # 10% of target per timestep
            
            return {
                "trading_volume": trading_volume,
                "tokens_locked": tokens_locked
            }
        
        return p_custom_agent_behavior
    
    def _create_enhanced_staking_policy(self, data) -> Callable:
        """Create enhanced staking policy with additional parameters."""
        staking_params = self.registry.get_parameters_by_category(ParameterCategory.STAKING)
        
        def p_enhanced_staking(params, substep, state_history, prev_state):
            """Enhanced staking policy with revenue sharing and multipliers."""
            # Get enhanced staking parameters with safe access
            staker_rev_share = 0.25  # Default 25%
            
            # Try runtime parameters first, then registry
            if "staker_rev_share" in params:
                staker_rev_share = params["staker_rev_share"] / 100.0 if params["staker_rev_share"] is not None else 0.25
            elif "staker_rev_share" in staking_params:
                registry_value = staking_params["staker_rev_share"].value
                staker_rev_share = registry_value / 100.0 if registry_value is not None else 0.25
            
            # Calculate staking rewards with revenue sharing
            circulating_supply = prev_state["circulating_supply"]
            
            # Estimate revenue (simplified)
            monthly_revenue = circulating_supply * 0.001  # 0.1% of supply as revenue
            staking_rewards = monthly_revenue * staker_rev_share
            
            return {"staking_rewards": staking_rewards}
        
        return p_enhanced_staking
    
    def _create_ve_emissions_policy(self, data) -> Callable:
        """Create VE emissions policy."""
        # Get VE emissions parameters
        ve_params = self.registry.get_parameters_by_category(ParameterCategory.VE_EMISSIONS)
        
        def p_ve_emissions(params, substep, state_history, prev_state):
            """Policy function for VE emissions."""
            time_step = prev_state["time_step"]
            
            # Create VE emissions configuration from parameters
            ve_config_params = {}
            
            # Map registry parameters to VE config
            param_mapping = {
                'total_ion_emitted': 'total_emissions_budget',
                'base_monthly_emissions_rate': 'base_monthly_rate',
                'borrowed_step_size': 'borrowed_step_size',
                'emissions_step_up': 'emissions_step_up',
                'target_utilization_rate': 'target_utilization_rate',
                'tvl': 'initial_tvl',
                'final_tvl': 'final_tvl',
                'borrow': 'initial_borrow',
                'final_borrowed': 'final_borrow',
                'protocol_fee': 'protocol_fee',
                'token_price': 'token_price',
                'mom_tvl_growth': 'monthly_tvl_growth',
                'mom_borrow_growth': 'monthly_borrow_growth'
            }
            
            # Extract parameters from registry and runtime params
            for registry_key, config_key in param_mapping.items():
                if registry_key in params:
                    ve_config_params[config_key] = params[registry_key]
                elif registry_key in ve_params:
                    ve_config_params[config_key] = ve_params[registry_key].value
            
            # Create VE emissions model if we have sufficient parameters
            if len(ve_config_params) > 5:
                try:
                    config = create_ve_emissions_config_from_params(ve_config_params)
                    ve_model = VEEmissionsModel(config)
                    
                    # Generate time series data
                    time_series = ve_model.generate_time_series()
                    
                    # Get emissions for current time step
                    if time_step < len(time_series):
                        current_data = time_series.iloc[time_step]
                        
                        return {
                            "ve_emissions_per_month": current_data['emissions_per_month'],
                            "ve_cumulative_emissions": current_data['cumulative_emissions'],
                            "ve_protocol_revenue": current_data['protocol_revenue'],
                            "ve_revenue_emissions_ratio": current_data['revenue_to_emissions_ratio'],
                            "ve_tvl": current_data['tvl'],
                            "ve_borrow_amount": current_data['borrow_amount'],
                            "ve_utilization_rate": current_data['utilization_rate'],
                            "ve_emission_step": current_data['emission_step']
                        }
                except Exception as e:
                    # If VE model fails, return zeros
                    pass
            
            # Default return if no VE emissions
            return {
                "ve_emissions_per_month": 0,
                "ve_cumulative_emissions": 0,
                "ve_protocol_revenue": 0,
                "ve_revenue_emissions_ratio": 0,
                "ve_tvl": 0,
                "ve_borrow_amount": 0,
                "ve_utilization_rate": 0,
                "ve_emission_step": 0
            }
        
        return p_ve_emissions
    
    def _create_agent_influenced_price_policy(self, data) -> Callable:
        """Create agent-influenced price policy that incorporates agent behavior."""
        agent_params = self.registry.get_parameters_by_category(ParameterCategory.AGENT_BEHAVIOR)
        pricing_params = self.registry.get_parameters_by_category(ParameterCategory.PRICING)
        
        def p_agent_influenced_price(params, substep, state_history, prev_state):
            """Price policy influenced by agent behaviors and market dynamics."""
            current_price = prev_state["token_price"]
            
            # Base market volatility
            market_volatility = params.get("market_volatility", 0.2)
            if "market_volatility" in pricing_params:
                market_volatility = pricing_params["market_volatility"].value
                
            # Agent behavior influences
            speculation_factor = 0.5  # Default
            liquidity_factor = 0.0001  # Default
            avg_trading_fund_usage = 0.1  # Default
            
            # Extract agent parameters
            if "speculation_factor" in params:
                speculation_factor = params["speculation_factor"]
            elif "speculation_factor" in agent_params:
                speculation_factor = agent_params["speculation_factor"].value
                
            if "liquidity_factor" in params:
                liquidity_factor = params["liquidity_factor"]
            elif "liquidity_factor" in agent_params:
                liquidity_factor = agent_params["liquidity_factor"].value
                
            if "avg_trading_fund_usage" in params:
                avg_trading_fund_usage = params["avg_trading_fund_usage"]
            elif "avg_trading_fund_usage" in agent_params:
                avg_trading_fund_usage = agent_params["avg_trading_fund_usage"].value
            
            # Calculate price influences
            staked_ratio = prev_state["staked_tokens"] / prev_state["circulating_supply"] if prev_state["circulating_supply"] > 0 else 0
            
            # Base price movement from staking ratio (reduces selling pressure)
            staking_influence = 1 + (staked_ratio - 0.5) * 0.1
            
            # Agent trading pressure (higher usage = more volatility)
            trading_pressure = 1 + (avg_trading_fund_usage - 0.1) * 0.2
            
            # Speculation influence
            speculation_influence = 1 + (random.random() - 0.5) * speculation_factor * 0.3
            
            # Liquidity influence (lower liquidity = higher impact)
            liquidity_impact = 1 + (1 - liquidity_factor * 10000) * 0.05
            
            # Market volatility (base random movement)
            random_factor = 1 + (random.random() - 0.5) * market_volatility
            
            # Combine all influences
            total_multiplier = staking_influence * trading_pressure * speculation_influence * liquidity_impact * random_factor
            
            new_price = current_price * total_multiplier
            new_price = max(new_price, 0.001)  # Price floor
            
            # Cap price changes to prevent extreme movements
            max_change_pct = params.get("max_price_change_pct", 0.1)
            if "max_price_change_pct" in agent_params:
                max_change_pct = agent_params["max_price_change_pct"].value
                
            max_price = current_price * (1 + max_change_pct)
            min_price = current_price * (1 - max_change_pct)
            new_price = max(min_price, min(new_price, max_price))
            
            return {"price_delta": new_price - current_price}
        
        return p_agent_influenced_price
    
    def create_state_updates(self) -> Dict[str, Callable]:
        """Create state update functions that work with dynamic policies."""
        return {
            'circulating_supply': self._s_update_supply,
            'staked_tokens': self._s_update_staking,
            'effective_circulating_supply': self._s_update_effective_supply,
            'token_price': self._s_update_price,
            'market_cap': self._s_update_market_cap,
            'time_step': self._s_update_time,
            'total_points_issued': self._s_update_points_issued,
            'total_tokens_converted': self._s_update_tokens_converted,
            'total_tokens_burned': self._s_update_tokens_burned,
            'staking_rewards': self._s_update_staking_rewards,
            've_emissions_per_month': self._s_update_ve_emissions_per_month,
            've_cumulative_emissions': self._s_update_ve_cumulative_emissions,
            've_protocol_revenue': self._s_update_ve_protocol_revenue,
            've_revenue_emissions_ratio': self._s_update_ve_revenue_emissions_ratio,
            've_tvl': self._s_update_ve_tvl,
            've_borrow_amount': self._s_update_ve_borrow_amount,
            've_utilization_rate': self._s_update_ve_utilization_rate,
            've_emission_step': self._s_update_ve_emission_step
        }
    
    def _s_update_supply(self, params, substep, state_history, prev_state, policy_input):
        """State update function for circulating supply."""
        newly_vested = policy_input.get("newly_vested", 0)
        tokens_converted = policy_input.get("tokens_converted", 0)
        tokens_burned = policy_input.get("tokens_burned", 0)
        
        new_supply = prev_state["circulating_supply"] + newly_vested + tokens_converted - tokens_burned
        return ("circulating_supply", max(0, new_supply))
    
    def _s_update_staking(self, params, substep, state_history, prev_state, policy_input):
        """State update function for staked tokens."""
        staking_delta = policy_input.get("staking_delta", 0)
        tokens_locked = policy_input.get("tokens_locked", 0)
        
        new_staked = prev_state["staked_tokens"] + staking_delta + tokens_locked
        # Ensure staked tokens don't exceed circulating supply
        max_staked = prev_state["circulating_supply"]
        return ("staked_tokens", max(0, min(new_staked, max_staked)))
    
    def _s_update_effective_supply(self, params, substep, state_history, prev_state, policy_input):
        """State update function for effective circulating supply."""
        new_effective = prev_state["circulating_supply"] - prev_state["staked_tokens"]
        return ("effective_circulating_supply", max(0, new_effective))
    
    def _s_update_price(self, params, substep, state_history, prev_state, policy_input):
        """State update function for token price."""
        price_delta = policy_input.get("price_delta", 0)
        new_price = prev_state["token_price"] + price_delta
        return ("token_price", max(0.001, new_price))  # Price floor
    
    def _s_update_market_cap(self, params, substep, state_history, prev_state, policy_input):
        """State update function for market cap."""
        market_cap = prev_state["circulating_supply"] * prev_state["token_price"]
        return ("market_cap", market_cap)
    
    def _s_update_time(self, params, substep, state_history, prev_state, policy_input):
        """State update function for time step."""
        return ("time_step", prev_state["time_step"] + 1)
    
    def _s_update_points_issued(self, params, substep, state_history, prev_state, policy_input):
        """State update function for points issued."""
        points_issued = policy_input.get("points_issued", 0)
        current_points = prev_state.get("total_points_issued", 0)
        return ("total_points_issued", current_points + points_issued)
    
    def _s_update_tokens_converted(self, params, substep, state_history, prev_state, policy_input):
        """State update function for tokens converted from points."""
        tokens_converted = policy_input.get("tokens_converted", 0)
        current_converted = prev_state.get("total_tokens_converted", 0)
        return ("total_tokens_converted", current_converted + tokens_converted)
    
    def _s_update_tokens_burned(self, params, substep, state_history, prev_state, policy_input):
        """State update function for tokens burned."""
        tokens_burned = policy_input.get("tokens_burned", 0)
        current_burned = prev_state.get("total_tokens_burned", 0)
        return ("total_tokens_burned", current_burned + tokens_burned)
    
    def _s_update_staking_rewards(self, params, substep, state_history, prev_state, policy_input):
        """State update function for staking rewards."""
        staking_rewards = policy_input.get("staking_rewards", 0)
        current_rewards = prev_state.get("staking_rewards", 0)
        return ("staking_rewards", current_rewards + staking_rewards)
    
    def _s_update_ve_emissions_per_month(self, params, substep, state_history, prev_state, policy_input):
        """State update function for VE emissions per month."""
        ve_emissions_per_month = policy_input.get("ve_emissions_per_month", 0)
        current_ve_emissions_per_month = prev_state.get("ve_emissions_per_month", 0)
        return ("ve_emissions_per_month", current_ve_emissions_per_month + ve_emissions_per_month)
    
    def _s_update_ve_cumulative_emissions(self, params, substep, state_history, prev_state, policy_input):
        """State update function for VE cumulative emissions."""
        ve_cumulative_emissions = policy_input.get("ve_cumulative_emissions", 0)
        current_ve_cumulative_emissions = prev_state.get("ve_cumulative_emissions", 0)
        return ("ve_cumulative_emissions", current_ve_cumulative_emissions + ve_cumulative_emissions)
    
    def _s_update_ve_protocol_revenue(self, params, substep, state_history, prev_state, policy_input):
        """State update function for VE protocol revenue."""
        ve_protocol_revenue = policy_input.get("ve_protocol_revenue", 0)
        current_ve_protocol_revenue = prev_state.get("ve_protocol_revenue", 0)
        return ("ve_protocol_revenue", current_ve_protocol_revenue + ve_protocol_revenue)
    
    def _s_update_ve_revenue_emissions_ratio(self, params, substep, state_history, prev_state, policy_input):
        """State update function for VE revenue-to-emissions ratio."""
        ve_revenue_emissions_ratio = policy_input.get("ve_revenue_emissions_ratio", 0)
        current_ve_revenue_emissions_ratio = prev_state.get("ve_revenue_emissions_ratio", 0)
        return ("ve_revenue_emissions_ratio", current_ve_revenue_emissions_ratio + ve_revenue_emissions_ratio)
    
    def _s_update_ve_tvl(self, params, substep, state_history, prev_state, policy_input):
        """State update function for VE TVL."""
        ve_tvl = policy_input.get("ve_tvl", 0)
        current_ve_tvl = prev_state.get("ve_tvl", 0)
        return ("ve_tvl", current_ve_tvl + ve_tvl)
    
    def _s_update_ve_borrow_amount(self, params, substep, state_history, prev_state, policy_input):
        """State update function for VE borrow amount."""
        ve_borrow_amount = policy_input.get("ve_borrow_amount", 0)
        current_ve_borrow_amount = prev_state.get("ve_borrow_amount", 0)
        return ("ve_borrow_amount", current_ve_borrow_amount + ve_borrow_amount)
    
    def _s_update_ve_utilization_rate(self, params, substep, state_history, prev_state, policy_input):
        """State update function for VE utilization rate."""
        ve_utilization_rate = policy_input.get("ve_utilization_rate", 0)
        current_ve_utilization_rate = prev_state.get("ve_utilization_rate", 0)
        return ("ve_utilization_rate", current_ve_utilization_rate + ve_utilization_rate)
    
    def _s_update_ve_emission_step(self, params, substep, state_history, prev_state, policy_input):
        """State update function for VE emission step."""
        ve_emission_step = policy_input.get("ve_emission_step", 0)
        current_ve_emission_step = prev_state.get("ve_emission_step", 0)
        return ("ve_emission_step", current_ve_emission_step + ve_emission_step)


def create_policy_factory(registry: ParameterRegistry) -> PolicyFactory:
    """Factory function to create a policy factory."""
    return PolicyFactory(registry) 