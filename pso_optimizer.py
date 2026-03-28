"""Particle Swarm Optimization for EV charging scheduling."""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from copy import deepcopy

from config import config, ChargingStation
from data_processing import DataProcessor, EVProfile


@dataclass
class Particle:
    """Represents a particle in the swarm."""
    
    position: np.ndarray           # Charging schedule matrix
    velocity: np.ndarray           # Velocity for position update
    personal_best_position: np.ndarray = None
    personal_best_fitness: float = float('inf')
    
    def __post_init__(self):
        if self.personal_best_position is None:
            self.personal_best_position = self.position.copy()


@dataclass
class ChargingSchedule:
    """Optimized charging schedule for a vehicle."""
    
    vehicle_id: str
    station_id: int
    start_hour: int
    end_hour: int
    hourly_power_kw: List[float]
    total_energy_kwh: float
    solar_energy_kwh: float
    grid_energy_kwh: float
    priority_score: float
    estimated_cost: float


class PSOOptimizer:
    """Particle Swarm Optimization for EV charging scheduling."""
    
    def __init__(self, data_processor: DataProcessor):
        self.data_processor = data_processor
        self.num_particles = config.num_particles
        self.max_iterations = config.max_iterations
        self.w = config.w_inertia
        self.c1 = config.c1_cognitive
        self.c2 = config.c2_social
        
        self.global_best_position: np.ndarray = None
        self.global_best_fitness: float = float('inf')
        self.particles: List[Particle] = []
        
        self.stations = [
            ChargingStation(station_id=i, power_kw=config.station_power_kw)
            for i in range(config.num_stations)
        ]
        
        self.fitness_history: List[float] = []
    
    def initialize_swarm(self, vehicles: List[EVProfile]) -> None:
        """Initialize particle swarm with random positions."""
        num_vehicles = len(vehicles)
        num_hours = config.time_slots
        
        self.particles = []
        
        for _ in range(self.num_particles):
            # Position: matrix of shape (num_vehicles, num_hours)
            # Values represent charging power allocation (0 to station_power_kw)
            position = np.random.uniform(
                0, config.station_power_kw,
                size=(num_vehicles, num_hours)
            )
            
            # Apply constraints based on vehicle availability
            for i, vehicle in enumerate(vehicles):
                for hour in range(num_hours):
                    if hour < vehicle.arrival_time or hour > vehicle.departure_time:
                        position[i, hour] = 0
            
            velocity = np.random.uniform(-5, 5, size=(num_vehicles, num_hours))
            
            particle = Particle(position=position, velocity=velocity)
            self.particles.append(particle)
        
        # Initialize global best
        self.global_best_position = self.particles[0].position.copy()
        self.global_best_fitness = float('inf')
    
    def calculate_fitness(self, position: np.ndarray, 
                         vehicles: List[EVProfile]) -> float:
        """
        Calculate fitness value for a charging schedule.
        
        Lower fitness is better. Objectives:
        1. Minimize grid overload
        2. Maximize solar energy usage
        3. Ensure fair allocation
        """
        num_hours = config.time_slots
        hourly_solar = self.data_processor.hourly_solar
        
        # Calculate hourly total load
        hourly_load = np.sum(position, axis=0)
        
        # Objective 1: Grid overload penalty
        max_load = config.transformer_capacity_kw * (config.max_grid_load_percent / 100)
        overload = np.maximum(0, hourly_load - max_load)
        overload_penalty = np.sum(overload ** 2) / num_hours
        
        # Objective 2: Solar utilization (negative because we want to maximize)
        solar_used = np.minimum(hourly_load, hourly_solar)
        total_solar_available = np.sum(hourly_solar)
        solar_utilization = np.sum(solar_used) / max(total_solar_available, 1)
        solar_penalty = 1 - solar_utilization  # Convert to minimization
        
        # Objective 3: Fairness - ensure all vehicles get proportional charging
        fairness_penalty = 0
        for i, vehicle in enumerate(vehicles):
            energy_received = np.sum(position[i, :])
            energy_needed = vehicle.energy_needed_kwh
            
            if energy_needed > 0:
                fulfillment_ratio = min(energy_received / energy_needed, 1.0)
                # Penalize under-charging more for high-priority vehicles
                fairness_penalty += (1 - fulfillment_ratio) * (1 + vehicle.priority_score)
        
        fairness_penalty /= len(vehicles) if vehicles else 1
        
        # Constraint penalty: Ensure charging doesn't exceed vehicle needs
        constraint_penalty = 0
        for i, vehicle in enumerate(vehicles):
            energy_received = np.sum(position[i, :])
            if energy_received > vehicle.energy_needed_kwh * 1.1:  # 10% tolerance
                constraint_penalty += (energy_received - vehicle.energy_needed_kwh) ** 2
        
        # Weighted sum of objectives
        fitness = (
            config.weight_grid_overload * overload_penalty +
            config.weight_solar_usage * solar_penalty +
            config.weight_fairness * fairness_penalty +
            0.1 * constraint_penalty  # Hard constraint
        )
        
        return fitness
    
    def update_velocity(self, particle: Particle) -> np.ndarray:
        """Update particle velocity using PSO equations."""
        r1 = np.random.random(particle.position.shape)
        r2 = np.random.random(particle.position.shape)
        
        cognitive = self.c1 * r1 * (particle.personal_best_position - particle.position)
        social = self.c2 * r2 * (self.global_best_position - particle.position)
        
        new_velocity = self.w * particle.velocity + cognitive + social
        
        # Clamp velocity
        max_velocity = config.station_power_kw * 0.5
        new_velocity = np.clip(new_velocity, -max_velocity, max_velocity)
        
        return new_velocity
    
    def update_position(self, particle: Particle, 
                       vehicles: List[EVProfile]) -> np.ndarray:
        """Update particle position and apply constraints."""
        new_position = particle.position + particle.velocity
        
        # Apply constraints
        new_position = np.clip(new_position, 0, config.station_power_kw)
        
        # Enforce vehicle availability windows
        for i, vehicle in enumerate(vehicles):
            for hour in range(config.time_slots):
                if hour < vehicle.arrival_time or hour > vehicle.departure_time:
                    new_position[i, hour] = 0
        
        # Limit station capacity per hour
        for hour in range(config.time_slots):
            hourly_total = np.sum(new_position[:, hour])
            max_capacity = config.num_stations * config.station_power_kw
            
            if hourly_total > max_capacity:
                scale_factor = max_capacity / hourly_total
                new_position[:, hour] *= scale_factor
        
        return new_position
    
    def optimize(self, vehicles: List[EVProfile] = None) -> Dict:
        """
        Run PSO optimization to find optimal charging schedule.
        
        Returns dict with optimized schedules and metrics.
        """
        if vehicles is None:
            vehicles = list(self.data_processor.ev_profiles.values())
        
        if not vehicles:
            return {
                'success': False,
                'message': 'No vehicles to optimize',
                'schedules': [],
                'metrics': {}
            }
        
        # Initialize swarm
        self.initialize_swarm(vehicles)
        self.fitness_history = []
        
        # Main optimization loop
        for iteration in range(self.max_iterations):
            for particle in self.particles:
                # Calculate fitness
                fitness = self.calculate_fitness(particle.position, vehicles)
                
                # Update personal best
                if fitness < particle.personal_best_fitness:
                    particle.personal_best_fitness = fitness
                    particle.personal_best_position = particle.position.copy()
                
                # Update global best
                if fitness < self.global_best_fitness:
                    self.global_best_fitness = fitness
                    self.global_best_position = particle.position.copy()
            
            # Update all particles
            for particle in self.particles:
                particle.velocity = self.update_velocity(particle)
                particle.position = self.update_position(particle, vehicles)
            
            self.fitness_history.append(self.global_best_fitness)
            
            # Adaptive inertia weight decay
            self.w = max(0.4, self.w * 0.99)
        
        # Generate final schedules
        schedules = self._generate_schedules(vehicles)
        metrics = self._calculate_metrics(vehicles)
        
        return {
            'success': True,
            'schedules': schedules,
            'metrics': metrics,
            'fitness_history': self.fitness_history,
            'final_fitness': self.global_best_fitness
        }
    
    def _generate_schedules(self, vehicles: List[EVProfile]) -> List[Dict]:
        """Convert optimized position to charging schedules."""
        schedules = []
        hourly_solar = self.data_processor.hourly_solar
        
        # Assign stations to vehicles based on priority
        station_assignments = self._assign_stations(vehicles)
        
        for i, vehicle in enumerate(vehicles):
            hourly_power = self.global_best_position[i, :]
            
            # Find active charging hours
            active_hours = np.where(hourly_power > 0.1)[0]
            
            if len(active_hours) == 0:
                start_hour = vehicle.arrival_time
                end_hour = vehicle.arrival_time
            else:
                start_hour = int(active_hours[0])
                end_hour = int(active_hours[-1])
            
            total_energy = np.sum(hourly_power)
            
            # Calculate solar vs grid energy
            solar_energy = 0
            for hour in range(config.time_slots):
                if hourly_power[hour] > 0:
                    available_solar = hourly_solar[hour] / len(vehicles)  # Fair share
                    solar_energy += min(hourly_power[hour], available_solar)
            
            grid_energy = total_energy - solar_energy
            
            # Estimate cost (example: $0.10/kWh grid, $0.02/kWh solar)
            estimated_cost = grid_energy * 0.10 + solar_energy * 0.02
            
            schedule = {
                'vehicle_id': vehicle.vehicle_id,
                'station_id': station_assignments.get(vehicle.vehicle_id, 0),
                'start_hour': start_hour,
                'end_hour': end_hour,
                'hourly_power_kw': hourly_power.tolist(),
                'total_energy_kwh': round(total_energy, 2),
                'solar_energy_kwh': round(solar_energy, 2),
                'grid_energy_kwh': round(max(0, grid_energy), 2),
                'priority_score': vehicle.priority_score,
                'estimated_cost': round(estimated_cost, 2),
                'fulfillment_percent': round(
                    min(100, (total_energy / vehicle.energy_needed_kwh) * 100), 1
                ) if vehicle.energy_needed_kwh > 0 else 100
            }
            schedules.append(schedule)
        
        return schedules
    
    def _assign_stations(self, vehicles: List[EVProfile]) -> Dict[str, int]:
        """Assign charging stations to vehicles based on priority."""
        assignments = {}
        
        # Sort by priority (highest first)
        sorted_vehicles = sorted(vehicles, key=lambda x: -x.priority_score)
        
        # Round-robin assignment with priority consideration
        for i, vehicle in enumerate(sorted_vehicles):
            station_id = i % config.num_stations
            assignments[vehicle.vehicle_id] = station_id
        
        return assignments
    
    def _calculate_metrics(self, vehicles: List[EVProfile]) -> Dict:
        """Calculate optimization metrics."""
        hourly_load = np.sum(self.global_best_position, axis=0)
        hourly_solar = self.data_processor.hourly_solar
        
        # Peak load and grid stress
        peak_load = float(np.max(hourly_load))
        avg_load = float(np.mean(hourly_load[hourly_load > 0])) if np.any(hourly_load > 0) else 0
        
        # Solar utilization
        solar_used = np.sum(np.minimum(hourly_load, hourly_solar))
        total_solar = np.sum(hourly_solar)
        solar_utilization = (solar_used / total_solar * 100) if total_solar > 0 else 0
        
        # Grid dependency
        total_load = np.sum(hourly_load)
        grid_usage = max(0, total_load - solar_used)
        grid_dependency = (grid_usage / total_load * 100) if total_load > 0 else 0
        
        # Fulfillment rate
        total_needed = sum(v.energy_needed_kwh for v in vehicles)
        total_delivered = np.sum(self.global_best_position)
        fulfillment_rate = (total_delivered / total_needed * 100) if total_needed > 0 else 100
        
        # Load distribution (Gini coefficient for fairness)
        load_variance = float(np.var(hourly_load[hourly_load > 0])) if np.any(hourly_load > 0) else 0
        
        return {
            'peak_load_kw': round(peak_load, 2),
            'average_load_kw': round(avg_load, 2),
            'solar_utilization_percent': round(solar_utilization, 1),
            'grid_dependency_percent': round(grid_dependency, 1),
            'fulfillment_rate_percent': round(min(100, fulfillment_rate), 1),
            'load_variance': round(load_variance, 2),
            'total_energy_kwh': round(total_load, 2),
            'solar_energy_kwh': round(solar_used, 2),
            'grid_energy_kwh': round(grid_usage, 2),
            'hourly_optimized_load': hourly_load.tolist(),
            'transformer_headroom_kw': round(
                config.transformer_capacity_kw - peak_load, 2
            )
        }
    
    def get_vehicle_schedule(self, vehicle_id: str) -> Optional[Dict]:
        """Get optimized schedule for a specific vehicle."""
        if vehicle_id not in self.data_processor.ev_profiles:
            return None
        
        vehicle = self.data_processor.ev_profiles[vehicle_id]
        
        # Run optimization if not already done
        if self.global_best_position is None:
            self.optimize()
        
        vehicles = list(self.data_processor.ev_profiles.values())
        vehicle_idx = None
        
        for i, v in enumerate(vehicles):
            if v.vehicle_id == vehicle_id:
                vehicle_idx = i
                break
        
        if vehicle_idx is None:
            return None
        
        schedules = self._generate_schedules(vehicles)
        
        for schedule in schedules:
            if schedule['vehicle_id'] == vehicle_id:
                return schedule
        
        return None


# Singleton instance
pso_optimizer = None

def get_optimizer(data_processor: DataProcessor) -> PSOOptimizer:
    """Get or create optimizer instance."""
    global pso_optimizer
    if pso_optimizer is None:
        pso_optimizer = PSOOptimizer(data_processor)
    return pso_optimizer
