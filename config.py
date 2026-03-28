"""System configuration and constants."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class SystemConfig:
    """Configuration for the EV charging management system."""
    
    # Grid constraints
    transformer_capacity_kw: float = 500.0  # Maximum transformer capacity
    max_grid_load_percent: float = 80.0     # Maximum allowed grid load percentage
    
    # Charging station parameters
    num_stations: int = 10
    station_power_kw: float = 50.0          # Power per charging station
    
    # Time parameters
    time_slots: int = 24                     # Hourly slots in a day
    slot_duration_hours: float = 1.0
    
    # PSO parameters
    num_particles: int = 50
    max_iterations: int = 100
    w_inertia: float = 0.7                  # Inertia weight
    c1_cognitive: float = 1.5               # Cognitive coefficient
    c2_social: float = 1.5                  # Social coefficient
    
    # Optimization weights
    weight_grid_overload: float = 0.4
    weight_solar_usage: float = 0.35
    weight_fairness: float = 0.25
    
    # Priority weights for vehicle scoring
    priority_weights: dict = field(default_factory=lambda: {
        'battery_level': 0.3,
        'urgency': 0.25,
        'wait_time': 0.25,
        'energy_needed': 0.2
    })


@dataclass
class ChargingStation:
    """Represents a single charging station."""
    
    station_id: int
    power_kw: float
    is_available: bool = True
    current_vehicle: str = None
    
    def assign_vehicle(self, vehicle_id: str):
        self.current_vehicle = vehicle_id
        self.is_available = False
    
    def release(self):
        self.current_vehicle = None
        self.is_available = True


# Global configuration instance
config = SystemConfig()
