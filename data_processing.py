"""Data processing for EV and solar datasets."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path

from config import config


@dataclass
class EVProfile:
    """Profile for an electric vehicle."""
    
    vehicle_id: str
    battery_capacity_kwh: float
    current_soc: float              # State of charge (0-1)
    target_soc: float               # Target state of charge (0-1)
    efficiency_kwh_per_km: float
    arrival_time: int               # Hour of day (0-23)
    departure_time: int             # Hour of day (0-23)
    priority_score: float = 0.0
    
    @property
    def energy_needed_kwh(self) -> float:
        """Calculate energy needed to reach target SOC."""
        return self.battery_capacity_kwh * (self.target_soc - self.current_soc)
    
    @property
    def charging_window(self) -> int:
        """Available hours for charging."""
        if self.departure_time > self.arrival_time:
            return self.departure_time - self.arrival_time
        return (24 - self.arrival_time) + self.departure_time


@dataclass
class SolarProfile:
    """Hourly solar generation profile."""
    
    hour: int
    generation_kw: float
    temperature_c: float
    irradiance_w_m2: float


class DataProcessor:
    """Processes EV and solar datasets."""
    
    def __init__(self, ev_data_path: str = "data/ev_data.csv",
                 solar_data_path: str = "data/solar_data.csv"):
        self.ev_data_path = Path(ev_data_path)
        self.solar_data_path = Path(solar_data_path)
        self.ev_profiles: Dict[str, EVProfile] = {}
        self.solar_profiles: List[SolarProfile] = []
        self.hourly_ev_load: np.ndarray = np.zeros(24)
        self.hourly_solar: np.ndarray = np.zeros(24)
    
    def load_ev_data(self) -> pd.DataFrame:
        """Load and process EV dataset."""
        if self.ev_data_path.exists():
            df = pd.read_csv(self.ev_data_path)
        else:
            # Generate synthetic data if file doesn't exist
            df = self._generate_synthetic_ev_data()
        
        return df
    
    def load_solar_data(self) -> pd.DataFrame:
        """Load and process solar dataset."""
        if self.solar_data_path.exists():
            df = pd.read_csv(self.solar_data_path)
        else:
            # Generate synthetic data if file doesn't exist
            df = self._generate_synthetic_solar_data()
        
        return df
    
    def _generate_synthetic_ev_data(self, num_vehicles: int = 50) -> pd.DataFrame:
        """Generate synthetic EV data for testing."""
        np.random.seed(42)
        
        vehicle_types = [
            {'name': 'Tesla Model 3', 'capacity': 75, 'efficiency': 0.15},
            {'name': 'Nissan Leaf', 'capacity': 62, 'efficiency': 0.18},
            {'name': 'Chevy Bolt', 'capacity': 66, 'efficiency': 0.17},
            {'name': 'Ford Mustang Mach-E', 'capacity': 88, 'efficiency': 0.19},
            {'name': 'VW ID.4', 'capacity': 82, 'efficiency': 0.18},
        ]
        
        data = []
        for i in range(num_vehicles):
            vehicle = np.random.choice(vehicle_types)
            arrival = np.random.choice(range(6, 20))  # Arrive between 6 AM - 8 PM
            departure = min(arrival + np.random.randint(2, 8), 23)  # Stay 2-8 hours
            
            data.append({
                'vehicle_id': f'EV_{i+1:03d}',
                'vehicle_type': vehicle['name'],
                'battery_capacity_kwh': vehicle['capacity'],
                'efficiency_kwh_per_km': vehicle['efficiency'],
                'current_soc': np.random.uniform(0.1, 0.5),
                'target_soc': np.random.uniform(0.8, 1.0),
                'arrival_time': arrival,
                'departure_time': departure,
                'urgency': np.random.randint(1, 6),  # 1-5 scale
                'wait_time_minutes': np.random.randint(0, 60)
            })
        
        df = pd.DataFrame(data)
        
        # Save generated data
        self.ev_data_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.ev_data_path, index=False)
        
        return df
    
    def _generate_synthetic_solar_data(self) -> pd.DataFrame:
        """Generate synthetic solar generation data."""
        np.random.seed(42)
        
        # Typical solar generation curve (peak at noon)
        hours = list(range(24))
        base_generation = [
            0, 0, 0, 0, 0, 5,           # 0-5: Night/early morning
            20, 60, 120, 180, 230, 260, # 6-11: Morning ramp up
            270, 260, 230, 180, 120, 60,# 12-17: Afternoon decline
            20, 5, 0, 0, 0, 0           # 18-23: Evening/night
        ]
        
        data = []
        for hour in hours:
            # Add some randomness
            generation = base_generation[hour] * np.random.uniform(0.85, 1.15)
            temperature = 15 + 10 * np.sin(np.pi * (hour - 6) / 12) + np.random.normal(0, 2)
            irradiance = max(0, generation * 4 + np.random.normal(0, 20))
            
            data.append({
                'hour': hour,
                'generation_kw': max(0, generation),
                'temperature_c': temperature,
                'irradiance_w_m2': irradiance
            })
        
        df = pd.DataFrame(data)
        
        # Save generated data
        self.solar_data_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.solar_data_path, index=False)
        
        return df
    
    def process_ev_profiles(self) -> Dict[str, EVProfile]:
        """Create EV profiles from dataset."""
        df = self.load_ev_data()
        
        for _, row in df.iterrows():
            profile = EVProfile(
                vehicle_id=row['vehicle_id'],
                battery_capacity_kwh=row['battery_capacity_kwh'],
                current_soc=row['current_soc'],
                target_soc=row['target_soc'],
                efficiency_kwh_per_km=row['efficiency_kwh_per_km'],
                arrival_time=int(row['arrival_time']),
                departure_time=int(row['departure_time'])
            )
            
            # Calculate priority score
            profile.priority_score = self._calculate_priority(row)
            self.ev_profiles[profile.vehicle_id] = profile
        
        return self.ev_profiles
    
    def _calculate_priority(self, row: pd.Series) -> float:
        """Calculate priority score for a vehicle."""
        weights = config.priority_weights
        
        # Normalize factors (0-1 scale)
        battery_factor = 1 - row['current_soc']  # Lower SOC = higher priority
        urgency_factor = row['urgency'] / 5.0
        wait_factor = min(row['wait_time_minutes'] / 60.0, 1.0)
        energy_factor = (row['target_soc'] - row['current_soc'])
        
        score = (
            weights['battery_level'] * battery_factor +
            weights['urgency'] * urgency_factor +
            weights['wait_time'] * wait_factor +
            weights['energy_needed'] * energy_factor
        )
        
        return round(score, 3)
    
    def process_solar_profiles(self) -> List[SolarProfile]:
        """Create solar generation profiles from dataset."""
        df = self.load_solar_data()
        
        self.solar_profiles = []
        self.hourly_solar = np.zeros(24)
        
        for _, row in df.iterrows():
            profile = SolarProfile(
                hour=int(row['hour']),
                generation_kw=row['generation_kw'],
                temperature_c=row['temperature_c'],
                irradiance_w_m2=row['irradiance_w_m2']
            )
            self.solar_profiles.append(profile)
            self.hourly_solar[profile.hour] = profile.generation_kw
        
        return self.solar_profiles
    
    def calculate_hourly_ev_load(self) -> np.ndarray:
        """Calculate aggregated hourly EV charging demand."""
        self.hourly_ev_load = np.zeros(24)
        
        for vehicle_id, profile in self.ev_profiles.items():
            # Distribute energy need across charging window
            energy_per_hour = profile.energy_needed_kwh / max(profile.charging_window, 1)
            
            for hour in range(profile.arrival_time, profile.departure_time + 1):
                if hour < 24:
                    self.hourly_ev_load[hour] += energy_per_hour
        
        return self.hourly_ev_load
    
    def get_vehicle_by_id(self, vehicle_id: str) -> Optional[EVProfile]:
        """Retrieve a vehicle profile by ID."""
        return self.ev_profiles.get(vehicle_id)
    
    def get_active_vehicles(self, hour: int) -> List[EVProfile]:
        """Get vehicles that need charging at a specific hour."""
        active = []
        for profile in self.ev_profiles.values():
            if profile.arrival_time <= hour <= profile.departure_time:
                if profile.current_soc < profile.target_soc:
                    active.append(profile)
        return sorted(active, key=lambda x: -x.priority_score)
    
    def add_vehicle(self, vehicle_data: Dict) -> Dict:
        """Add new vehicle to dataset and profiles."""
        try:
            # Load current data
            df = self.load_ev_data()
            
            # Generate unique vehicle ID
            existing_ids = [row.get('vehicle_id', '') for _, row in df.iterrows()]
            max_id = max([int(id.split('_')[1]) for id in existing_ids if id.startswith('EV_')] + [0])
            new_id = f'EV_{(max_id + 1):03d}'
            
            # Create new row
            new_row = {
                'vehicle_id': new_id,
                'vehicle_type': vehicle_data.get('vehicle_type', 'Custom EV'),
                **vehicle_data
            }
            
            # Append to dataframe
            new_df = pd.DataFrame([new_row])
            updated_df = pd.concat([df, new_df], ignore_index=True)
            
            # Save to CSV
            self.ev_data_path.parent.mkdir(parents=True, exist_ok=True)
            updated_df.to_csv(self.ev_data_path, index=False)
            
            # Reload profiles
            self.process_ev_profiles()
            self.calculate_hourly_ev_load()
            
            return {
                'success': True,
                'vehicle_id': new_id,
                'message': f'Vehicle {new_id} added successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_summary_stats(self) -> Dict:
        """Get summary statistics for dashboard."""
        total_demand = sum(p.energy_needed_kwh for p in self.ev_profiles.values())
        total_solar = sum(self.hourly_solar)
        
        return {
            'total_vehicles': len(self.ev_profiles),
            'total_demand_kwh': round(total_demand, 2),
            'total_solar_kwh': round(total_solar, 2),
            'solar_coverage_percent': round((total_solar / total_demand) * 100, 1) if total_demand > 0 else 0,
            'peak_demand_hour': int(np.argmax(self.hourly_ev_load)),
            'peak_solar_hour': int(np.argmax(self.hourly_solar)),
            'hourly_ev_load': self.hourly_ev_load.tolist(),
            'hourly_solar': self.hourly_solar.tolist()
        }


# Singleton instance
data_processor = DataProcessor()
