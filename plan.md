# Unit Zero Labs Tokenomics Engine Standardization Plan

## Executive Summary

The current repo is over-engineered for a single client. The system has strong foundations but lacks the standardized framework needed for rapid client onboarding.

## Current Architecture Analysis

### Strengths
- **Parameter-First Design**: Dynamic parameter discovery and UI generation
- **Modular Policy System**: Extensible policy factory for custom behaviors
- **Monte Carlo Capabilities**: Statistical analysis with confidence intervals
- **Agent-Based Modeling**: Basic agent types (RandomTrader, TrendFollower, StakingAgent)

### Critical Issues
1. **Over-Coupling**: Hardcoded references to specific client needs (VE emissions, specific parameter names)
2. **Limited Liquidity Pool Models**: Only basic liquidity pool handling, no sophisticated AMM models
3. **Inflexible Agent System**: Simple agents without proper liquidity pool interaction
4. **No Client Configuration System**: Single global configuration instead of client-specific configs
5. **Monolithic Structure**: No clear separation between framework and client-specific implementations

## Standardization Roadmap

### 1. Standardize the Simulation Process

#### A. Core Framework Restructure
```
sim-systems/
├── framework/                    # Standardized simulation framework
│   ├── core/
│   │   ├── simulation_engine.py  # Base simulation engine
│   │   ├── state_manager.py      # Enhanced state management
│   │   └── policy_registry.py    # Policy registration system
│   ├── liquidity_pools/          # Liquidity pool models library
│   │   ├── base_pool.py          # Abstract base class
│   │   ├── uniswap_v2.py         # Uniswap v2 constant product
│   │   ├── uniswap_v3.py         # Concentrated liquidity
│   │   ├── curve.py              # Stableswap AMM
│   │   ├── velodrome.py          # Vote-escrow model
│   │   └── balancer.py           # Weighted pools
│   ├── agents/                   # Enhanced agent system
│   │   ├── base_agent.py         # Abstract agent base
│   │   ├── liquidity_providers/  # LP-specific agents
│   │   ├── traders/              # Trading agents
│   │   └── arbitrageurs/         # MEV/arbitrage agents
│   └── validators/               # Quality control system
├── clients/                      # Client-specific configurations
│   ├── xeta/
│   │   ├── client_xeta.yaml      # Configuration file
│   │   ├── custom_policies.py    # Client-specific policies
│   │   └── custom_agents.py      # Client-specific agents
│   └── template/                 # Template for new clients
└── reports/                      # Automated reporting system
```

#### B. Simulation Engine Standardization
```python
class StandardizedSimulationEngine:
    """
    Standardized simulation engine that adapts to client configurations
    while maintaining consistent quality and performance standards.
    """
    
    def __init__(self, client_config: ClientConfig):
        self.client_config = client_config
        self.liquidity_pool_factory = LiquidityPoolFactory()
        self.agent_factory = AgentFactory()
        self.policy_registry = PolicyRegistry()
        self.quality_validator = QualityValidator()
    
    def initialize_simulation(self, parameters: Dict[str, Any]):
        """Initialize simulation with client-specific configuration."""
        # Load client-specific liquidity pool model
        pool_model = self.liquidity_pool_factory.create_pool(
            pool_type=self.client_config.liquidity_pool_type,
            parameters=parameters
        )
        
        # Initialize agents based on client requirements
        agents = self.agent_factory.create_agent_ecosystem(
            config=self.client_config.agent_config,
            pool_model=pool_model
        )
        
        # Validate configuration quality
        self.quality_validator.validate_setup(pool_model, agents, parameters)
        
        return SimulationContext(pool_model, agents, parameters)
```

### 2. Configuration-Driven Modeling

#### A. Client Configuration System
```yaml
# clients/xeta/client_xeta.yaml
client:
  name: "XETA"
  version: "1.0.0"
  description: "XETA Protocol Tokenomics Model"

liquidity_pools:
  primary_model: "uniswap_v3"
  secondary_models: ["curve_stable"]
  parameters:
    fee_tier: 0.003
    tick_spacing: 60
    price_range: 0.2

agents:
  enabled_types:
    - "sophisticated_lp"
    - "momentum_trader" 
    - "arbitrageur"
  populations:
    sophisticated_lp: 50
    momentum_trader: 100
    arbitrageur: 25

tokenomics:
  total_supply: 1000000000
  initial_price: 0.05
  vesting_schedules:
    team: "linear_36_months"
    public: "cliff_6_linear_18"

simulation:
  default_timesteps: 120
  monte_carlo_runs: 100
  quality_checks:
    - "liquidity_depth_validation"
    - "price_impact_bounds"
    - "agent_behavior_realism"

reporting:
  template: "institutional_grade"
  metrics:
    - "liquidity_efficiency"
    - "price_stability"
    - "tokenomics_health"
```

#### B. Liquidity Pool Model Library
```python
class LiquidityPoolFactory:
    """Factory for creating different types of liquidity pool models."""
    
    POOL_MODELS = {
        "uniswap_v2": UniswapV2Pool,
        "uniswap_v3": UniswapV3Pool,
        "curve_stable": CurveStablePool,
        "velodrome": VelodromePool,
        "balancer_weighted": BalancerWeightedPool
    }
    
    def create_pool(self, pool_type: str, parameters: Dict[str, Any]) -> BaseLiquidityPool:
        """Create a liquidity pool model with rigorous mathematical implementation."""
        if pool_type not in self.POOL_MODELS:
            raise ValueError(f"Unsupported pool type: {pool_type}")
        
        pool_class = self.POOL_MODELS[pool_type]
        return pool_class(parameters)

class UniswapV3Pool(BaseLiquidityPool):
    """
    Rigorous Uniswap V3 concentrated liquidity implementation.
    Includes tick-based pricing, fee calculations, and IL modeling.
    """
    
    def __init__(self, parameters: Dict[str, Any]):
        super().__init__(parameters)
        self.tick_spacing = parameters.get("tick_spacing", 60)
        self.fee_tier = parameters.get("fee_tier", 0.003)
        self.active_liquidity = 0
        self.tick_data = {}
    
    def calculate_price_impact(self, swap_amount: float, direction: str) -> float:
        """Calculate price impact using concentrated liquidity math."""
        # Implement rigorous Uniswap V3 price impact calculation
        pass
    
    def update_liquidity_positions(self, positions: List[LiquidityPosition]):
        """Update liquidity positions and recalculate active liquidity."""
        # Implement tick-based liquidity updates
        pass

class VelodromePool(BaseLiquidityPool):
    """
    Velodrome vote-escrow liquidity pool with emissions and bribes.
    """
    
    def __init__(self, parameters: Dict[str, Any]):
        super().__init__(parameters)
        self.ve_rewards_rate = parameters.get("ve_rewards_rate", 0.02)
        self.bribe_multiplier = parameters.get("bribe_multiplier", 1.5)
    
    def calculate_ve_rewards(self, lp_tokens: float, ve_power: float) -> float:
        """Calculate vote-escrow reward distribution."""
        # Implement Velodrome-specific reward math
        pass
```

### 3. Enhanced Agent System for Liquidity Pool Modeling

#### A. Sophisticated Agent Architecture
```python
class LiquidityProvider(Agent):
    """Sophisticated liquidity provider with risk management."""
    
    def __init__(self, agent_id: int, initial_capital: float, risk_tolerance: float):
        super().__init__(agent_id, initial_capital)
        self.risk_tolerance = risk_tolerance
        self.positions = []
        self.pnl_history = []
        self.impermanent_loss_threshold = 0.05
    
    def decide_liquidity_provision(self, pool: BaseLiquidityPool, market_state: Dict[str, Any]) -> LiquidityDecision:
        """Make sophisticated LP decisions based on expected returns and IL risk."""
        # Calculate expected returns vs impermanent loss
        expected_fees = self.estimate_fee_returns(pool, market_state)
        expected_il = self.estimate_impermanent_loss(pool, market_state)
        
        # Risk-adjusted decision making
        if expected_fees > expected_il * (1 + self.risk_tolerance):
            return self.optimize_position_size(pool, market_state)
        else:
            return LiquidityDecision("withdraw", self.calculate_exit_strategy())

class ArbitrageAgent(Agent):
    """MEV-aware arbitrage agent for cross-pool opportunities."""
    
    def __init__(self, agent_id: int, capital: float, gas_sensitivity: float):
        super().__init__(agent_id, capital)
        self.gas_sensitivity = gas_sensitivity
        self.min_profit_threshold = 0.001  # 0.1% minimum profit
    
    def scan_arbitrage_opportunities(self, pools: List[BaseLiquidityPool]) -> List[ArbitrageOpportunity]:
        """Scan for profitable arbitrage opportunities across pools."""
        opportunities = []
        for pool_a, pool_b in combinations(pools, 2):
            price_diff = abs(pool_a.get_price() - pool_b.get_price())
            if price_diff > self.min_profit_threshold:
                opportunity = self.calculate_arbitrage_profit(pool_a, pool_b)
                if opportunity.net_profit > 0:
                    opportunities.append(opportunity)
        return sorted(opportunities, key=lambda x: x.net_profit, reverse=True)
```

### 4. Reporting and Visualization System

#### A. Automated Quality Control
```python
class QualityValidator:
    """Automated quality control for simulation outputs."""
    
    def validate_liquidity_depth(self, pool: BaseLiquidityPool, results: pd.DataFrame) -> ValidationResult:
        """Validate that liquidity depth remains realistic."""
        min_liquidity = pool.initial_liquidity * 0.1  # 10% minimum
        liquidity_violations = results[results['liquidity'] < min_liquidity]
        
        return ValidationResult(
            passed=len(liquidity_violations) == 0,
            metric="liquidity_depth",
            violations=len(liquidity_violations),
            recommendation="Adjust agent behavior or initial conditions"
        )
    
    def validate_price_stability(self, results: pd.DataFrame) -> ValidationResult:
        """Validate price movements are within realistic bounds."""
        price_changes = results['token_price'].pct_change()
        extreme_moves = price_changes[abs(price_changes) > 0.5]  # 50% moves
        
        return ValidationResult(
            passed=len(extreme_moves) == 0,
            metric="price_stability", 
            violations=len(extreme_moves),
            recommendation="Review market volatility parameters"
        )

class ProfessionalReportGenerator:
    """Generate institutional-grade reports."""
    
    def generate_executive_summary(self, client_config: ClientConfig, results: SimulationResults) -> ExecutiveSummary:
        """Generate executive summary with key insights."""
        return ExecutiveSummary(
            client_name=client_config.name,
            simulation_period=results.timespan,
            key_metrics=self.extract_key_metrics(results),
            risk_assessment=self.assess_risks(results),
            recommendations=self.generate_recommendations(results)
        )
```

#### B. Client Dashboard Selection
```python
# Enhanced app.py structure
def main():
    st.set_page_config(page_title="Unit Zero Labs - Tokenomics Engine")
    
    # Client selection at the top level
    st.sidebar.header("Client Configuration")
    available_clients = load_available_clients()
    
    if not available_clients:
        st.error("No client configurations found. Please set up client configs.")
        return
    
    selected_client = st.sidebar.selectbox(
        "Select Client Configuration",
        options=available_clients,
        format_func=lambda x: f"{x.name} - {x.description}"
    )
    
    # Load client-specific configuration
    client_config = load_client_config(selected_client)
    
    # Initialize simulation engine with client config
    simulation_engine = StandardizedSimulationEngine(client_config)
    
    # Display client-specific liquidity pool options
    st.sidebar.subheader("Liquidity Pool Model")
    pool_type = st.sidebar.selectbox(
        "Select Pool Type",
        options=client_config.available_pool_types,
        help="Choose the liquidity pool model for simulation"
    )
    
    # Rest of the application adapts to client configuration
    run_client_simulation(simulation_engine, client_config, pool_type)
```

## Implementation Priority

### Phase 1: Framework Foundation 
1. **Restructure codebase** with framework/clients separation
2. **Implement base liquidity pool classes** with mathematical rigor
3. **Create client configuration system** with YAML-based configs
4. **Build quality validation framework**

### Phase 2: Enhanced Modeling 
1. **Implement Uniswap V2/V3 models** with proper AMM math
2. **Add Curve and Balancer pool models**
3. **Enhance agent system** with sophisticated LP and arbitrage agents
4. **Create automated testing suite**

### Phase 3: Professional Deliverables 
1. **Build reporting system** with institutional-grade outputs
2. **Create client onboarding templates**
3. **Implement dashboard selection system**
4. **Add performance benchmarking**

## Key Benefits

1. **Rapid Client Onboarding**: New clients can be onboarded in days, not weeks
2. **Rigorous Mathematics**: Each liquidity pool model implements proper AMM mathematics
3. **Quality Assurance**: Automated validation ensures professional-grade outputs
4. **Scalable Architecture**: Framework scales from 1 to 100+ clients seamlessly
5. **Competitive Differentiation**: Sophisticated modeling capabilities set apart from basic tools

This standardization approach transforms the current client-specific tool into a commercial-grade platform while maintaining the flexibility to create bespoke models for each client's unique requirements.