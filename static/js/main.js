/**
 * EV Charging Management System - Frontend JavaScript
 */

// ==================== State Management ====================
const state = {
    currentTab: 'user',
    vehicles: [],
    schedules: [],
    config: {},
    charts: {}
};

// ==================== API Functions ====================
const API = {
    baseUrl: '',
    
    async get(endpoint) {
        const response = await fetch(`${this.baseUrl}${endpoint}`);
        return response.json();
    },
    
    async post(endpoint, data = {}) {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return response.json();
    },
    
    async put(endpoint, data) {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return response.json();
    }
};

// ==================== Tab Navigation ====================
function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(tab).classList.add('active');
            
            state.currentTab = tab;
            
            if (tab === 'dashboard') {
                loadDashboard();
            } else if (tab === 'admin') {
                loadAdminData();
            }
        });
    });
}

// ==================== User Portal Functions ====================
async function addVehicle() {
    const formData = {
        vehicle_type: document.getElementById('new-vehicle-type').value || 'Custom EV',
        battery_capacity_kwh: parseFloat(document.getElementById('new-battery-capacity').value),
        efficiency_kwh_per_km: parseFloat(document.getElementById('new-efficiency').value),
        current_soc: parseFloat(document.getElementById('new-current-soc').value),
        target_soc: parseFloat(document.getElementById('new-target-soc').value),
        arrival_time: parseInt(document.getElementById('new-arrival-time').value),
        departure_time: parseInt(document.getElementById('new-departure-time').value),
        urgency: parseInt(document.getElementById('new-urgency').value),
        wait_time_minutes: parseInt(document.getElementById('new-wait-time').value)
    };
    
    // Basic validation
    if (!formData.battery_capacity_kwh || formData.battery_capacity_kwh <= 0) {
        showVehicleMessage('Battery capacity must be positive', false);
        return;
    }
    if (formData.current_soc < 0 || formData.current_soc > 1 || formData.target_soc < 0 || formData.target_soc > 1) {
        showVehicleMessage('SOC values must be between 0 and 1', false);
        return;
    }
    if (formData.current_soc >= formData.target_soc) {
        showVehicleMessage('Target SOC must be higher than current SOC', false);
        return;
    }
    if (formData.arrival_time < 0 || formData.arrival_time > 23 || formData.departure_time < 0 || formData.departure_time > 23) {
        showVehicleMessage('Times must be between 0-23', false);
        return;
    }
    if (formData.arrival_time >= formData.departure_time) {
        showVehicleMessage('Departure time must be after arrival time', false);
        return;
    }
    
    try {
        const result = await API.post('/api/vehicles', formData);
        
        if (result.success) {
            showVehicleMessage(result.message, true);
            document.getElementById('newVehicleForm').reset();
            loadVehicleList(); // Refresh list
        } else {
            showVehicleMessage(result.error, false);
        }
    } catch (error) {
        console.error('Add vehicle error:', error);
        showVehicleMessage('Network error. Please try again.', false);
    }
}

function showVehicleMessage(message, isSuccess) {
    const msgEl = document.getElementById('vehicleMessage');
    msgEl.textContent = message;
    msgEl.className = `vehicle-message ${isSuccess ? 'success' : 'error'}`;
    msgEl.style.display = 'block';
    setTimeout(() => {
        msgEl.style.display = 'none';
    }, 5000);
}

async function searchVehicle() {
    const vehicleId = document.getElementById('vehicleId').value.trim();
    
    if (!vehicleId) {
        alert('Please enter a vehicle ID');
        return;
    }
    
    try {
        const result = await API.get(`/api/vehicle/${vehicleId}`);
        
        if (result.success) {
            displayVehicleInfo(result.vehicle);
            displaySchedule(result.schedule);
        } else {
            alert(result.error || 'Vehicle not found');
            hideResults();
        }
    } catch (error) {
        console.error('Search error:', error);
        alert('Error searching for vehicle');
    }
}

function displayVehicleInfo(vehicle) {
    document.getElementById('vehicleResult').classList.remove('hidden');
    
    document.getElementById('v-id').textContent = vehicle.vehicle_id;
    document.getElementById('v-priority').textContent = vehicle.priority_score.toFixed(3);
    document.getElementById('v-current-soc').textContent = `${vehicle.current_soc}%`;
    document.getElementById('v-target-soc').textContent = `${vehicle.target_soc}%`;
    document.getElementById('v-energy').textContent = `${vehicle.energy_needed_kwh} kWh`;
    document.getElementById('v-window').textContent = 
        `${formatHour(vehicle.arrival_time)} - ${formatHour(vehicle.departure_time)}`;
}

function displaySchedule(schedule) {
    if (!schedule) {
        document.getElementById('scheduleResult').classList.add('hidden');
        return;
    }
    
    document.getElementById('scheduleResult').classList.remove('hidden');
    
    document.getElementById('s-station').textContent = `Station #${schedule.station_id + 1}`;
    document.getElementById('s-time').textContent = 
        `${formatHour(schedule.start_hour)} - ${formatHour(schedule.end_hour)}`;
    document.getElementById('s-total-energy').textContent = `${schedule.total_energy_kwh} kWh`;
    document.getElementById('s-solar-energy').textContent = `${schedule.solar_energy_kwh} kWh`;
    document.getElementById('s-grid-energy').textContent = `${schedule.grid_energy_kwh} kWh`;
    document.getElementById('s-cost').textContent = `$${schedule.estimated_cost.toFixed(2)}`;
    
    createChargingChart(schedule.hourly_power_kw);
}

function hideResults() {
    document.getElementById('vehicleResult').classList.add('hidden');
    document.getElementById('scheduleResult').classList.add('hidden');
}

function createChargingChart(hourlyPower) {
    const ctx = document.getElementById('chargingChart').getContext('2d');
    
    if (state.charts.charging) {
        state.charts.charging.destroy();
    }
    
    state.charts.charging = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: Array.from({length: 24}, (_, i) => formatHour(i)),
            datasets: [{
                label: 'Charging Power (kW)',
                data: hourlyPower,
                backgroundColor: 'rgba(37, 99, 235, 0.8)',
                borderColor: 'rgba(37, 99, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Power (kW)' }
                }
            }
        }
    });
}

async function loadVehicleList() {
    try {
        const result = await API.get('/api/vehicles');
        
        if (result.success) {
            state.vehicles = result.vehicles;
            renderVehicleList();
        }
    } catch (error) {
        console.error('Error loading vehicles:', error);
    }
}

function renderVehicleList() {
    const container = document.getElementById('vehicleList');
    
    if (state.vehicles.length === 0) {
        container.innerHTML = '<p class="loading">No vehicles found</p>';
        return;
    }
    
    container.innerHTML = state.vehicles.map(v => `
        <div class="vehicle-item" onclick="selectVehicle('${v.vehicle_id}')">
            <div>
                <span class="vehicle-id">${v.vehicle_id}</span>
                <span class="vehicle-details">
                    SOC: ${v.current_soc}% → ${v.target_soc}% | 
                    ${formatHour(v.arrival_time)} - ${formatHour(v.departure_time)}
                </span>
            </div>
            <span class="vehicle-priority">${v.priority_score.toFixed(2)}</span>
        </div>
    `).join('');
}

function selectVehicle(vehicleId) {
    document.getElementById('vehicleId').value = vehicleId;
    searchVehicle();
}

// ==================== Admin Panel Functions ====================
async function loadAdminData() {
    await Promise.all([
        loadConfig(),
        loadStationStatus()
    ]);
}

async function loadConfig() {
    try {
        const result = await API.get('/api/admin/config');
        
        if (result.success) {
            state.config = result.config;
            populateConfigForm();
        }
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

function populateConfigForm() {
    const cfg = state.config;
    
    document.getElementById('cfg-transformer').value = cfg.transformer_capacity_kw;
    document.getElementById('cfg-max-load').value = cfg.max_grid_load_percent;
    document.getElementById('cfg-stations').value = cfg.num_stations;
    document.getElementById('cfg-station-power').value = cfg.station_power_kw;
    document.getElementById('cfg-particles').value = cfg.num_particles;
    document.getElementById('cfg-iterations').value = cfg.max_iterations;
    
    document.getElementById('weight-grid').value = cfg.weight_grid_overload * 100;
    document.getElementById('weight-solar').value = cfg.weight_solar_usage * 100;
    document.getElementById('weight-fairness').value = cfg.weight_fairness * 100;
    
    updateWeightDisplay();
}

function updateWeightDisplay() {
    document.getElementById('weight-grid-val').textContent = 
        (document.getElementById('weight-grid').value / 100).toFixed(2);
    document.getElementById('weight-solar-val').textContent = 
        (document.getElementById('weight-solar').value / 100).toFixed(2);
    document.getElementById('weight-fairness-val').textContent = 
        (document.getElementById('weight-fairness').value / 100).toFixed(2);
}

async function updateConfig(e) {
    e.preventDefault();
    
    const config = {
        transformer_capacity_kw: parseFloat(document.getElementById('cfg-transformer').value),
        max_grid_load_percent: parseFloat(document.getElementById('cfg-max-load').value),
        num_stations: parseInt(document.getElementById('cfg-stations').value),
        station_power_kw: parseFloat(document.getElementById('cfg-station-power').value),
        num_particles: parseInt(document.getElementById('cfg-particles').value),
        max_iterations: parseInt(document.getElementById('cfg-iterations').value)
    };
    
    try {
        const result = await API.put('/api/admin/config', config);
        showActionResult(result.success, result.message || result.error);
    } catch (error) {
        showActionResult(false, 'Error updating configuration');
    }
}

async function updateWeights(e) {
    e.preventDefault();
    
    const weights = {
        weight_grid_overload: parseFloat(document.getElementById('weight-grid').value) / 100,
        weight_solar_usage: parseFloat(document.getElementById('weight-solar').value) / 100,
        weight_fairness: parseFloat(document.getElementById('weight-fairness').value) / 100
    };
    
    try {
        const result = await API.put('/api/admin/config', weights);
        showActionResult(result.success, result.message || result.error);
    } catch (error) {
        showActionResult(false, 'Error updating weights');
    }
}

async function loadStationStatus() {
    try {
        const result = await API.get('/api/admin/stations');
        
        if (result.success) {
            renderStationStatus(result.stations);
        }
    } catch (error) {
        console.error('Error loading stations:', error);
    }
}

function renderStationStatus(stations) {
    const container = document.getElementById('stationStatus');
    
    container.innerHTML = stations.map(s => `
        <div class="station-item ${s.is_available ? 'available' : 'occupied'}">
            #${s.station_id + 1}<br>
            ${s.power_kw}kW
        </div>
    `).join('');
}

async function runOptimization() {
    showActionResult(true, 'Running optimization...');
    
    try {
        const result = await API.post('/api/optimize');
        
        if (result.success) {
            state.schedules = result.schedules;
            showActionResult(true, 
                `Optimization complete! Final fitness: ${result.final_fitness.toFixed(4)}`);
        } else {
            showActionResult(false, result.error);
        }
    } catch (error) {
        showActionResult(false, 'Error running optimization');
    }
}

async function resetSystem() {
    if (!confirm('Are you sure you want to reset the system? This will regenerate all data.')) {
        return;
    }
    
    try {
        const result = await API.post('/api/admin/reset');
        showActionResult(result.success, result.message || result.error);
        
        if (result.success) {
            loadVehicleList();
            loadAdminData();
        }
    } catch (error) {
        showActionResult(false, 'Error resetting system');
    }
}

function showActionResult(success, message) {
    const container = document.getElementById('actionResult');
    container.className = `action-result ${success ? 'success' : 'error'}`;
    container.textContent = message;
    container.classList.remove('hidden');
}

// ==================== Dashboard Functions ====================
async function loadDashboard() {
    try {
        const result = await API.get('/api/dashboard');
        
        if (result.success) {
            renderMetrics(result.summary, result.optimization_metrics);
            createLoadChart(result.summary);
            createMetricsChart(result.optimization_metrics);
            renderTopSchedules(result.schedules);
        }
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

function renderMetrics(summary, metrics) {
    document.getElementById('m-vehicles').textContent = summary.total_vehicles;
    document.getElementById('m-demand').textContent = summary.total_demand_kwh.toLocaleString();
    document.getElementById('m-solar').textContent = summary.total_solar_kwh.toLocaleString();
    document.getElementById('m-coverage').textContent = `${summary.solar_coverage_percent}%`;
}

function createLoadChart(summary) {
    const ctx = document.getElementById('loadChart').getContext('2d');
    
    if (state.charts.load) {
        state.charts.load.destroy();
    }
    
    state.charts.load = new Chart(ctx, {
        type: 'line',
        data: {
            labels: Array.from({length: 24}, (_, i) => formatHour(i)),
            datasets: [
                {
                    label: 'EV Demand (kW)',
                    data: summary.hourly_ev_load,
                    borderColor: 'rgba(37, 99, 235, 1)',
                    backgroundColor: 'rgba(37, 99, 235, 0.1)',
                    fill: true,
                    tension: 0.3
                },
                {
                    label: 'Solar Generation (kW)',
                    data: summary.hourly_solar,
                    borderColor: 'rgba(251, 191, 36, 1)',
                    backgroundColor: 'rgba(251, 191, 36, 0.1)',
                    fill: true,
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Power (kW)' }
                }
            }
        }
    });
}

function createMetricsChart(metrics) {
    const ctx = document.getElementById('metricsChart').getContext('2d');
    
    if (state.charts.metrics) {
        state.charts.metrics.destroy();
    }
    
    state.charts.metrics = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Solar Energy', 'Grid Energy'],
            datasets: [{
                data: [metrics.solar_energy_kwh, metrics.grid_energy_kwh],
                backgroundColor: [
                    'rgba(251, 191, 36, 0.8)',
                    'rgba(100, 116, 139, 0.8)'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                title: {
                    display: true,
                    text: `Solar Utilization: ${metrics.solar_utilization_percent}%`
                }
            }
        }
    });
}

function renderTopSchedules(schedules) {
    const container = document.getElementById('topSchedules');
    
    if (!schedules || schedules.length === 0) {
        container.innerHTML = '<p class="loading">No schedules available</p>';
        return;
    }
    
    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Vehicle</th>
                    <th>Station</th>
                    <th>Time</th>
                    <th>Energy</th>
                    <th>Solar %</th>
                    <th>Cost</th>
                </tr>
            </thead>
            <tbody>
                ${schedules.map(s => `
                    <tr>
                        <td><strong>${s.vehicle_id}</strong></td>
                        <td>#${s.station_id + 1}</td>
                        <td>${formatHour(s.start_hour)} - ${formatHour(s.end_hour)}</td>
                        <td>${s.total_energy_kwh} kWh</td>
                        <td>${((s.solar_energy_kwh / s.total_energy_kwh) * 100).toFixed(0)}%</td>
                        <td>$${s.estimated_cost.toFixed(2)}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// ==================== Utility Functions ====================
function formatHour(hour) {
    const h = hour % 24;
    const ampm = h >= 12 ? 'PM' : 'AM';
    const displayHour = h % 12 || 12;
    return `${displayHour}${ampm}`;
}

// ==================== Event Listeners ====================
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    
    // User portal
    document.getElementById('searchBtn').addEventListener('click', searchVehicle);
    document.getElementById('vehicleId').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchVehicle();
    });
    
    document.getElementById('newVehicleForm').addEventListener('submit', (e) => {
        e.preventDefault();
        addVehicle();
    });
    
    // Admin panel
    document.getElementById('configForm').addEventListener('submit', updateConfig);
    document.getElementById('weightsForm').addEventListener('submit', updateWeights);
    
    ['weight-grid', 'weight-solar', 'weight-fairness'].forEach(id => {
        document.getElementById(id).addEventListener('input', updateWeightDisplay);
    });
    
    document.getElementById('runOptimization').addEventListener('click', runOptimization);
    document.getElementById('resetSystem').addEventListener('click', resetSystem);
    
    // Initial data load
    loadVehicleList();
});
