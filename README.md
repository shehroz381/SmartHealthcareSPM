# Smart Healthcare Project Management & Monitoring System (SPM)

An enterprise-grade web application for healthcare software project management, monitoring, and quality assurance across multi-hospital network implementations.

Built for **COMSATS University Islamabad (CSE-494 Mid-term Exam & Project Management Portfolio)**.

---

## 🏥 Project Overview

The **Smart Healthcare SPM System** is tailored to manage and track complex hospital software rollouts across a 5-hospital network (appointments, lab records, consultations, doctor scheduling, and billing). It provides complete lifecycle management aligned with PMBOK, Agile, and CMMI best practices:

- **Executive Analytics Dashboard**: High-level KPI indicators, progress tracking, defect severity metrics, EVM charts, and project health indicators.
- **Project Charter & Management Plan**: Scope boundaries, stakeholder registers, milestone targets, approved baseline budget, and management plans.
- **Milestones & Responsibilities**: Target milestones, responsible team roles, schedule weeks, and delivery statuses.
- **Requirements Management**: Requirements traceability, priority levels (High, Medium, Low), approval statuses, and change control.
- **Work Breakdown Structure (WBS)**: Hierarchical decomposition into Deliverables, Sub-deliverables, and Work Packages.
- **Schedule & Critical Path Management**: Precedence diagramming, Gantt scheduling, delay detection, downstream impact calculations, and buffer slippage alerts.
- **Change Request (CR) Control**: Cost impact, timeline slippage assessment, justification documentation, and approval workflows.
- **Earned Value Management (EVM)**: Planned Value (PV), Earned Value (EV), Actual Cost (AC), Cost Variance (CV), Schedule Variance (SV), CPI, SPI, and EAC forecasting.
- **Quality Assurance & Defect Tracking**: Defect registers, severity triage, root-cause categorization, and 80/20 Pareto analysis.
- **5×5 Risk Matrix & PDPC**: 5×5 Likelihood vs. Impact prioritization heatmap and Process Decision Program Chart (PDPC) contingency tree.
- **Formal Project Closure**: Lessons learned repository, client acceptance status, and final sign-off records.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.10+ / Flask
- **Database**: SQLite3 (with foreign key enforcement and transactional integrity)
- **Frontend**: Vanilla JavaScript (SPA navigation), HTML5, Custom Responsive CSS (Admindek theme)
- **Configuration**: `python-dotenv` for environment management

---

## 🚀 Quick Start Guide

### 1. Prerequisites
Ensure you have Python 3.10 or higher installed:
```bash
python --version
```

### 2. Clone the Repository
```bash
git clone https://github.com/<your-username>/SmartHealthcareSPM.git
cd SmartHealthcareSPM
```

### 3. Create and Activate Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy the example configuration to `.env`:
```bash
# Windows (cmd/PowerShell)
copy .env.example .env

# macOS / Linux
cp .env.example .env
```
*(You can customize `SECRET_KEY`, `PORT`, and `FLASK_DEBUG` inside `.env` as needed).*

### 6. Run the Application
```bash
python app.py
```
Open your browser and navigate to:
```
http://localhost:5000
```
*(The SQLite database and case study records will automatically initialize on first launch).*

---

## 📁 Repository Structure

```
SmartHealthcareSPM/
├── static/
│   └── style.css            # Custom CSS styling (Admindek theme)
├── templates/
│   └── index.html           # Single-Page Application (SPA) master template
├── app.py                   # Core Flask application, models & routes
├── healthcare.db            # SQLite database
├── check_db.py              # Database diagnostics utility
├── requirements.txt         # Python project dependencies
├── .env                     # Local environment variables (ignored by git)
├── .env.example             # Template environment variables
├── .gitignore               # Git ignore rules for Python, Flask & OS files
└── README.md                # Project documentation
```

---

## 🔒 Security & Environment Notes
- `.env` contains local configuration and sensitive secrets and is excluded from git tracking via `.gitignore`.
- Never commit secret keys or production credentials to public GitHub repositories.

---

## 👤 Author
- **Shehroz Mehmood** – Lead Project Manager / Developer
- COMSATS University Islamabad – Department of Computer Science
