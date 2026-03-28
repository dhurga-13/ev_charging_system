"""Flask API server for EV Charging Management System."""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import logging

from config import config, SystemConfig
from data_processing import data_processor, DataProcessor
from pso_optimizer import get_optimizer, PSOOptimizer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize components
data_processor.process_ev_profiles()
data_processor.process_solar_profiles()
data_processor.calculate_hourly_ev_load()
optimizer = get_optimizer(data_processor)


# ==================== Page Routes ====================

@app.route('/')
def index():
    """Serve main application page."""
    return render_template('index.html')


# ==================== User API Routes ====================

@app.route('/api/vehicle/<vehicle_id>', methods=['GET'])
def get_vehicle_info(vehicle_id: str):
    """Get vehicle information and optimized charging plan."""
    try:
        vehicle = data_processor.get_vehicle_by_id(vehicle_id.upper())
        
        if not vehicle:
            return jsonify({
                'success': False,
                'error': f'Vehicle {vehicle_id} not found'
            }), 404
        
        # Get optimized schedule
        schedule = optimizer.get_vehicle_schedule(vehicle_id.upper())
        
        return jsonify({
            'success': True,
            'vehicle': {
                'vehicle_id': vehicle.vehicle_id,
                'battery_capacity_kwh': vehicle.battery_capacity_kwh,
                'current_soc': round(vehicle.current_soc * 100, 1),
                'target_soc': round(vehicle.target_soc * 100, 1),
                'energy_needed_kwh': round(vehicle.energy_needed_kwh, 2),
                'arrival_time': vehicle.arrival_time,
                'departure_time': vehicle.departure_time,
                'priority_score': vehicle.priority_score,
                'charging_window_hours': vehicle.charging_window
            },
            'schedule': schedule
        })
    
    except Exception as e:
        logger.error(f"Error getting vehicle info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/vehicles', methods=['GET', 'POST'])
def vehicles():
    if request.method == 'GET':
        """Get list of all vehicles."""
        try:
            vehicles = []
            for v in data_processor.ev_profiles.values():
                vehicles.append({
                    'vehicle_id': v.vehicle_id,
                    'current_soc': round(v.current_soc * 100, 1),
                    'target_soc': round(v.target_soc * 100, 1),
                    'priority_score': v.priority_score,
                    'arrival_time': v.arrival_time,
                    'departure_time': v.departure_time
                })
            
            # Sort by priority
            vehicles.sort(key=lambda x: -x['priority_score'])
            
            return jsonify({
                'success': True,
                'vehicles': vehicles,
                'total_count': len(vehicles)
            })
        
        except Exception as e:
            logger.error(f"Error getting vehicles: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    elif request.method == 'POST':
        """Add new vehicle."""
        try:
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['battery_capacity_kwh', 'current_soc', 'target_soc', 
                             'efficiency_kwh_per_km', 'arrival_time', 'departure_time', 
                             'urgency', 'wait_time_minutes']
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }), 400
            
            # Generate unique vehicle ID
            max_id = max([int(v.vehicle_id.split('_')[1]) for v in data_processor.ev_profiles.values()] + [0])
            new_id = f'EV_{(max_id + 1):03d}'
            
            # Create new row data
            new_row = {
                'vehicle_id': new_id,
                'vehicle_type': data.get('vehicle_type', 'Custom EV'),
                'battery_capacity_kwh': data['battery_capacity_kwh'],
                'efficiency_kwh_per_km': data['efficiency_kwh_per_km'],
                'current_soc': data['current_soc'],
                'target_soc': data['target_soc'],
                'arrival_time': data['arrival_time'],
                'departure_time': data['departure_time'],
                'urgency': data['urgency'],
                'wait_time_minutes': data['wait_time_minutes']
            }
            
            # Use DataProcessor add_vehicle method
            result = data_processor.add_vehicle(new_row)
            if not result['success']:
                return jsonify(result), 500
            
            logger.info(f"Added new vehicle: {result['vehicle_id']}")
            
            logger.info(f"Added new vehicle: {new_id}")
            return jsonify({
                'success': True,
                'message': f'Vehicle {new_id} added successfully',
                'vehicle_id': new_id
            })
            
        except Exception as e:
            logger.error(f"Error adding vehicle: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


# ==================== Optimization API Routes ====================

@app.route('/api/optimize', methods=['POST'])
def run_optimization():
    """Run PSO optimization and return results."""
    try:
        result = optimizer.optimize()
        
        return jsonify({
            'success': result['success'],
            'schedules': result['schedules'],
            'metrics': result['metrics'],
            'final_fitness': result.get('final_fitness', 0)
        })
    
    except Exception as e:
        logger.error(f"Optimization error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/dashboard', methods=['GET'])
def get_dashboard_data():
    """Get dashboard summary data."""
    try:
        stats = data_processor.get_summary_stats()
        
        # Run optimization to get metrics
        result = optimizer.optimize()
        
        return jsonify({
            'success': True,
            'summary': stats,
            'optimization_metrics': result['metrics'],
            'schedules': result['schedules'][:10]  # Top 10 for dashboard
        })
    
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== Admin API Routes ====================

@app.route('/api/admin/config', methods=['GET'])
def get_config():
    """Get current system configuration."""
    return jsonify({
        'success': True,
        'config': {
            'transformer_capacity_kw': config.transformer_capacity_kw,
            'max_grid_load_percent': config.max_grid_load_percent,
            'num_stations': config.num_stations,
            'station_power_kw': config.station_power_kw,
            'num_particles': config.num_particles,
            'max_iterations': config.max_iterations,
            'weight_grid_overload': config.weight_grid_overload,
            'weight_solar_usage': config.weight_solar_usage,
            'weight_fairness': config.weight_fairness
        }
    })


@app.route('/api/admin/config', methods=['PUT'])
def update_config():
    """Update system configuration."""
    try:
        data = request.get_json()
        
        # Update allowed configuration fields
        allowed_fields = [
            'transformer_capacity_kw', 'max_grid_load_percent',
            'num_stations', 'station_power_kw',
            'num_particles', 'max_iterations',
            'weight_grid_overload', 'weight_solar_usage', 'weight_fairness'
        ]
        
        updated = []
        for field in allowed_fields:
            if field in data:
                setattr(config, field, data[field])
                updated.append(field)
        
        # Reinitialize optimizer with new config
        global optimizer
        optimizer = PSOOptimizer(data_processor)
        
        return jsonify({
            'success': True,
            'message': f'Updated configuration: {", ".join(updated)}',
            'updated_fields': updated
        })
    
    except Exception as e:
        logger.error(f"Config update error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/admin/stations', methods=['GET'])
def get_stations_status():
    """Get status of all charging stations."""
    try:
        stations = []
        for station in optimizer.stations:
            stations.append({
                'station_id': station.station_id,
                'power_kw': station.power_kw,
                'is_available': station.is_available,
                'current_vehicle': station.current_vehicle
            })
        
        return jsonify({
            'success': True,
            'stations': stations,
            'total_capacity_kw': sum(s.power_kw for s in optimizer.stations)
        })
    
    except Exception as e:
        logger.error(f"Stations status error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/admin/load-profile', methods=['GET'])
def get_load_profile():
    """Get hourly load and solar profiles."""
    try:
        return jsonify({
            'success': True,
            'hourly_ev_load': data_processor.hourly_ev_load.tolist(),
            'hourly_solar': data_processor.hourly_solar.tolist(),
            'hours': list(range(24))
        })
    
    except Exception as e:
        logger.error(f"Load profile error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/admin/reset', methods=['POST'])
def reset_system():
    """Reset system and regenerate data."""
    try:
        global data_processor, optimizer
        
        # Reinitialize data processor
        data_processor = DataProcessor()
        data_processor.process_ev_profiles()
        data_processor.process_solar_profiles()
        data_processor.calculate_hourly_ev_load()
        
        # Reinitialize optimizer
        optimizer = PSOOptimizer(data_processor)
        
        return jsonify({
            'success': True,
            'message': 'System reset successfully'
        })
    
    except Exception as e:
        logger.error(f"Reset error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== Error Handlers ====================

@app.errorhandler(404)
def not_found(e):
    return jsonify({
        'success': False,
        'error': 'Resource not found'
    }), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500


# ==================== Main ====================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
