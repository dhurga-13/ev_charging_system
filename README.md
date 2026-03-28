# EV Charging Management System 🚀

## 🎯 Overview

Smart EV charging scheduler using **Particle Swarm Optimization (PSO)** that maximizes solar usage while respecting grid constraints. Production-ready Flask web app with professional enterprise UI.

## ✨ Features

```
✅ Real-time PSO optimization (50 particles, 100 iterations)
✅ Solar integration with hourly generation profiles
✅ Dynamic vehicle management (Add/Search/Edit)
✅ Priority-based scheduling
✅ Admin dashboard with live metrics/charts
✅ Responsive professional UI (deep blue enterprise theme)
✅ CSV data persistence
✅ Grid constraint enforcement (transformer capacity, load %)
```

## 🏗️ Tech Stack

```
Backend: Flask, Pandas, NumPy
Optimization: Custom PSO algorithm
Frontend: Vanilla JS + Chart.js
Styling: Custom CSS (Tailwind-inspired)
Data: CSV (ev_data.csv, solar_data.csv)
Deployment: Production-ready (0.0.0.0:5000)
```

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
python app.py

# Open browser
http://127.0.0.1:5000
```

## 📱 Usage

### 1. **User Portal** (User Portal tab)

```
- Add New Vehicle: Fill form → Auto-generates EV_### ID → Saves to CSV
- Search Vehicle: Enter EV_001 → View optimized solar/grid schedule
- All Vehicles: Live list with priority scores
```

### 2. **Admin Panel** (Admin tab)

```
- Configure: Transformer kW, stations, PSO params (particles/iterations)
- Weights: Grid overload (40%), Solar (35%), Fairness (25%)
- Actions: Run optimization, Reset system
- Stations: Live status grid
```

### 3. **Dashboard** (Dashboard tab)

```
- Metrics: Vehicles, demand kWh, solar coverage %
- Charts: EV demand vs solar (line), Solar/Grid split (doughnut)
- Top Schedules: Priority table (vehicle/station/time/energy/solar%)
```

## 🔧 Key Algorithms

### PSO Optimization

```
Objective: Minimize = w1*GridOverload + w2*(1-SolarUtilization) + w3*FairnessPenalty
Constraints: Transformer capacity, station power, vehicle windows
Particles: 50, Iterations: 100, Adaptive inertia decay
```

### Vehicle Priority

```
Score = 0.3*(1-CurrentSOC) + 0.25*(Urgency/5) + 0.25*(Wait/60) + 0.2*(Target-CurrentSOC)
```

## 📊 Sample Data

```
EV Profiles: 50 vehicles (Tesla/Nissan/Chevy/Ford/VW)
Solar: 24h profile (270kW peak noon)
Grid: 500kW transformer @ 80% max
Stations: 10 × 50kW
```

## 🎨 Professional Styling

```
Theme: Deep Indigo #1e3a8a + Slate Grays
Buttons: Uniform blue across all actions
Cards: Crisp white w/ subtle shadows
Responsive: Mobile-first grid layouts
```

## 🛠️ File Structure

```
├── app.py              # Flask API + routing
├── data_processing.py  # EV/Solar data + add_vehicle()
├── pso_optimizer.py    # PSO core algorithm
├── config.py           # System parameters
├── templates/index.html # SPA frontend
├── static/css/style.css # Enterprise theme
├── static/js/main.js   # Charts + interactivity
├── requirements.txt    # Dependencies
├── data/ev_data.csv    # Vehicle data (auto-generated)
└── README.md          # This file
```

## 📈 API Endpoints

```
GET  /api/vehicles          # List all vehicles
POST /api/vehicles          # Add new vehicle
GET  /api/vehicle/:id       # Vehicle + schedule
POST /api/optimize          # Run PSO
GET  /api/dashboard         # Metrics + charts
GET/PUT /api/admin/config   # System config
GET  /api/admin/stations    # Station status
POST /api/admin/reset       # Reset data
```

## 🔒 Production Notes

```
Port: 0.0.0.0:5000 (network accessible)
Debug: True (dev) → False (prod)
Data: Auto-generates CSV if missing
Scale: Adjust config.num_stations, config.transformer_capacity_kw
```

## 🎉 Next Steps

```
1. Deploy: `gunicorn app:app` or cloud platform
2. Extend: User auth, real solar API, payment integration
3. Scale: Redis queue for PSO, PostgreSQL for vehicles
4. Monitor: Add Prometheus metrics endpoint
```

**Live Demo**: http://127.0.0.1:5000  
**Status**: 🚀 Production Ready Enterprise EV Charging Platform
