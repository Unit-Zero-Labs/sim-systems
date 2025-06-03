"""
Parameter registry system for dynamic parameter discovery and policy configuration.
Enables parameter-first design for client-specific tokenomics simulations.
"""

import pandas as pd
import streamlit as st
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import re


class ParameterType(Enum):
    """Types of parameters for automatic UI generation."""
    NUMERIC = "numeric"
    PERCENTAGE = "percentage"
    DATE = "date"
    STRING = "string"
    BOOLEAN = "boolean"
    SELECTION = "selection"


class ParameterCategory(Enum):
    """Categories for grouping parameters in UI."""
    TOKENOMICS = "tokenomics"
    VESTING = "vesting"
    STAKING = "staking"
    PRICING = "pricing"
    ADOPTION = "adoption"
    POINTS_CAMPAIGN = "points_campaign"
    AGENT_BEHAVIOR = "agent_behavior"
    UTILITY = "utility"
    FINANCIAL = "financial"
    VE_EMISSIONS = "ve_emissions"
    CUSTOM = "custom"


@dataclass
class ParameterDefinition:
    """Definition of a parameter with metadata for UI generation and validation."""
    name: str
    value: Any
    param_type_str: str  # Store as string for pickle compatibility
    category_str: str    # Store as string for pickle compatibility
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    format_str: Optional[str] = None
    help_text: Optional[str] = None
    options: Optional[List[str]] = None
    is_configurable: bool = True
    policy_consumer: Optional[str] = None
    
    @property
    def param_type(self) -> ParameterType:
        """Get the parameter type as enum."""
        return ParameterType(self.param_type_str)
    
    @property
    def category(self) -> ParameterCategory:
        """Get the parameter category as enum."""
        return ParameterCategory(self.category_str)


class ParameterRegistry:
    """
    Registry for managing and categorizing parameters from CSV inputs.
    Enables dynamic UI generation and policy configuration.
    """
    
    def __init__(self):
        self.parameters: Dict[str, ParameterDefinition] = {}
        self.category_patterns = self._setup_category_patterns()
        self.type_patterns = self._setup_type_patterns()
        
    def _setup_category_patterns(self) -> Dict[ParameterCategory, List[str]]:
        """Setup regex patterns for automatic parameter categorization."""
        return {
            ParameterCategory.TOKENOMICS: [
                r'.*total.*supply.*', r'.*allocation.*', r'.*token.*count.*'
            ],
            ParameterCategory.VESTING: [
                r'.*vesting.*', r'.*cliff.*', r'.*duration.*', r'.*initial.*vesting.*'
            ],
            ParameterCategory.STAKING: [
                r'.*stak.*', r'.*apr.*', r'.*reward.*', r'.*lock.*'
            ],
            ParameterCategory.PRICING: [
                r'.*price.*', r'.*valuation.*', r'.*market.*cap.*', r'.*volatility.*'
            ],
            ParameterCategory.ADOPTION: [
                r'.*user.*', r'.*adoption.*', r'.*growth.*', r'.*velocity.*'
            ],
            ParameterCategory.POINTS_CAMPAIGN: [
                r'.*point.*', r'.*campaign.*', r'.*stage.*', r'.*conversion.*', 
                r'.*awareness.*', r'.*presale.*', r'.*multiplier.*'
            ],
            ParameterCategory.AGENT_BEHAVIOR: [
                r'.*agent.*', r'.*trader.*', r'.*behavior.*', r'.*factor.*',
                r'.*random.*trader.*', r'.*trend.*follow.*', r'.*staking.*agent.*',
                r'.*trading.*fund.*usage.*', r'.*token.*lock.*', r'.*liquidity.*factor.*',
                r'.*speculation.*factor.*', r'.*max.*price.*change.*', r'.*min.*token.*price.*',
                r'.*random_trader.*', r'.*trend_follower.*', r'.*staking_agent.*',
                r'.*agent_.*', r'.*trading_.*', r'.*market_.*behavior.*'
            ],
            ParameterCategory.UTILITY: [
                r'.*utility.*', r'.*burn.*', r'.*transfer.*', r'.*incentiv.*'
            ],
            ParameterCategory.FINANCIAL: [
                r'.*income.*', r'.*revenue.*', r'.*cost.*', r'.*expense.*', r'.*cash.*'
            ],
            ParameterCategory.VE_EMISSIONS: [
                r'.*emission.*', r'.*emitted.*', r'.*tvl.*', r'.*total.*value.*locked.*',
                r'.*borrow.*', r'.*utilization.*', r'.*step.*', r'.*revenue.*',
                r'.*protocol.*fee.*', r'.*admin.*fee.*', r'.*reserve.*fee.*',
                r'.*liquidation.*fee.*', r'.*vetoken.*', r'.*ve.*token.*',
                r'.*base.*.*rate.*', r'.*multiplier.*', r'.*kink.*', r'.*jump.*',
                r'.*growth.*', r'.*final.*', r'.*target.*', r'.*borrowed.*step.*size.*',
                r'.*emissions.*step.*up.*', r'.*monthly.*emissions.*rate.*',
                r'.*weekly.*emissions.*rate.*', r'.*lender.*', r'.*blocks.*per.*'
            ]
        }
    
    def _setup_type_patterns(self) -> Dict[ParameterType, List[str]]:
        """Setup patterns for automatic parameter type detection."""
        return {
            ParameterType.PERCENTAGE: [r'.*perc.*', r'.*share.*', r'.*ratio.*', r'.*%.*'],
            ParameterType.DATE: [r'.*date.*', r'.*launch.*', r'.*start.*', r'.*end.*'],
            ParameterType.BOOLEAN: [r'.*flag.*', r'.*enable.*', r'.*allow.*', r'.*use.*']
        }
    
    def register_parameters_from_csv(self, csv_params: Dict[str, Any]) -> None:
        """
        Register parameters from CSV data with automatic categorization and type detection.
        
        Args:
            csv_params: Dictionary of parameters from CSV
        """
        for param_name, param_value in csv_params.items():
            param_def = self._create_parameter_definition(param_name, param_value)
            self.parameters[param_name] = param_def
            
    def _create_parameter_definition(self, name: str, value: Any) -> ParameterDefinition:
        """Create a parameter definition with automatic categorization and type detection."""
        param_type = self._detect_parameter_type(name, value)
        category = self._detect_parameter_category(name)
        
        # Set up bounds and formatting based on type
        min_val, max_val, step, format_str = self._get_type_constraints(param_type, value)
        
        # Generate help text
        help_text = self._generate_help_text(name, param_type, category)
        
        return ParameterDefinition(
            name=name,
            value=value,
            param_type_str=param_type.value,
            category_str=category.value,
            min_value=min_val,
            max_value=max_val,
            step=step,
            format_str=format_str,
            help_text=help_text,
            is_configurable=self._is_configurable_parameter(name)
        )
    
    def _detect_parameter_type(self, name: str, value: Any) -> ParameterType:
        """Detect parameter type from name and value."""
        name_lower = name.lower()
        
        # Check type patterns
        for param_type, patterns in self.type_patterns.items():
            if any(re.match(pattern, name_lower) for pattern in patterns):
                return param_type
        
        # Check value type
        if isinstance(value, bool):
            return ParameterType.BOOLEAN
        elif isinstance(value, str):
            if pd.api.types.is_datetime64_any_dtype(pd.Series([value])):
                return ParameterType.DATE
            return ParameterType.STRING
        elif isinstance(value, (int, float)):
            # Check if it's a percentage (between 0 and 1, or has % in name)
            if 0 <= value <= 1 and any(keyword in name_lower for keyword in ['perc', 'share', 'ratio']):
                return ParameterType.PERCENTAGE
            return ParameterType.NUMERIC
        
        return ParameterType.NUMERIC  # Default
    
    def _detect_parameter_category(self, name: str) -> ParameterCategory:
        """Detect parameter category from name patterns."""
        name_lower = name.lower()
        
        for category, patterns in self.category_patterns.items():
            if any(re.match(pattern, name_lower) for pattern in patterns):
                return category
                
        return ParameterCategory.CUSTOM
    
    def _get_type_constraints(self, param_type: ParameterType, value: Any) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]:
        """Get constraints and formatting for parameter type."""
        if param_type == ParameterType.PERCENTAGE:
            return 0.0, 1.0, 0.01, "%.2f"
        elif param_type == ParameterType.NUMERIC:
            if isinstance(value, (int, float)) and value > 0:
                return 0.0, float(value) * 10.0, max(float(value) * 0.01, 1.0), None
            return None, None, None, None
        return None, None, None, None
    
    def _generate_help_text(self, name: str, param_type: ParameterType, category: ParameterCategory) -> str:
        """Generate helpful description for parameter."""
        base_descriptions = {
            ParameterCategory.POINTS_CAMPAIGN: "Parameter for off-chain points campaign configuration",
            ParameterCategory.STAKING: "Staking mechanism parameter",
            ParameterCategory.VESTING: "Token vesting schedule parameter",
            ParameterCategory.PRICING: "Token pricing and valuation parameter",
            ParameterCategory.ADOPTION: "User adoption and growth parameter"
        }
        
        base = base_descriptions.get(category, f"{category.value.replace('_', ' ').title()} parameter")
        return f"{base}: {name}"
    
    def _is_configurable_parameter(self, name: str) -> bool:
        """Determine if parameter should be configurable in UI."""
        # Some parameters shouldn't be user-configurable
        non_configurable = ['initial_total_supply', 'launch_date']
        return name not in non_configurable
    
    def get_parameters_by_category(self, category: ParameterCategory) -> Dict[str, ParameterDefinition]:
        """Get all parameters in a specific category."""
        return {name: param for name, param in self.parameters.items() 
                if param.category == category}
    
    def get_configurable_parameters(self) -> Dict[str, ParameterDefinition]:
        """Get all user-configurable parameters."""
        return {name: param for name, param in self.parameters.items() 
                if param.is_configurable}
    
    def discover_new_policies(self) -> List[str]:
        """
        Discover what new policies should be created based on available parameters.
        
        Returns:
            List of policy names that should be implemented
        """
        discovered_policies = []
        
        # Check for points campaign parameters
        points_params = self.get_parameters_by_category(ParameterCategory.POINTS_CAMPAIGN)
        if points_params:
            discovered_policies.append("points_campaign")
            
        # Check for custom agent behavior parameters
        agent_params = self.get_parameters_by_category(ParameterCategory.AGENT_BEHAVIOR)
        if any('custom' in name.lower() for name in agent_params.keys()):
            discovered_policies.append("custom_agent_behavior")
            
        # Check for custom utility mechanisms
        utility_params = self.get_parameters_by_category(ParameterCategory.UTILITY)
        if utility_params:
            discovered_policies.append("custom_utility")
            
        return discovered_policies
    
    def validate_parameter_coverage(self, consumed_params: List[str]) -> Tuple[List[str], List[str]]:
        """
        Validate that all loaded parameters are being consumed by policies.
        
        Args:
            consumed_params: List of parameter names actually used by policies
            
        Returns:
            Tuple of (unused_parameters, missing_parameters)
        """
        all_param_names = set(self.parameters.keys())
        consumed_set = set(consumed_params)
        
        unused = list(all_param_names - consumed_set)
        missing = list(consumed_set - all_param_names)
        
        return unused, missing


# Global registry instance
parameter_registry = ParameterRegistry() 