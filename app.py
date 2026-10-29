
import os
from pathlib import Path
from datetime import date, datetime, timedelta
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smart-healthcare-project-management-key")

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "healthcare.db"

APPROVAL_STATUSES = ["Pending", "Approved", "Rejected"]


# =========================================================
# DATABASE CONNECTION & INITIALIZATION
# =========================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()

    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                objectives TEXT NOT NULL,
                stakeholders TEXT NOT NULL,
                scope_boundaries TEXT NOT NULL,
                approved_budget REAL NOT NULL DEFAULT 0,
                deadline_weeks INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'Planning',
                plan_scope TEXT NOT NULL DEFAULT '',
                plan_schedule TEXT NOT NULL DEFAULT '',
                plan_cost TEXT NOT NULL DEFAULT '',
                plan_quality TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                milestone_name TEXT NOT NULL,
                due_week INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'Pending',
                responsible_person TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (project_id) REFERENCES projects(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS closures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL UNIQUE,
                completion_date TEXT NOT NULL,
                final_status TEXT NOT NULL,
                closure_notes TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (project_id) REFERENCES projects(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS requirements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'Medium',
                approval_status TEXT NOT NULL DEFAULT 'Pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS wbs_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                parent_id INTEGER,
                wbs_code TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                item_type TEXT NOT NULL DEFAULT 'Deliverable',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (parent_id) REFERENCES wbs_items(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS change_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                justification TEXT NOT NULL,
                cost_impact REAL NOT NULL DEFAULT 0,
                schedule_impact_days INTEGER NOT NULL DEFAULT 0,
                approval_status TEXT NOT NULL DEFAULT 'Pending',
                requested_by TEXT NOT NULL DEFAULT '',
                reviewer_comments TEXT NOT NULL DEFAULT '',
                reviewed_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
                    ON DELETE CASCADE
            );

            /* MODULE 3: SCHEDULE AND RESOURCE MANAGEMENT */
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                wbs_id INTEGER,
                title TEXT NOT NULL,
                assigned_to TEXT NOT NULL DEFAULT '',
                duration_days INTEGER NOT NULL DEFAULT 1,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                predecessor_id INTEGER,
                status TEXT NOT NULL DEFAULT 'Not Started',
                progress_percent INTEGER NOT NULL DEFAULT 0,
                delay_days INTEGER NOT NULL DEFAULT 0,
                planned_cost REAL NOT NULL DEFAULT 0,
                actual_cost REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (wbs_id) REFERENCES wbs_items(id)
                    ON DELETE SET NULL,
                FOREIGN KEY (predecessor_id) REFERENCES activities(id)
                    ON DELETE SET NULL
            );

            /* MODULE 5: QUALITY MANAGEMENT - DEFECT TRACKING */
            CREATE TABLE IF NOT EXISTS defects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                module_affected TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'Minor',
                assigned_to TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Open',
                resolution_notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
                    ON DELETE CASCADE
            );

            /* MODULE 5: QUALITY MANAGEMENT - QUALITY CHECKLIST */
            CREATE TABLE IF NOT EXISTS quality_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                deliverable_name TEXT NOT NULL,
                check_item TEXT NOT NULL,
                inspection_status TEXT NOT NULL DEFAULT 'Pending',
                inspected_by TEXT NOT NULL DEFAULT '',
                inspection_date TEXT,
                remarks TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
                    ON DELETE CASCADE
            );

            /* MODULE 5: RISK CONTROL - PRIORITIZATION MATRIX */
            CREATE TABLE IF NOT EXISTS risks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Technical',
                likelihood INTEGER NOT NULL DEFAULT 3,
                impact INTEGER NOT NULL DEFAULT 3,
                risk_score INTEGER NOT NULL DEFAULT 9,
                priority_level TEXT NOT NULL DEFAULT 'Medium',
                status TEXT NOT NULL DEFAULT 'Open',
                mitigation_strategy TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
                    ON DELETE CASCADE
            );

            /* MODULE 5: RISK CONTROL - PROCESS DECISION PROGRAM CHART (PDPC) */
            CREATE TABLE IF NOT EXISTS pdpc_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                process_step TEXT NOT NULL,
                potential_problem TEXT NOT NULL,
                countermeasure TEXT NOT NULL,
                action_type TEXT NOT NULL DEFAULT 'Preventive',
                status TEXT NOT NULL DEFAULT 'Selected',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
                    ON DELETE CASCADE
            );
        """)

        # Add approved_scope to existing databases if it is missing.
        project_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(projects)"
            ).fetchall()
        }

        if "approved_scope" not in project_columns:
            conn.execute("""
                ALTER TABLE projects
                ADD COLUMN approved_scope TEXT NOT NULL DEFAULT ''
            """)

        # Ensure every existing project has a current approved scope.
        project_ids = conn.execute(
            "SELECT id FROM projects"
        ).fetchall()

        if not project_ids:
            conn.execute("""
                INSERT INTO projects (
                    title, objectives, stakeholders, scope_boundaries,
                    approved_budget, deadline_weeks, status,
                    plan_scope, plan_schedule, plan_cost, plan_quality
                ) VALUES (
                    'Smart Health Care Project Management and Monitoring System',
                    'Manage patient appointments, laboratory reports, doctor schedules, online consultations and hospital billing across five hospitals.',
                    'Project manager; two backend developers; two frontend developers; one database developer; one QA engineer; hospital management.',
                    'Initial scope includes appointments, laboratory reports, doctor schedules, online consultations and hospital billing. AI diagnosis and mobile application are proposed changes pending approval.',
                    5000000.0, 16, 'In Progress',
                    'Approved features, project boundaries aur change approval process',
                    '16 weeks ka timeline, activities, dependencies aur milestones',
                    'Approved budget PKR 5,000,000, activity costs aur expenditure monitoring',
                    'Testing, inspections, defect tracking aur verification'
                )
            """)
            conn.commit()
            project_ids = conn.execute("SELECT id FROM projects").fetchall()

        for project in project_ids:
            refresh_approved_scope(conn, project["id"])

        conn.commit()

        # Check if sample data should be pre-seeded for Project 1 if empty
        if project_ids:
            first_pid = project_ids[0]["id"]
            act_count = conn.execute("SELECT COUNT(*) FROM activities WHERE project_id = ?", (first_pid,)).fetchone()[0]
            if act_count == 0:
                seed_sample_case_study(conn, first_pid)
                conn.commit()

    except sqlite3.Error:
        conn.rollback()
        app.logger.exception("Database initialization failed")
        raise

    finally:
        conn.close()


# =========================================================
# APPROVED SCOPE CONTROL
# =========================================================

def refresh_approved_scope(conn, project_id):
    """
    Only requirements with status Approved are included in the
    approved project scope.

    Pending and Rejected requirements are always excluded.
    This function must be called whenever requirements are added,
    edited, deleted, or have their approval status changed.
    """
    approved_requirements = conn.execute("""
        SELECT id, title, description
        FROM requirements
        WHERE project_id = ?
          AND approval_status = 'Approved'
        ORDER BY id ASC
    """, (project_id,)).fetchall()

    scope_lines = []
    for number, requirement in enumerate(approved_requirements, start=1):
        scope_lines.append(
            f"{number}. {requirement['title']}\n"
            f"   {requirement['description']}"
        )

    if scope_lines:
        approved_scope = "\n\n".join(scope_lines)
    else:
        approved_scope = (
            "No approved requirements. "
            "Pending and rejected requirements are excluded."
        )

    conn.execute("""
        UPDATE projects
        SET approved_scope = ?
        WHERE id = ?
    """, (approved_scope, project_id))


def get_approved_requirements(conn, project_id):
    """
    Return only approved requirements for the selected project.
    """
    return conn.execute("""
        SELECT *
        FROM requirements
        WHERE project_id = ?
          AND approval_status = 'Approved'
        ORDER BY id ASC
    """, (project_id,)).fetchall()


# =========================================================
# WBS HELPER FUNCTIONS
# =========================================================

def get_wbs_tree(items, parent_id=None):
    tree = []
    for item in items:
        if item["parent_id"] == parent_id:
            node = dict(item)
            node["children"] = get_wbs_tree(items, item["id"])
            tree.append(node)
    return tree


def get_wbs_descendant_ids(conn, item_id):
    rows = conn.execute("""
        WITH RECURSIVE descendants(id) AS (
            SELECT id FROM wbs_items WHERE id = ?
            UNION ALL
            SELECT w.id
            FROM wbs_items w
            JOIN descendants d ON w.parent_id = d.id
        )
        SELECT id FROM descendants
    """, (item_id,)).fetchall()
    return {row["id"] for row in rows}


def get_wbs_code(conn, project_id, parent_id, exclude_id=None):
    parent_code = ""
    if parent_id is not None:
        parent = conn.execute("""
            SELECT wbs_code
            FROM wbs_items
            WHERE id = ? AND project_id = ?
        """, (parent_id, project_id)).fetchone()

        if not parent:
            raise ValueError("The selected parent item was not found.")
        parent_code = parent["wbs_code"]

    query = """
        SELECT COUNT(*) AS total
        FROM wbs_items
        WHERE project_id = ? AND parent_id IS ?
    """
    params = [project_id, parent_id]

    if exclude_id is not None:
        query += " AND id != ?"
        params.append(exclude_id)

    number = conn.execute(query, params).fetchone()["total"] + 1
    return f"{parent_code}.{number}" if parent_code else str(number)


def validate_wbs_hierarchy(item_type, parent_type):
    if parent_type is None:
        return item_type == "Deliverable"
    if parent_type == "Deliverable":
        return item_type in ["Sub-deliverable", "Work Package"]
    if parent_type == "Sub-deliverable":
        return item_type == "Work Package"
    return False


# =========================================================
# MODULE 8: SCHEDULE & RESOURCE MANAGEMENT CALCULATIONS
# =========================================================

def calculate_schedule(conn, project_id, deadline_weeks=16):
    """
    Calculates activity start/end dates, identifies delayed activities,
    computes dependency impacts on successors and the final deadline,
    and formats data for a Gantt-style timeline chart.
    """
    rows = conn.execute("""
        SELECT a.*, p.title as predecessor_title, p.end_date as pred_end_date,
               p.delay_days as pred_delay, w.title as wbs_title
        FROM activities a
        LEFT JOIN activities p ON a.predecessor_id = p.id
        LEFT JOIN wbs_items w ON a.wbs_id = w.id
        WHERE a.project_id = ?
        ORDER BY a.start_date ASC, a.id ASC
    """, (project_id,)).fetchall()

    activities = [dict(r) for r in rows]
    act_map = {a["id"]: a for a in activities}

    # Find successors for each activity
    for a in activities:
        a["successors"] = []
    for a in activities:
        pid = a.get("predecessor_id")
        if pid and pid in act_map:
            act_map[pid]["successors"].append(a["id"])

    # Calculate delay impacts
    delayed_activities = []
    total_project_delay_days = 0

    for a in activities:
        is_delayed = (a["status"] == "Delayed") or (a["delay_days"] > 0)
        a["is_delayed"] = is_delayed

        # Find downstream dependent activities recursively
        impacted_ids = []
        queue = list(a["successors"])
        visited = set()
        while queue:
            curr_id = queue.pop(0)
            if curr_id not in visited:
                visited.add(curr_id)
                impacted_ids.append(curr_id)
                if curr_id in act_map:
                    queue.extend(act_map[curr_id]["successors"])

        a["impacted_tasks_count"] = len(impacted_ids)
        a["impacted_tasks_titles"] = [act_map[i]["title"] for i in impacted_ids if i in act_map]

        if is_delayed:
            delayed_activities.append(a)
            total_project_delay_days = max(total_project_delay_days, a["delay_days"])

    # Calculate project timeline boundaries
    if activities:
        try:
            start_dates = [datetime.fromisoformat(a["start_date"]) for a in activities if a["start_date"]]
            end_dates = []
            for a in activities:
                if a["end_date"]:
                    base_end = datetime.fromisoformat(a["end_date"])
                    effective_end = base_end + timedelta(days=a["delay_days"])
                    end_dates.append(effective_end)

            min_start = min(start_dates) if start_dates else datetime.now()
            max_end = max(end_dates) if end_dates else min_start + timedelta(days=deadline_weeks * 7)
        except Exception:
            min_start = datetime.now()
            max_end = min_start + timedelta(days=deadline_weeks * 7)
    else:
        min_start = datetime.now()
        max_end = min_start + timedelta(days=deadline_weeks * 7)

    total_days_span = max((max_end - min_start).days, deadline_weeks * 7, 1)

    # Approved change requests schedule impact
    approved_cr_days = conn.execute("""
        SELECT COALESCE(SUM(schedule_impact_days), 0)
        FROM change_requests
        WHERE project_id = ? AND approval_status = 'Approved'
    """, (project_id,)).fetchone()[0]

    baseline_deadline_days = deadline_weeks * 7
    revised_deadline_days = baseline_deadline_days + approved_cr_days

    projected_total_days = (max_end - min_start).days
    deadline_slippage_days = max(0, projected_total_days - revised_deadline_days)
    slippage_weeks = round(deadline_slippage_days / 7.0, 1)

    # Prepare Gantt bars data
    gantt_items = []
    for a in activities:
        try:
            s_dt = datetime.fromisoformat(a["start_date"])
            e_dt = datetime.fromisoformat(a["end_date"]) + timedelta(days=a["delay_days"])
            offset_days = max(0, (s_dt - min_start).days)
            duration_days = max(1, (e_dt - s_dt).days)

            left_pct = round((offset_days / total_days_span) * 100, 2)
            width_pct = max(round((duration_days / total_days_span) * 100, 2), 3.0)

            # Bar style class
            if a["status"] == "Completed":
                bar_class = "completed"
            elif a["is_delayed"]:
                bar_class = "delayed"
            elif a["status"] == "In Progress":
                bar_class = "ontrack"
            else:
                bar_class = "notstarted"

            gantt_items.append({
                "id": a["id"],
                "title": a["title"],
                "assigned_to": a["assigned_to"],
                "left_pct": left_pct,
                "width_pct": width_pct,
                "progress_percent": a["progress_percent"],
                "status": a["status"],
                "bar_class": bar_class,
                "duration_days": a["duration_days"],
                "delay_days": a["delay_days"],
                "start_date": a["start_date"],
                "end_date": a["end_date"],
                "predecessor_title": a.get("predecessor_title")
            })
        except Exception:
            continue

    # Milestones for timeline
    milestones_rows = conn.execute("""
        SELECT * FROM milestones WHERE project_id = ? ORDER BY due_week ASC
    """, (project_id,)).fetchall()
    milestone_items = []
    for m in milestones_rows:
        week = m["due_week"]
        m_day = (week - 1) * 7
        m_pct = min(round((m_day / total_days_span) * 100, 2), 98)
        milestone_items.append({
            "name": m["milestone_name"],
            "due_week": week,
            "pct": m_pct,
            "status": m["status"],
            "person": m["responsible_person"]
        })

    # Resource Allocation Summary (The 7 roles from case study)
    case_study_roles = [
        'Project Manager',
        'Backend Developer 1',
        'Backend Developer 2',
        'Frontend Developer 1',
        'Frontend Developer 2',
        'Database Developer',
        'Quality Assurance Engineer'
    ]
    resource_allocations = []
    for role in case_study_roles:
        role_acts = [a for a in activities if a.get("assigned_to") == role]
        total_duration = sum(a.get("duration_days", 0) for a in role_acts)
        total_planned = sum(a.get("planned_cost", 0) for a in role_acts)
        total_actual = sum(a.get("actual_cost", 0) for a in role_acts)
        completed = len([a for a in role_acts if a.get("status") == "Completed"])
        delayed = len([a for a in role_acts if a.get("status") == "Delayed" or a.get("delay_days", 0) > 0])
        avg_progress = round(sum(a.get("progress_percent", 0) for a in role_acts) / len(role_acts), 1) if role_acts else 0

        if delayed > 0:
            load_status = "Delayed Tasks"
            status_tag = "tag-delayed"
        elif completed == len(role_acts) and len(role_acts) > 0:
            load_status = "Completed"
            status_tag = "tag-completed"
        elif len(role_acts) > 0:
            load_status = "Active"
            status_tag = "tag-in-progress"
        else:
            load_status = "Available"
            status_tag = "tag-notstarted"

        resource_allocations.append({
            "role": role,
            "tasks_count": len(role_acts),
            "activities": role_acts,
            "total_duration": total_duration,
            "total_planned_cost": total_planned,
            "total_actual_cost": total_actual,
            "completed_count": completed,
            "delayed_count": delayed,
            "avg_progress": avg_progress,
            "status": load_status,
            "status_tag": status_tag
        })

    return {
        "activities": activities,
        "delayed_activities": delayed_activities,
        "delayed_count": len(delayed_activities),
        "total_delay_days": total_project_delay_days,
        "baseline_deadline_weeks": deadline_weeks,
        "baseline_deadline_days": baseline_deadline_days,
        "approved_cr_days": approved_cr_days,
        "revised_deadline_weeks": round(revised_deadline_days / 7.0, 1),
        "projected_total_days": projected_total_days,
        "slippage_days": deadline_slippage_days,
        "slippage_weeks": slippage_weeks,
        "deadline_status": "Delayed" if deadline_slippage_days > 0 else "On Schedule",
        "gantt_items": gantt_items,
        "milestones": milestone_items,
        "resources": resource_allocations,
        "total_days_span": total_days_span
    }



# =========================================================
# MODULE 9: COST MANAGEMENT & EVM CALCULATIONS
# =========================================================

def calculate_evm(conn, project_id, approved_budget=0):
    """
    Computes Planned Value (PV), Earned Value (EV), Actual Cost (AC),
    Cost Performance Index (CPI), Schedule Performance Index (SPI),
    Estimate at Completion (EAC), Cost/Schedule Variances,
    and evaluates threshold alerts for overruns and delays.
    """
    activities = conn.execute("""
        SELECT planned_cost, actual_cost, progress_percent, status
        FROM activities
        WHERE project_id = ?
    """, (project_id,)).fetchall()

    bac = sum(row["planned_cost"] for row in activities) or approved_budget or 0
    ac = sum(row["actual_cost"] for row in activities)

    # Earned Value (EV) = sum(Progress% * Planned Cost)
    ev = sum((row["planned_cost"] * (row["progress_percent"] / 100.0)) for row in activities)

    # Planned Value (PV) = Scheduled budget to date based on activity completion/progress
    pv = 0
    for row in activities:
        if row["status"] == "Completed":
            pv += row["planned_cost"]
        elif row["status"] in ["In Progress", "Delayed"]:
            pv += row["planned_cost"] * 0.75
        else:
            pv += 0

    if pv == 0 and bac > 0 and len(activities) > 0:
        pv = bac * 0.60  # Scheduled baseline estimation

    # Cost Performance Index (CPI) = EV / AC
    cpi = round(ev / ac, 2) if ac > 0 else 1.0

    # Schedule Performance Index (SPI) = EV / PV
    spi = round(ev / pv, 2) if pv > 0 else 1.0

    # Variances
    cv = round(ev - ac, 2)
    sv = round(ev - pv, 2)

    # Estimate at Completion (EAC) = BAC / CPI
    eac = round(bac / cpi, 2) if cpi > 0 else bac
    vac = round(bac - eac, 2)

    # Approved change requests impact on budget
    approved_changes_cost = conn.execute("""
        SELECT COALESCE(SUM(cost_impact), 0)
        FROM change_requests
        WHERE project_id = ? AND approval_status = 'Approved'
    """, (project_id,)).fetchone()[0]

    baseline_budget = approved_budget
    revised_budget = baseline_budget + approved_changes_cost

    # Automated Threshold Warning Messages
    warnings = []
    if cpi < 0.85:
        warnings.append({
            "level": "critical",
            "title": "CRITICAL COST OVERRUN DETECTED",
            "message": f"Cost Performance Index (CPI = {cpi:.2f}) is below the 0.85 threshold. The project is spending PKR {(1/cpi):.2f} for every PKR 1.00 of earned value! Cost Variance: -PKR {abs(cv):,.2f}."
        })
    elif cpi < 1.0:
        warnings.append({
            "level": "warning",
            "title": "COST OVERRUN WARNING",
            "message": f"Cost Performance Index (CPI = {cpi:.2f}) is below 1.00. Project expenditures are exceeding the budgeted cost of completed work (CV = -PKR {abs(cv):,.2f})."
        })

    if spi < 0.85:
        warnings.append({
            "level": "critical",
            "title": "CRITICAL SCHEDULE DELAY DETECTED",
            "message": f"Schedule Performance Index (SPI = {spi:.2f}) is below the 0.85 threshold. Work progress is lagging significantly behind the planned schedule (SV = -PKR {abs(sv):,.2f})."
        })
    elif spi < 1.0:
        warnings.append({
            "level": "warning",
            "title": "SCHEDULE DEVIATION WARNING",
            "message": f"Schedule Performance Index (SPI = {spi:.2f}) indicates schedule slippage. Earned value is less than planned value by PKR {abs(sv):,.2f}."
        })

    if ac > revised_budget and revised_budget > 0:
        warnings.append({
            "level": "critical",
            "title": "APPROVED BUDGET EXCEEDED",
            "message": f"Actual expenditure (PKR {ac:,.2f}) has exceeded the approved project budget of PKR {revised_budget:,.2f} by PKR {(ac - revised_budget):,.2f}!"
        })
    elif eac > revised_budget and revised_budget > 0:
        warnings.append({
            "level": "warning",
            "title": "PROJECTED BUDGET OVERRUN AT COMPLETION",
            "message": f"Estimate at Completion (EAC = PKR {eac:,.2f}) exceeds the approved project budget by PKR {(eac - revised_budget):,.2f}."
        })

    return {
        "bac": bac,
        "pv": round(pv, 2),
        "ev": round(ev, 2),
        "ac": round(ac, 2),
        "cpi": cpi,
        "spi": spi,
        "cv": cv,
        "sv": sv,
        "eac": eac,
        "vac": vac,
        "baseline_budget": baseline_budget,
        "approved_changes_cost": approved_changes_cost,
        "revised_budget": revised_budget,
        "warnings": warnings,
        "is_cost_overrun": cpi < 1.0,
        "is_schedule_delayed": spi < 1.0
    }


# =========================================================
# MODULE 10: QUALITY MANAGEMENT & RISK CONTROL
# =========================================================

def calculate_quality_risk(conn, project_id):
    """
    Computes metrics for defect tracking, quality checklists,
    a 5x5 Risk Prioritization Matrix (Heat Map), and PDPC contingency views.
    """
    # Defect Tracking
    defects = conn.execute("""
        SELECT * FROM defects WHERE project_id = ? ORDER BY id DESC
    """, (project_id,)).fetchall()
    defect_list = [dict(d) for d in defects]

    open_defects = [d for d in defect_list if d["status"] in ["Open", "In Progress"]]
    critical_defects = [d for d in defect_list if d["severity"] in ["Critical", "Major"]]
    unresolved_critical = [d for d in open_defects if d["severity"] in ["Critical", "Major"]]

    # Quality Checklist
    checks = conn.execute("""
        SELECT * FROM quality_checks WHERE project_id = ? ORDER BY id DESC
    """, (project_id,)).fetchall()
    check_list = [dict(c) for c in checks]

    passed_checks = [c for c in check_list if c["inspection_status"] == "Passed"]
    failed_checks = [c for c in check_list if c["inspection_status"] == "Failed"]
    pass_rate = round((len(passed_checks) / len(check_list) * 100), 1) if check_list else 0

    # Risk Prioritization Matrix (5x5 Heat Map)
    risks = conn.execute("""
        SELECT * FROM risks WHERE project_id = ? ORDER BY risk_score DESC
    """, (project_id,)).fetchall()
    risk_list = [dict(r) for r in risks]

    critical_risks = [r for r in risk_list if r["priority_level"] == "Critical"]
    high_risks = [r for r in risk_list if r["priority_level"] == "High"]

    matrix_cells = {}
    for likelihood in range(1, 6):
        for impact in range(1, 6):
            cell_risks = [r for r in risk_list if r["likelihood"] == likelihood and r["impact"] == impact]
            score = likelihood * impact
            if score >= 15:
                cell_class = "cell-crit"
            elif score >= 10:
                cell_class = "cell-high"
            elif score >= 5:
                cell_class = "cell-med"
            else:
                cell_class = "cell-low"
            matrix_cells[(likelihood, impact)] = {
                "score": score,
                "class": cell_class,
                "risks": cell_risks
            }

    # PDPC Items grouped by Process Step
    pdpc_rows = conn.execute("""
        SELECT * FROM pdpc_items WHERE project_id = ? ORDER BY id ASC
    """, (project_id,)).fetchall()
    pdpc_grouped = {}
    for item in pdpc_rows:
        step = item["process_step"]
        if step not in pdpc_grouped:
            pdpc_grouped[step] = []
        pdpc_grouped[step].append(dict(item))

    return {
        "defects": defect_list,
        "total_defects": len(defect_list),
        "open_defects": len(open_defects),
        "unresolved_critical": unresolved_critical,
        "unresolved_critical_count": len(unresolved_critical),
        "checks": check_list,
        "total_checks": len(check_list),
        "passed_checks": len(passed_checks),
        "failed_checks": len(failed_checks),
        "pass_rate": pass_rate,
        "risks": risk_list,
        "total_risks": len(risk_list),
        "critical_risks_count": len(critical_risks),
        "high_risks_count": len(high_risks),
        "matrix_cells": matrix_cells,
        "pdpc_grouped": pdpc_grouped
    }


# =========================================================
# MODULE 11: INTEGRATION, VALIDATION & DASHBOARD
# =========================================================

def calculate_change_impact(conn, project_id, project):
    """
    Demonstrates how approved change requests affect Scope, Schedule, and Budget
    (Mandatory Implementation Requirement 4).
    """
    baseline_budget = project["approved_budget"] if project else 0
    baseline_weeks = project["deadline_weeks"] if project else 16
    baseline_days = baseline_weeks * 7

    approved_crs = conn.execute("""
        SELECT * FROM change_requests
        WHERE project_id = ? AND approval_status = 'Approved'
        ORDER BY id ASC
    """, (project_id,)).fetchall()

    total_cost_impact = sum(cr["cost_impact"] for cr in approved_crs)
    total_schedule_impact_days = sum(cr["schedule_impact_days"] for cr in approved_crs)

    revised_budget = baseline_budget + total_cost_impact
    revised_days = baseline_days + total_schedule_impact_days
    revised_weeks = round(revised_days / 7.0, 1)

    return {
        "baseline_budget": baseline_budget,
        "approved_crs_cost": total_cost_impact,
        "revised_budget": revised_budget,
        "baseline_weeks": baseline_weeks,
        "baseline_days": baseline_days,
        "approved_crs_days": total_schedule_impact_days,
        "revised_weeks": revised_weeks,
        "revised_days": revised_days,
        "approved_crs": [dict(cr) for cr in approved_crs],
        "approved_crs_count": len(approved_crs)
    }


def calculate_dashboard(conn, project_id, schedule_data, evm_data, qr_data, change_requests):
    """
    Generates an executive project dashboard and health report showing
    overall progress, pending change requests, delayed activities,
    budget status, and unresolved critical defects.
    """
    activities = schedule_data.get("activities", [])
    if activities:
        total_planned_cost = sum(a["planned_cost"] for a in activities)
        if total_planned_cost > 0:
            overall_progress = sum((a["progress_percent"] * a["planned_cost"]) for a in activities) / total_planned_cost
        else:
            overall_progress = sum(a["progress_percent"] for a in activities) / len(activities)
    else:
        overall_progress = 0

    pending_crs = [cr for cr in change_requests if cr["approval_status"] == "Pending"]
    delayed_acts = schedule_data.get("delayed_activities", [])
    unresolved_crit = qr_data.get("unresolved_critical", [])

    # Project Health Assessment
    cpi = evm_data.get("cpi", 1.0)
    spi = evm_data.get("spi", 1.0)
    slippage = schedule_data.get("slippage_days", 0)
    delayed_cnt = schedule_data.get("delayed_count", 0)

    if len(unresolved_crit) > 0 or cpi < 0.85 or slippage > 14:
        health_status = "Critical Attention Needed"
        health_class = "tag-critical"
    elif cpi < 1.0 or delayed_cnt > 0 or len(pending_crs) > 0:
        health_status = "Performance Warning"
        health_class = "tag-warning"
    else:
        health_status = "Healthy / On Track"
        health_class = "tag-healthy"

    return {
        "overall_progress": round(overall_progress, 1),
        "pending_crs": pending_crs,
        "pending_crs_count": len(pending_crs),
        "delayed_activities": delayed_acts,
        "delayed_count": len(delayed_acts),
        "budget_spent": evm_data.get("ac", 0),
        "budget_planned": evm_data.get("bac", 0),
        "budget_revised": evm_data.get("revised_budget", 0),
        "cpi": cpi,
        "spi": spi,
        "unresolved_critical": unresolved_crit,
        "unresolved_critical_count": len(unresolved_crit),
        "health_status": health_status,
        "health_class": health_class
    }


# =========================================================
# SAMPLE DATA SEEDER
# =========================================================

def seed_sample_case_study(conn, project_id):
    """
    Seeds realistic sample data based on the SPM Exam Case Study:
    - Smart Healthcare network for 5 hospitals
    - Core modules: appointments, lab reports, doctor schedules, consultations, billing
    - Baseline: 16 weeks duration, PKR 5,000,000 approved budget
    - Team: Project manager, 2 backend devs, 2 frontend devs, 1 DB dev, 1 QA engineer (7 roles)
    - Additional requirements: AI preliminary diagnosis & mobile app (+PKR 800,000, +3 weeks)
    - Critical testing defects in appointment scheduling & patient records
    """
    # 0. Clean prior records for this project to maintain idempotency
    conn.execute("DELETE FROM activities WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM defects WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM quality_checks WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM risks WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM pdpc_items WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM change_requests WHERE project_id = ?", (project_id,))

    # 1. Activities with dynamic predecessor linking
    activities_def = [
        ("Requirements Engineering & System Architecture", "Project Manager", 14, "2026-07-01", "2026-07-14", None, "Completed", 100, 0, 400000.0, 390000.0),
        ("Database Schema Design & Central EHR Repository", "Database Developer", 14, "2026-07-15", "2026-07-28", 0, "Completed", 100, 0, 450000.0, 470000.0),
        ("Patient Appointment Scheduling Module", "Backend Developer 1", 18, "2026-07-29", "2026-08-15", 1, "Delayed", 85, 7, 550000.0, 680000.0),
        ("Patient Medical Record & EHR Management", "Database Developer", 18, "2026-07-29", "2026-08-15", 1, "Delayed", 80, 7, 600000.0, 720000.0),
        ("Laboratory Reports Management Module", "Backend Developer 2", 14, "2026-08-16", "2026-08-29", 2, "In Progress", 75, 4, 500000.0, 520000.0),
        ("Doctor Schedule & Availability Management", "Frontend Developer 1", 14, "2026-08-16", "2026-08-29", 2, "In Progress", 90, 0, 450000.0, 440000.0),
        ("Online Consultation Video & Chat Service", "Frontend Developer 2", 16, "2026-08-30", "2026-09-14", 5, "In Progress", 60, 5, 550000.0, 590000.0),
        ("Hospital Billing & Multi-Hospital Invoicing", "Backend Developer 1", 15, "2026-08-30", "2026-09-13", 4, "In Progress", 50, 0, 500000.0, 510000.0),
        ("AI Preliminary Diagnosis Module (Approved Change)", "Backend Developer 2", 14, "2026-09-14", "2026-09-27", 6, "In Progress", 40, 0, 500000.0, 420000.0),
        ("Mobile Application Development (Approved Change)", "Frontend Developer 1", 18, "2026-09-14", "2026-10-01", 6, "In Progress", 35, 0, 300000.0, 330000.0),
        ("System Integration Across 5 Hospital Networks", "Project Manager", 14, "2026-10-02", "2026-10-15", 8, "Not Started", 0, 0, 400000.0, 0.0),
        ("Comprehensive QA, Security & Acceptance Audit", "Quality Assurance Engineer", 14, "2026-10-16", "2026-10-29", 10, "Not Started", 0, 0, 300000.0, 0.0),
    ]

    inserted_ids = []
    for title, assigned_to, dur, s_date, e_date, pred_idx, status, prog, delay, p_cost, a_cost in activities_def:
        pred_id = inserted_ids[pred_idx] if pred_idx is not None else None
        cursor = conn.execute("""
            INSERT INTO activities (
                project_id, title, assigned_to, duration_days, start_date, end_date,
                predecessor_id, status, progress_percent, delay_days, planned_cost, actual_cost
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (project_id, title, assigned_to, dur, s_date, e_date, pred_id, status, prog, delay, p_cost, a_cost))
        inserted_ids.append(cursor.lastrowid)

    # 2. Defects (Reflecting case study critical defects in appointment scheduling & patient records)
    sample_defects = [
        (project_id, "Appointment Scheduling Concurrency Collision - Double Booking", "Concurrent user requests allow two patients to book the same doctor slot at the same time across hospital terminals. Race condition in database slot reservation.", "Patient Appointments", "Critical", "Quality Assurance Engineer", "Open", "Needs atomic row lock and isolation check."),
        (project_id, "Patient Medical Record Synchronization Failure Across 5 Hospitals", "Offline synchronization fails during network drops, causing stale patient medical records at remote branch hospitals.", "Patient Records & EHR", "Critical", "Database Developer", "In Progress", "Implementing retry queue and data conflict resolution protocol."),
        (project_id, "Multi-Hospital Billing Invoice Tax Rounding Discrepancy", "Consolidated billing calculations had 0.5% rounding discrepancy during multi-branch invoicing.", "Hospital Billing", "Major", "Backend Developer 1", "Resolved", "Updated precision to 4 decimal places with standard banker rounding."),
        (project_id, "Video Consultation Connection Drop on High-Latency 3G Link", "WebRTC peer connection drops unexpectedly during outpatient telemedicine sessions with low bandwidth.", "Online Consultations & Chat", "Major", "Frontend Developer 2", "In Progress", "Adding adaptive bitrate codec and audio-only fallback mode.")
    ]

    for d in sample_defects:
        conn.execute("""
            INSERT INTO defects (
                project_id, title, description, module_affected,
                severity, assigned_to, status, resolution_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, d)

    # 3. Quality Checklist
    sample_checks = [
        (project_id, "Patient Appointment Scheduling", "Concurrency & Double-Booking Stress Test (500 simultaneous users)", "Failed", "Quality Assurance Engineer", "2026-08-20", "Failed due to concurrent slot collision. Critical hotfix required."),
        (project_id, "Patient Record Management", "HIPAA Data Privacy & Multi-Hospital EHR Synchronization Audit", "Failed", "Quality Assurance Engineer", "2026-08-22", "Failed due to intermittent branch packet drop."),
        (project_id, "Laboratory Reports Module", "HL7 / FHIR Medical Diagnostic Format Compliance", "Passed", "Quality Assurance Engineer", "2026-08-25", "Passed: Schema conforms to hospital network lab specifications."),
        (project_id, "Doctor Schedule Management", "Real-Time OPD Schedule Calendar Sync", "Passed", "Quality Assurance Engineer", "2026-08-26", "Passed: Screen sync verified under 2-second threshold."),
        (project_id, "Hospital Billing System", "Payment Gateway Rollback & Multi-Hospital Tax Audit", "Passed", "Quality Assurance Engineer", "2026-08-28", "Passed: Automated transaction rollbacks verified.")
    ]

    for c in sample_checks:
        conn.execute("""
            INSERT INTO quality_checks (
                project_id, deliverable_name, check_item,
                inspection_status, inspected_by, inspection_date, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, c)

    # 4. Risks (5x5 Prioritization Matrix)
    sample_risks = [
        (project_id, "Critical Defects in Scheduling and EHR Data Sync Delaying Go-Live", "Quality", 5, 4, 20, "Critical", "Open", "QA Engineer dedicated to automated regression suite; hotfix sprint with Backend Devs."),
        (project_id, "Multi-Hospital Network Latency & Intermittent Branch Outages", "Technical", 4, 4, 16, "Critical", "Mitigating", "Deploy local cache servers at each hospital with asynchronous sync queue."),
        (project_id, "Scope Creep from AI Diagnosis and Mobile Application Additions", "Scope", 4, 4, 16, "Critical", "Mitigating", "Formal change request procedure with +PKR 800,000 budget and +3 weeks timeline approved."),
        (project_id, "Doctor and Healthcare Staff Training Resistance to New Portal", "Schedule", 3, 3, 9, "Medium", "Mitigating", "Provide interactive UI with in-app guided walkthroughs and hospital training sessions."),
        (project_id, "Server Infrastructure & Cloud Hosting Cost Overruns", "Cost", 2, 3, 6, "Medium", "Closed", "Signed fixed-tier annual service contract with cloud infrastructure provider.")
    ]

    for r in sample_risks:
        conn.execute("""
            INSERT INTO risks (
                project_id, title, category, likelihood, impact,
                risk_score, priority_level, status, mitigation_strategy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, r)

    # 5. Process Decision Program Chart (PDPC) Items
    sample_pdpc = [
        (project_id, "Hospital Network Deployment", "Intermittent WAN outage between 5 hospitals", "Deploy local SQLite/Redis caching proxy for offline operations", "Preventive", "Selected"),
        (project_id, "Hospital Network Deployment", "Bandwidth throttling during peak morning hours", "Dedicated MPLS leased lines for heavy diagnostic imaging", "Preventive", "Backup Plan"),
        (project_id, "Appointment Scheduling Integration", "Concurrent booking collision / race condition", "Implement distributed row-level locks and optimistic concurrency token", "Corrective", "Selected"),
        (project_id, "Appointment Scheduling Integration", "Doctor emergency cancellation without patient notice", "Automated SMS/Email broadcast and automated slot reallocation bot", "Preventive", "Selected"),
        (project_id, "Patient Record Synchronization", "Conflicting patient records created at different hospitals", "Apply Lamport timestamps with automated central database conflict resolution", "Corrective", "Selected"),
        (project_id, "Hospital Billing System", "Payment gateway timeout during insurance claim settlement", "Two-phase commit transaction protocol with asynchronous reconciliation", "Corrective", "Selected")
    ]

    for p in sample_pdpc:
        conn.execute("""
            INSERT INTO pdpc_items (
                project_id, process_step, potential_problem,
                countermeasure, action_type, status
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, p)

    # 6. Change Requests (Matching case study +PKR 800,000 and +3 weeks)
    crs_data = [
        (project_id, "AI-Based Preliminary Diagnosis Module", "Introduce an AI-driven clinical preliminary diagnosis triage module to assist medical staff and prioritize high-risk patients across 5 hospital emergency departments.", "Hospital management and chief medical officers requested AI diagnostic assistance to decrease triage wait times and enhance diagnostic accuracy.", 500000.0, 14, "Approved", "Hospital Management", "Approved by Project Manager Shehroz Mehmood and Change Control Board. Adds PKR 500,000 to budget and extends deadline by 2 weeks.", "2026-08-10 10:00:00"),
        (project_id, "Cross-Platform Mobile Application", "Develop and deploy native Android and iOS mobile application for patients to schedule appointments, view lab reports, and consult doctors remotely.", "High patient demand for smartphone accessibility to reduce physical OPD visits across the 5 hospitals.", 300000.0, 7, "Approved", "Patient Care Committee", "Approved by Project Manager Shehroz Mehmood and CCB. Adds PKR 300,000 to budget and extends deadline by 1 week.", "2026-08-15 14:30:00"),
        (project_id, "Emergency Ward Real-Time Bed Occupancy Dashboard", "Implement an interactive live display showing real-time bed availability in emergency and intensive care units.", "Hospital operations requires immediate visibility of critical care bed status to coordinate emergency admissions.", 150000.0, 7, "Pending", "Hospital Administration", "Under review by engineering team regarding ICU sensor hardware integration.", None),
        (project_id, "Cryptocurrency Medical Billing Settlement", "Allow patients to pay consultation and lab fees using digital cryptocurrency tokens.", "External fintech partnership proposal.", 200000.0, 10, "Rejected", "Fintech Consultant", "Rejected: Non-compliant with hospital regulatory policies and financial volatility risks.", "2026-08-20 16:00:00")
    ]

    for cr in crs_data:
        conn.execute("""
            INSERT INTO change_requests (
                project_id, title, description, justification,
                cost_impact, schedule_impact_days, approval_status,
                requested_by, reviewer_comments, reviewed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, cr)

    # 7. Update Project 1 parameters
    conn.execute("""
        UPDATE projects
        SET approved_budget = 5000000.0,
            deadline_weeks = 16,
            status = 'In Progress'
        WHERE id = ?
    """, (project_id,))


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def index():
    conn = get_db()

    try:
        projects = conn.execute("""
            SELECT * FROM projects ORDER BY id DESC
        """).fetchall()

        edit_id = request.args.get("edit", type=int)
        project = None

        if edit_id:
            project = conn.execute(
                "SELECT * FROM projects WHERE id = ?",
                (edit_id,)
            ).fetchone()

            if not project:
                flash("The selected project was not found.", "error")

        # Determine active project for dashboards
        active_project_id = request.args.get("project_id", type=int)
        if not active_project_id and projects:
            p_ids = [p["id"] for p in projects]
            active_project_id = 1 if 1 in p_ids else p_ids[0]

        active_project = None
        if active_project_id:
            active_project = conn.execute(
                "SELECT * FROM projects WHERE id = ?",
                (active_project_id,)
            ).fetchone()

        milestones = conn.execute("""
            SELECT m.*, p.title AS project_title
            FROM milestones m
            JOIN projects p ON m.project_id = p.id
            ORDER BY m.id DESC
        """).fetchall()

        closures = conn.execute("""
            SELECT c.*, p.title AS project_title
            FROM closures c
            JOIN projects p ON c.project_id = p.id
            ORDER BY c.id DESC
        """).fetchall()

        requirements = conn.execute("""
            SELECT r.*, p.title AS project_title
            FROM requirements r
            JOIN projects p ON r.project_id = p.id
            ORDER BY r.id DESC
        """).fetchall()

        edit_requirement_id = request.args.get("edit_requirement", type=int)
        requirement = None
        if edit_requirement_id:
            requirement = conn.execute("""
                SELECT * FROM requirements WHERE id = ?
            """, (edit_requirement_id,)).fetchone()
            if not requirement:
                flash("The selected requirement was not found.", "error")

        wbs_items = conn.execute("""
            SELECT w.*, p.title AS project_title
            FROM wbs_items w
            JOIN projects p ON w.project_id = p.id
            ORDER BY w.id ASC
        """).fetchall()

        wbs_trees = {}
        for current_project in projects:
            project_items = [
                dict(item)
                for item in wbs_items
                if item["project_id"] == current_project["id"]
            ]
            wbs_trees[current_project["id"]] = get_wbs_tree(project_items)

        edit_wbs_id = request.args.get("edit_wbs", type=int)
        wbs_item = None
        if edit_wbs_id:
            wbs_item = conn.execute("""
                SELECT * FROM wbs_items WHERE id = ?
            """, (edit_wbs_id,)).fetchone()
            if not wbs_item:
                flash("The WBS item was not found.", "error")

        change_requests = conn.execute("""
            SELECT cr.*, p.title AS project_title
            FROM change_requests cr
            JOIN projects p ON cr.project_id = p.id
            ORDER BY cr.id DESC
        """).fetchall()

        change_request_counts = conn.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN approval_status = 'Pending' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN approval_status = 'Approved' THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN approval_status = 'Rejected' THEN 1 ELSE 0 END) AS rejected
            FROM change_requests
        """).fetchone()

        approved_requirements = conn.execute("""
            SELECT r.*, p.title AS project_title
            FROM requirements r
            JOIN projects p ON r.project_id = p.id
            WHERE r.approval_status = 'Approved'
            ORDER BY r.project_id, r.id
        """).fetchall()

        # Module 8: Schedule & Resource Data
        activities = []
        schedule_data = {}
        edit_activity_id = request.args.get("edit_activity", type=int)
        activity = None

        if active_project_id:
            activities = conn.execute("""
                SELECT a.*, p.title as predecessor_title
                FROM activities a
                LEFT JOIN activities p ON a.predecessor_id = p.id
                WHERE a.project_id = ?
                ORDER BY a.start_date ASC, a.id ASC
            """, (active_project_id,)).fetchall()

            deadline_w = active_project["deadline_weeks"] if active_project else 16
            schedule_data = calculate_schedule(conn, active_project_id, deadline_w)

            if edit_activity_id:
                activity = conn.execute("SELECT * FROM activities WHERE id = ?", (edit_activity_id,)).fetchone()

        # Module 9: Cost Management & EVM Data
        evm_data = {}
        if active_project_id:
            app_budget = active_project["approved_budget"] if active_project else 0
            evm_data = calculate_evm(conn, active_project_id, app_budget)

        # Module 10: Quality Management & Risk Control Data
        qr_data = {}
        defects = []
        quality_checks = []
        risks = []
        pdpc_items = []
        edit_defect_id = request.args.get("edit_defect", type=int)
        defect = None
        edit_check_id = request.args.get("edit_check", type=int)
        quality_check = None
        edit_risk_id = request.args.get("edit_risk", type=int)
        risk = None
        edit_pdpc_id = request.args.get("edit_pdpc", type=int)
        pdpc_item = None

        if active_project_id:
            qr_data = calculate_quality_risk(conn, active_project_id)
            defects = qr_data.get("defects", [])
            quality_checks = qr_data.get("checks", [])
            risks = qr_data.get("risks", [])

            pdpc_items = conn.execute("""
                SELECT * FROM pdpc_items WHERE project_id = ? ORDER BY id ASC
            """, (active_project_id,)).fetchall()

            if edit_defect_id:
                defect = conn.execute("SELECT * FROM defects WHERE id = ?", (edit_defect_id,)).fetchone()
            if edit_check_id:
                quality_check = conn.execute("SELECT * FROM quality_checks WHERE id = ?", (edit_check_id,)).fetchone()
            if edit_risk_id:
                risk = conn.execute("SELECT * FROM risks WHERE id = ?", (edit_risk_id,)).fetchone()
            if edit_pdpc_id:
                pdpc_item = conn.execute("SELECT * FROM pdpc_items WHERE id = ?", (edit_pdpc_id,)).fetchone()

        # Module 11: Change Impact Demonstration & Integrated Dashboard
        change_impact_data = {}
        dashboard_data = {}
        if active_project_id:
            change_impact_data = calculate_change_impact(conn, active_project_id, active_project)
            active_project_crs = [cr for cr in change_requests if cr["project_id"] == active_project_id]
            dashboard_data = calculate_dashboard(conn, active_project_id, schedule_data, evm_data, qr_data, active_project_crs)

        return render_template(
            "index.html",
            projects=projects,
            project=project,
            active_project_id=active_project_id,
            active_project=active_project,
            milestones=milestones,
            closures=closures,
            requirements=requirements,
            requirement=requirement,
            today=date.today().isoformat(),
            wbs_trees=wbs_trees,
            wbs_item=wbs_item,
            wbs_items=wbs_items,
            change_requests=change_requests,
            change_request_counts=change_request_counts,
            approved_requirements=approved_requirements,
            # New Modules Context
            activities=activities,
            activity=activity,
            schedule_data=schedule_data,
            evm_data=evm_data,
            defects=defects,
            defect=defect,
            quality_checks=quality_checks,
            quality_check=quality_check,
            risks=risks,
            risk=risk,
            pdpc_items=pdpc_items,
            pdpc_item=pdpc_item,
            qr_data=qr_data,
            change_impact_data=change_impact_data,
            dashboard_data=dashboard_data
        )

    finally:
        conn.close()


# =========================================================
# MODULE 1: PROJECT MANAGEMENT
# =========================================================

@app.route("/save", methods=["POST"])
def save_project():
    project_id = request.form.get("project_id", type=int)

    title = request.form.get("title", "").strip()
    objectives = request.form.get("objectives", "").strip()
    stakeholders = request.form.get("stakeholders", "").strip()
    scope_boundaries = request.form.get("scope_boundaries", "").strip()

    plan_scope = request.form.get("plan_scope", "").strip()
    plan_schedule = request.form.get("plan_schedule", "").strip()
    plan_cost = request.form.get("plan_cost", "").strip()
    plan_quality = request.form.get("plan_quality", "").strip()
    status = request.form.get("status", "Planning").strip()

    try:
        approved_budget = float(request.form.get("approved_budget", 0) or 0)
        deadline_weeks = int(request.form.get("deadline_weeks", 1) or 1)
    except (TypeError, ValueError):
        flash("Enter valid budget and deadline values.", "error")
        return redirect(url_for("index"))

    if not all([title, objectives, stakeholders, scope_boundaries]):
        flash("Please complete all required project fields.", "error")
        return redirect(url_for("index"))

    if approved_budget < 0 or deadline_weeks < 1:
        flash("Budget cannot be negative and deadline must be at least one week.", "error")
        return redirect(url_for("index"))

    if status not in ["Planning", "In Progress", "On Hold", "Completed", "Cancelled"]:
        status = "Planning"

    conn = get_db()

    try:
        if project_id:
            existing = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not existing:
                flash("Project not found.", "error")
                return redirect(url_for("index"))

            conn.execute("""
                UPDATE projects
                SET title=?, objectives=?, stakeholders=?,
                    scope_boundaries=?, approved_budget=?,
                    deadline_weeks=?, status=?, plan_scope=?,
                    plan_schedule=?, plan_cost=?, plan_quality=?
                WHERE id=?
            """, (
                title, objectives, stakeholders, scope_boundaries,
                approved_budget, deadline_weeks, status, plan_scope,
                plan_schedule, plan_cost, plan_quality, project_id
            ))
            flash("Project updated successfully.", "success")
        else:
            conn.execute("""
                INSERT INTO projects (
                    title, objectives, stakeholders, scope_boundaries,
                    approved_budget, deadline_weeks, status, plan_scope,
                    plan_schedule, plan_cost, plan_quality
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                title, objectives, stakeholders, scope_boundaries,
                approved_budget, deadline_weeks, status, plan_scope,
                plan_schedule, plan_cost, plan_quality
            ))
            flash("Project saved successfully.", "success")

        conn.commit()

    except sqlite3.Error:
        conn.rollback()
        app.logger.exception("Project save failed")
        flash("Database error while saving project.", "error")

    finally:
        conn.close()

    if project_id:
        return redirect(url_for("index", project_id=project_id) + "#project-plan")
    return redirect(url_for("index") + "#project-plan")


@app.route("/delete/<int:project_id>", methods=["POST"])
def delete_project(project_id):
    conn = get_db()
    try:
        result = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
        flash(
            "Project and related records deleted successfully." if result.rowcount else "Project not found.",
            "success" if result.rowcount else "error"
        )
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to delete project.", "error")
    finally:
        conn.close()

    return redirect(url_for("index") + "#project-plan")


# =========================================================
# MILESTONES
# =========================================================

@app.route("/add_milestone", methods=["POST"])
def add_milestone():
    project_id = request.form.get("project_id", type=int)
    name = request.form.get("milestone_name", "").strip()
    person = request.form.get("responsible_person", "").strip()
    status = request.form.get("milestone_status", "Pending").strip()

    try:
        due_week = int(request.form.get("due_week", 1))
    except (TypeError, ValueError):
        flash("Enter a valid due week.", "error")
        return redirect(url_for("index") + "#milestones")

    if status not in ["Pending", "In Progress", "Completed"]:
        status = "Pending"

    if not project_id or not name or due_week < 1:
        flash("Project, milestone name and valid due week are required.", "error")
        return redirect(url_for("index") + "#milestones")

    conn = get_db()
    try:
        exists = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not exists:
            flash("Project not found.", "error")
            return redirect(url_for("index") + "#milestones")

        conn.execute("""
            INSERT INTO milestones (
                project_id, milestone_name, due_week, status, responsible_person
            )
            VALUES (?, ?, ?, ?, ?)
        """, (project_id, name, due_week, status, person))
        conn.commit()
        flash("Milestone added successfully.", "success")
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to save milestone.", "error")
    finally:
        conn.close()

    return redirect(url_for("index", project_id=project_id) + "#milestones")


@app.route("/delete_milestone/<int:milestone_id>", methods=["POST"])
def delete_milestone(milestone_id):
    conn = get_db()
    project_id = None
    try:
        row = conn.execute("SELECT project_id FROM milestones WHERE id = ?", (milestone_id,)).fetchone()
        if row:
            project_id = row["project_id"]
        result = conn.execute("DELETE FROM milestones WHERE id = ?", (milestone_id,))
        conn.commit()
        flash(
            "Milestone deleted successfully." if result.rowcount else "Milestone not found.",
            "success" if result.rowcount else "error"
        )
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to delete milestone.", "error")
    finally:
        conn.close()

    if project_id:
        return redirect(url_for("index", project_id=project_id) + "#milestones")
    return redirect(url_for("index") + "#milestones")


# =========================================================
# PROJECT CLOSURE
# =========================================================

@app.route("/save_closure", methods=["POST"])
def save_closure():
    project_id = request.form.get("project_id", type=int)
    completion_date = request.form.get("completion_date", "").strip()
    final_status = request.form.get("final_status", "").strip()
    notes = request.form.get("closure_notes", "").strip()

    if not project_id or not completion_date:
        flash("Select a project and completion date.", "error")
        return redirect(url_for("index") + "#closures")

    try:
        date.fromisoformat(completion_date)
    except ValueError:
        flash("Enter a valid completion date.", "error")
        return redirect(url_for("index") + "#closures")

    if final_status not in ["Completed", "Cancelled"]:
        flash("Final status must be Completed or Cancelled.", "error")
        return redirect(url_for("index") + "#closures")

    conn = get_db()
    try:
        exists = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not exists:
            flash("Project not found.", "error")
            return redirect(url_for("index") + "#closures")

        conn.execute("""
            INSERT INTO closures (
                project_id, completion_date, final_status, closure_notes
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                completion_date=excluded.completion_date,
                final_status=excluded.final_status,
                closure_notes=excluded.closure_notes
        """, (project_id, completion_date, final_status, notes))

        conn.execute("UPDATE projects SET status = ? WHERE id = ?", (final_status, project_id))
        conn.commit()
        flash("Project closure saved successfully.", "success")
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to save closure record.", "error")
    finally:
        conn.close()

    return redirect(url_for("index", project_id=project_id) + "#closures")


# =========================================================
# MODULE 2: REQUIREMENTS MANAGEMENT
# =========================================================

@app.route("/save_requirement", methods=["POST"])
def save_requirement():
    requirement_id = request.form.get("requirement_id", type=int)
    project_id = request.form.get("project_id", type=int)
    title = request.form.get("requirement_title", "").strip()
    description = request.form.get("requirement_description", "").strip()
    priority = request.form.get("priority", "Medium").strip()

    if not project_id or not title or not description:
        flash("Project, requirement title and description are required.", "error")
        return redirect(url_for("index") + "#requirements")

    if priority not in ["High", "Medium", "Low"]:
        priority = "Medium"

    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone():
            flash("Select a valid project.", "error")
            return redirect(url_for("index") + "#requirements")

        if requirement_id:
            existing = conn.execute("SELECT project_id FROM requirements WHERE id = ?", (requirement_id,)).fetchone()
            if not existing:
                flash("Requirement not found.", "error")
                return redirect(url_for("index") + "#requirements")

            old_project_id = existing["project_id"]
            conn.execute("""
                UPDATE requirements
                SET project_id=?, title=?, description=?, priority=?, approval_status='Pending'
                WHERE id=?
            """, (project_id, title, description, priority, requirement_id))

            refresh_approved_scope(conn, old_project_id)
            refresh_approved_scope(conn, project_id)

            flash("Requirement updated. It is Pending until reviewed and is excluded from approved scope.", "success")
        else:
            conn.execute("""
                INSERT INTO requirements (project_id, title, description, priority, approval_status)
                VALUES (?, ?, ?, ?, 'Pending')
            """, (project_id, title, description, priority))

            refresh_approved_scope(conn, project_id)
            flash("Requirement added as Pending. It is excluded from approved scope.", "success")

        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        app.logger.exception("Requirement save failed")
        flash("Unable to save requirement.", "error")
    finally:
        conn.close()

    return redirect(url_for("index") + "#requirements")


@app.route("/requirement_status/<int:requirement_id>", methods=["POST"])
def requirement_status(requirement_id):
    new_status = request.form.get("approval_status", "").strip()

    if new_status not in APPROVAL_STATUSES:
        flash("Select a valid requirement status.", "error")
        return redirect(url_for("index") + "#requirements")

    conn = get_db()
    try:
        requirement = conn.execute("SELECT project_id FROM requirements WHERE id = ?", (requirement_id,)).fetchone()
        if not requirement:
            flash("Requirement not found.", "error")
            return redirect(url_for("index") + "#requirements")

        project_id = requirement["project_id"]
        conn.execute("UPDATE requirements SET approval_status = ? WHERE id = ?", (new_status, requirement_id))
        refresh_approved_scope(conn, project_id)
        conn.commit()

        flash(f"Requirement status changed to {new_status}. Approved project scope has been refreshed.", "success")
    except sqlite3.Error:
        conn.rollback()
        app.logger.exception("Requirement status update failed")
        flash("Unable to update requirement status.", "error")
    finally:
        conn.close()

    return redirect(url_for("index") + "#requirements")


@app.route("/delete_requirement/<int:requirement_id>", methods=["POST"])
def delete_requirement(requirement_id):
    conn = get_db()
    try:
        requirement = conn.execute("SELECT project_id FROM requirements WHERE id = ?", (requirement_id,)).fetchone()
        if not requirement:
            flash("Requirement not found.", "error")
            return redirect(url_for("index") + "#requirements")

        project_id = requirement["project_id"]
        conn.execute("DELETE FROM requirements WHERE id = ?", (requirement_id,))
        refresh_approved_scope(conn, project_id)
        conn.commit()
        flash("Requirement deleted and approved scope refreshed.", "success")
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to delete requirement.", "error")
    finally:
        conn.close()

    return redirect(url_for("index") + "#requirements")


# =========================================================
# MODULE 2: WORK BREAKDOWN STRUCTURE
# =========================================================

@app.route("/save_wbs", methods=["POST"])
def save_wbs():
    wbs_id = request.form.get("wbs_id", type=int)
    project_id = request.form.get("wbs_project_id", type=int)
    parent_value = request.form.get("parent_id", "").strip()
    title = request.form.get("wbs_title", "").strip()
    description = request.form.get("wbs_description", "").strip()
    item_type = request.form.get("item_type", "").strip()

    allowed_types = ["Deliverable", "Sub-deliverable", "Work Package"]

    if not project_id or not title:
        flash("Select a project and enter a WBS item name.", "error")
        return redirect(url_for("index") + "#wbs")

    if item_type not in allowed_types:
        flash("Select a valid WBS item type.", "error")
        return redirect(url_for("index") + "#wbs")

    try:
        parent_id = int(parent_value) if parent_value else None
    except ValueError:
        flash("Invalid parent WBS item.", "error")
        return redirect(url_for("index") + "#wbs")

    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone():
            flash("Project not found.", "error")
            return redirect(url_for("index") + "#wbs")

        if wbs_id:
            existing = conn.execute("SELECT * FROM wbs_items WHERE id = ?", (wbs_id,)).fetchone()
            if not existing:
                flash("WBS item not found.", "error")
                return redirect(url_for("index") + "#wbs")

            if existing["project_id"] != project_id:
                flash("An existing WBS item cannot be moved to another project.", "error")
                return redirect(url_for("index") + "#wbs")

            descendants = get_wbs_descendant_ids(conn, wbs_id)
            if parent_id == wbs_id or (parent_id is not None and parent_id in descendants):
                flash("A WBS item cannot be its own parent or child of its descendant.", "error")
                return redirect(url_for("index") + "#wbs")

        parent = None
        if parent_id is not None:
            parent = conn.execute("SELECT id, project_id, item_type FROM wbs_items WHERE id = ?", (parent_id,)).fetchone()
            if not parent or parent["project_id"] != project_id:
                flash("Select a valid parent from the same project.", "error")
                return redirect(url_for("index") + "#wbs")

        parent_type = parent["item_type"] if parent else None
        if not validate_wbs_hierarchy(item_type, parent_type):
            flash("Invalid WBS hierarchy for the selected item type.", "error")
            return redirect(url_for("index") + "#wbs")

        code = get_wbs_code(conn, project_id, parent_id, exclude_id=wbs_id)

        if wbs_id:
            conn.execute("""
                UPDATE wbs_items
                SET parent_id=?, wbs_code=?, title=?, description=?, item_type=?
                WHERE id=?
            """, (parent_id, code, title, description, item_type, wbs_id))
            flash("WBS item updated successfully.", "success")
        else:
            conn.execute("""
                INSERT INTO wbs_items (project_id, parent_id, wbs_code, title, description, item_type)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (project_id, parent_id, code, title, description, item_type))
            flash("WBS item added successfully.", "success")

        conn.commit()
    except (sqlite3.Error, ValueError):
        conn.rollback()
        app.logger.exception("WBS save failed")
        flash("Unable to save WBS item.", "error")
    finally:
        conn.close()

    return redirect(url_for("index") + "#wbs")


@app.route("/delete_wbs/<int:wbs_id>", methods=["POST"])
def delete_wbs(wbs_id):
    conn = get_db()
    project_id = None
    try:
        row = conn.execute("SELECT project_id FROM wbs_items WHERE id = ?", (wbs_id,)).fetchone()
        if row:
            project_id = row["project_id"]
        result = conn.execute("DELETE FROM wbs_items WHERE id = ?", (wbs_id,))
        conn.commit()
        flash(
            "WBS item and child items deleted successfully." if result.rowcount else "WBS item not found.",
            "success" if result.rowcount else "error"
        )
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to delete WBS item.", "error")
    finally:
        conn.close()

    if project_id:
        return redirect(url_for("index", project_id=project_id) + "#wbs")
    return redirect(url_for("index") + "#wbs")


# =========================================================
# MODULE 2: CHANGE REQUEST MANAGEMENT
# =========================================================

@app.route("/save_change_request", methods=["POST"])
def save_change_request():
    project_id = request.form.get("project_id", type=int)
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    justification = request.form.get("justification", "").strip()
    requested_by = request.form.get("requested_by", "").strip()

    try:
        cost_impact = float(request.form.get("cost_impact", "0") or 0)
        schedule_impact_days = int(request.form.get("schedule_impact_days", "0") or 0)
    except (TypeError, ValueError):
        flash("Enter valid cost and schedule impact values.", "error")
        return redirect(url_for("index", project_id=project_id) + "#change-requests")

    if cost_impact < 0 or schedule_impact_days < 0:
        flash("Cost and schedule impact cannot be negative.", "error")
        return redirect(url_for("index", project_id=project_id) + "#change-requests")

    if not project_id or not title or not description or not justification:
        flash("Project, title, description and justification are required.", "error")
        return redirect(url_for("index", project_id=project_id) + "#change-requests")

    conn = get_db()
    try:
        exists = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not exists:
            flash("Select a valid project.", "error")
            return redirect(url_for("index") + "#change-requests")

        conn.execute("""
            INSERT INTO change_requests (
                project_id, title, description, justification,
                cost_impact, schedule_impact_days, approval_status, requested_by
            )
            VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?)
        """, (project_id, title, description, justification, cost_impact, schedule_impact_days, requested_by))

        conn.commit()
        flash("Change request submitted. Status: Pending.", "success")
    except sqlite3.Error:
        conn.rollback()
        app.logger.exception("Change request save failed")
        flash("Unable to save change request.", "error")
    finally:
        conn.close()

    return redirect(url_for("index", project_id=project_id) + "#change-requests")


@app.route("/change_request_status/<int:request_id>", methods=["POST"])
def change_request_status(request_id):
    new_status = request.form.get("approval_status", "").strip()
    comments = request.form.get("reviewer_comments", "").strip()

    if new_status not in APPROVAL_STATUSES:
        flash("Select a valid change request status.", "error")
        return redirect(url_for("index") + "#change-requests")

    conn = get_db()
    project_id = None
    try:
        exists = conn.execute("SELECT id, project_id FROM change_requests WHERE id = ?", (request_id,)).fetchone()
        if not exists:
            flash("Change request not found.", "error")
            return redirect(url_for("index") + "#change-requests")

        project_id = exists["project_id"]
        reviewed_at = None
        if new_status != "Pending":
            reviewed_at = conn.execute("SELECT CURRENT_TIMESTAMP").fetchone()[0]

        conn.execute("""
            UPDATE change_requests
            SET approval_status=?, reviewer_comments=?, reviewed_at=?
            WHERE id=?
        """, (new_status, comments, reviewed_at, request_id))

        conn.commit()
        flash(f"Change request status updated to {new_status}. Project budget and schedule impacts updated.", "success")
    except sqlite3.Error:
        conn.rollback()
        app.logger.exception("Change request status update failed")
        flash("Unable to update change request.", "error")
    finally:
        conn.close()

    if project_id:
        return redirect(url_for("index", project_id=project_id) + "#change-requests")
    return redirect(url_for("index") + "#change-requests")


@app.route("/delete_change_request/<int:request_id>", methods=["POST"])
def delete_change_request(request_id):
    conn = get_db()
    project_id = None
    try:
        row = conn.execute("SELECT project_id FROM change_requests WHERE id = ?", (request_id,)).fetchone()
        if row:
            project_id = row["project_id"]
        result = conn.execute("DELETE FROM change_requests WHERE id = ?", (request_id,))
        conn.commit()
        flash(
            "Change request deleted successfully." if result.rowcount else "Change request not found.",
            "success" if result.rowcount else "error"
        )
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to delete change request.", "error")
    finally:
        conn.close()

    if project_id:
        return redirect(url_for("index", project_id=project_id) + "#change-requests")
    return redirect(url_for("index") + "#change-requests")


# =========================================================
# MODULE 8: SCHEDULE & RESOURCE MANAGEMENT ENDPOINTS
# =========================================================

@app.route("/save_activity", methods=["POST"])
def save_activity():
    activity_id = request.form.get("activity_id", type=int)
    project_id = request.form.get("project_id", type=int)
    wbs_id = request.form.get("wbs_id", type=int)
    title = request.form.get("title", "").strip()
    assigned_to = request.form.get("assigned_to", "").strip()
    start_date = request.form.get("start_date", "").strip()
    end_date = request.form.get("end_date", "").strip()
    status = request.form.get("status", "Not Started").strip()

    try:
        duration_days = int(request.form.get("duration_days", 1) or 1)
        progress_percent = int(request.form.get("progress_percent", 0) or 0)
        delay_days = int(request.form.get("delay_days", 0) or 0)
        planned_cost = float(request.form.get("planned_cost", 0) or 0)
        actual_cost = float(request.form.get("actual_cost", 0) or 0)
        predecessor_id = request.form.get("predecessor_id", type=int)
    except (TypeError, ValueError):
        flash("Enter valid numerical values for duration, progress, delay, and costs.", "error")
        return redirect(url_for("index") + "#schedule")

    if not project_id or not title or not start_date or not end_date:
        flash("Project, activity name, start date and end date are required.", "error")
        return redirect(url_for("index") + "#schedule")

    if duration_days < 1 or planned_cost < 0 or actual_cost < 0 or delay_days < 0:
        flash("Duration must be at least 1 day. Costs and delay cannot be negative.", "error")
        return redirect(url_for("index") + "#schedule")

    progress_percent = max(0, min(100, progress_percent))

    # Automatic status adjustment based on progress & delay
    if progress_percent == 100:
        status = "Completed"
    elif delay_days > 0 and status != "Completed":
        status = "Delayed"
    elif progress_percent > 0 and status == "Not Started":
        status = "In Progress"

    conn = get_db()
    try:
        # Validate predecessor does not cycle
        if activity_id and predecessor_id == activity_id:
            flash("An activity cannot depend on itself.", "error")
            return redirect(url_for("index") + "#schedule")

        if activity_id:
            conn.execute("""
                UPDATE activities
                SET project_id=?, wbs_id=?, title=?, assigned_to=?,
                    duration_days=?, start_date=?, end_date=?, predecessor_id=?,
                    status=?, progress_percent=?, delay_days=?, planned_cost=?, actual_cost=?
                WHERE id=?
            """, (
                project_id, wbs_id, title, assigned_to,
                duration_days, start_date, end_date, predecessor_id,
                status, progress_percent, delay_days, planned_cost, actual_cost, activity_id
            ))
            flash("Activity updated successfully.", "success")
        else:
            conn.execute("""
                INSERT INTO activities (
                    project_id, wbs_id, title, assigned_to,
                    duration_days, start_date, end_date, predecessor_id,
                    status, progress_percent, delay_days, planned_cost, actual_cost
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id, wbs_id, title, assigned_to,
                duration_days, start_date, end_date, predecessor_id,
                status, progress_percent, delay_days, planned_cost, actual_cost
            ))
            flash("Activity scheduled successfully.", "success")

        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        app.logger.exception("Activity save failed")
        flash("Database error while saving activity.", "error")
    finally:
        conn.close()

    return redirect(url_for("index", project_id=project_id) + "#schedule")


@app.route("/delete_activity/<int:activity_id>", methods=["POST"])
def delete_activity(activity_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT project_id FROM activities WHERE id = ?", (activity_id,)).fetchone()
        project_id = row["project_id"] if row else None
        result = conn.execute("DELETE FROM activities WHERE id = ?", (activity_id,))
        conn.commit()
        flash("Activity deleted successfully." if result.rowcount else "Activity not found.", "success" if result.rowcount else "error")
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to delete activity.", "error")
    finally:
        conn.close()

    return redirect(url_for("index", project_id=project_id) + "#schedule")


@app.route("/update_activity_progress/<int:activity_id>", methods=["POST"])
def update_activity_progress(activity_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT project_id FROM activities WHERE id = ?", (activity_id,)).fetchone()
        if not row:
            flash("Activity not found.", "error")
            return redirect(url_for("index") + "#schedule")

        project_id = row["project_id"]
        progress_percent = int(request.form.get("progress_percent", 0) or 0)
        delay_days = int(request.form.get("delay_days", 0) or 0)
        actual_cost = float(request.form.get("actual_cost", 0) or 0)
        status = request.form.get("status", "In Progress").strip()

        progress_percent = max(0, min(100, progress_percent))
        if progress_percent == 100:
            status = "Completed"
        elif delay_days > 0 and status != "Completed":
            status = "Delayed"

        conn.execute("""
            UPDATE activities
            SET progress_percent = ?, delay_days = ?, actual_cost = ?, status = ?
            WHERE id = ?
        """, (progress_percent, delay_days, actual_cost, status, activity_id))
        conn.commit()
        flash("Activity progress and delay updated successfully.", "success")
    except (sqlite3.Error, ValueError):
        conn.rollback()
        flash("Unable to update progress.", "error")
    finally:
        conn.close()

    return redirect(url_for("index", project_id=project_id) + "#schedule")


# =========================================================
# MODULE 10: QUALITY & DEFECT MANAGEMENT ENDPOINTS
# =========================================================

@app.route("/save_defect", methods=["POST"])
def save_defect():
    defect_id = request.form.get("defect_id", type=int)
    project_id = request.form.get("project_id", type=int)
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    module_affected = request.form.get("module_affected", "").strip()
    severity = request.form.get("severity", "Minor").strip()
    assigned_to = request.form.get("assigned_to", "").strip()
    status = request.form.get("status", "Open").strip()
    resolution_notes = request.form.get("resolution_notes", "").strip()

    if not project_id or not title or not module_affected:
        flash("Project, defect title, and affected module are required.", "error")
        return redirect(url_for("index") + "#quality-risk")

    if severity not in ["Critical", "Major", "Minor", "Low"]:
        severity = "Minor"

    if status not in ["Open", "In Progress", "Resolved", "Closed"]:
        status = "Open"

    conn = get_db()
    try:
        if defect_id:
            conn.execute("""
                UPDATE defects
                SET project_id=?, title=?, description=?, module_affected=?,
                    severity=?, assigned_to=?, status=?, resolution_notes=?
                WHERE id=?
            """, (project_id, title, description, module_affected, severity, assigned_to, status, resolution_notes, defect_id))
            flash("Defect record updated successfully.", "success")
        else:
            conn.execute("""
                INSERT INTO defects (
                    project_id, title, description, module_affected,
                    severity, assigned_to, status, resolution_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (project_id, title, description, module_affected, severity, assigned_to, status, resolution_notes))
            flash("Defect logged successfully.", "success")

        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to save defect record.", "error")
    finally:
        conn.close()

    return redirect(url_for("index", project_id=project_id) + "#quality-risk")


@app.route("/defect_status/<int:defect_id>", methods=["POST"])
def defect_status(defect_id):
    new_status = request.form.get("status", "Open").strip()
    notes = request.form.get("resolution_notes", "").strip()

    conn = get_db()
    try:
        row = conn.execute("SELECT project_id FROM defects WHERE id = ?", (defect_id,)).fetchone()
        project_id = row["project_id"] if row else None

        conn.execute("""
            UPDATE defects
            SET status = ?, resolution_notes = ?
            WHERE id = ?
        """, (new_status, notes, defect_id))
        conn.commit()
        flash(f"Defect status updated to {new_status}.", "success")
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to update defect status.", "error")
    finally:
        conn.close()

    return redirect(url_for("index", project_id=project_id) + "#quality-risk")


@app.route("/delete_defect/<int:defect_id>", methods=["POST"])
def delete_defect(defect_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT project_id FROM defects WHERE id = ?", (defect_id,)).fetchone()
        project_id = row["project_id"] if row else None
        conn.execute("DELETE FROM defects WHERE id = ?", (defect_id,))
        conn.commit()
        flash("Defect record deleted.", "success")
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to delete defect.", "error")
    finally:
        conn.close()

    return redirect(url_for("index", project_id=project_id) + "#quality-risk")


@app.route("/save_quality_check", methods=["POST"])
def save_quality_check():
    check_id = request.form.get("check_id", type=int)
    project_id = request.form.get("project_id", type=int)
    deliverable_name = request.form.get("deliverable_name", "").strip()
    check_item = request.form.get("check_item", "").strip()
    inspection_status = request.form.get("inspection_status", "Pending").strip()
    inspected_by = request.form.get("inspected_by", "").strip()
    inspection_date = request.form.get("inspection_date", "").strip()
    remarks = request.form.get("remarks", "").strip()

    if not project_id or not deliverable_name or not check_item:
        flash("Project, deliverable name and quality inspection criteria are required.", "error")
        return redirect(url_for("index") + "#quality-risk")

    conn = get_db()
    try:
        if check_id:
            conn.execute("""
                UPDATE quality_checks
                SET project_id=?, deliverable_name=?, check_item=?,
                    inspection_status=?, inspected_by=?, inspection_date=?, remarks=?
                WHERE id=?
            """, (project_id, deliverable_name, check_item, inspection_status, inspected_by, inspection_date, remarks, check_id))
            flash("Quality checklist item updated.", "success")
        else:
            conn.execute("""
                INSERT INTO quality_checks (
                    project_id, deliverable_name, check_item,
                    inspection_status, inspected_by, inspection_date, remarks
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (project_id, deliverable_name, check_item, inspection_status, inspected_by, inspection_date, remarks))
            flash("Quality checklist item added.", "success")

        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to save quality check.", "error")
    finally:
        conn.close()

    return redirect(url_for("index", project_id=project_id) + "#quality-risk")


@app.route("/quality_check_status/<int:check_id>", methods=["POST"])
def quality_check_status(check_id):
    new_status = request.form.get("inspection_status", "Passed").strip()
    inspected_by = request.form.get("inspected_by", "").strip()
    remarks = request.form.get("remarks", "").strip()

    conn = get_db()
    try:
        row = conn.execute("SELECT project_id FROM quality_checks WHERE id = ?", (check_id,)).fetchone()
        project_id = row["project_id"] if row else None
        today_str = date.today().isoformat()

        conn.execute("""
            UPDATE quality_checks
            SET inspection_status=?, inspected_by=?, inspection_date=?, remarks=?
            WHERE id=?
        """, (new_status, inspected_by, today_str, remarks, check_id))
        conn.commit()
        flash(f"Inspection recorded: {new_status}.", "success")
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to update quality check.", "error")
    finally:
        conn.close()

    return redirect(url_for("index", project_id=project_id) + "#quality-risk")


@app.route("/delete_quality_check/<int:check_id>", methods=["POST"])
def delete_quality_check(check_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT project_id FROM quality_checks WHERE id = ?", (check_id,)).fetchone()
        project_id = row["project_id"] if row else None
        conn.execute("DELETE FROM quality_checks WHERE id = ?", (check_id,))
        conn.commit()
        flash("Quality checklist item deleted.", "success")
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to delete check item.", "error")
    finally:
        conn.close()

    return redirect(url_for("index", project_id=project_id) + "#quality-risk")


# =========================================================
# MODULE 10: RISK CONTROL & PDPC ENDPOINTS
# =========================================================

@app.route("/save_risk", methods=["POST"])
def save_risk():
    risk_id = request.form.get("risk_id", type=int)
    project_id = request.form.get("project_id", type=int)
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "Technical").strip()
    status = request.form.get("status", "Open").strip()
    mitigation_strategy = request.form.get("mitigation_strategy", "").strip()

    try:
        likelihood = int(request.form.get("likelihood", 3) or 3)
        impact = int(request.form.get("impact", 3) or 3)
    except (TypeError, ValueError):
        flash("Likelihood and impact must be integer ratings between 1 and 5.", "error")
        return redirect(url_for("index") + "#quality-risk")

    likelihood = max(1, min(5, likelihood))
    impact = max(1, min(5, impact))
    risk_score = likelihood * impact

    if risk_score >= 15:
        priority_level = "Critical"
    elif risk_score >= 10:
        priority_level = "High"
    elif risk_score >= 5:
        priority_level = "Medium"
    else:
        priority_level = "Low"

    if not project_id or not title:
        flash("Project and risk title are required.", "error")
        return redirect(url_for("index") + "#quality-risk")

    conn = get_db()
    try:
        if risk_id:
            conn.execute("""
                UPDATE risks
                SET project_id=?, title=?, category=?, likelihood=?, impact=?,
                    risk_score=?, priority_level=?, status=?, mitigation_strategy=?
                WHERE id=?
            """, (project_id, title, category, likelihood, impact, risk_score, priority_level, status, mitigation_strategy, risk_id))
            flash(f"Risk updated. Prioritization Rank: {priority_level} (Score: {risk_score}).", "success")
        else:
            conn.execute("""
                INSERT INTO risks (
                    project_id, title, category, likelihood, impact,
                    risk_score, priority_level, status, mitigation_strategy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (project_id, title, category, likelihood, impact, risk_score, priority_level, status, mitigation_strategy))
            flash(f"Risk registered. Prioritization Rank: {priority_level} (Score: {risk_score}).", "success")

        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to save risk record.", "error")
    finally:
        conn.close()

    return redirect(url_for("index", project_id=project_id) + "#quality-risk")


@app.route("/delete_risk/<int:risk_id>", methods=["POST"])
def delete_risk(risk_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT project_id FROM risks WHERE id = ?", (risk_id,)).fetchone()
        project_id = row["project_id"] if row else None
        conn.execute("DELETE FROM risks WHERE id = ?", (risk_id,))
        conn.commit()
        flash("Risk record removed from matrix.", "success")
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to delete risk.", "error")
    finally:
        conn.close()

    return redirect(url_for("index", project_id=project_id) + "#quality-risk")


@app.route("/save_pdpc", methods=["POST"])
def save_pdpc():
    pdpc_id = request.form.get("pdpc_id", type=int)
    project_id = request.form.get("project_id", type=int)
    process_step = request.form.get("process_step", "").strip()
    potential_problem = request.form.get("potential_problem", "").strip()
    countermeasure = request.form.get("countermeasure", "").strip()
    action_type = request.form.get("action_type", "Preventive").strip()
    status = request.form.get("status", "Selected").strip()

    if not project_id or not process_step or not potential_problem or not countermeasure:
        flash("All PDPC fields are required.", "error")
        return redirect(url_for("index") + "#quality-risk")

    conn = get_db()
    try:
        if pdpc_id:
            conn.execute("""
                UPDATE pdpc_items
                SET project_id=?, process_step=?, potential_problem=?,
                    countermeasure=?, action_type=?, status=?
                WHERE id=?
            """, (project_id, process_step, potential_problem, countermeasure, action_type, status, pdpc_id))
            flash("PDPC contingency updated.", "success")
        else:
            conn.execute("""
                INSERT INTO pdpc_items (
                    project_id, process_step, potential_problem,
                    countermeasure, action_type, status
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (project_id, process_step, potential_problem, countermeasure, action_type, status))
            flash("PDPC risk response contingency added.", "success")

        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to save PDPC item.", "error")
    finally:
        conn.close()

    return redirect(url_for("index", project_id=project_id) + "#quality-risk")


@app.route("/delete_pdpc/<int:pdpc_id>", methods=["POST"])
def delete_pdpc(pdpc_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT project_id FROM pdpc_items WHERE id = ?", (pdpc_id,)).fetchone()
        project_id = row["project_id"] if row else None
        conn.execute("DELETE FROM pdpc_items WHERE id = ?", (pdpc_id,))
        conn.commit()
        flash("PDPC item deleted.", "success")
    except sqlite3.Error:
        conn.rollback()
        flash("Unable to delete PDPC item.", "error")
    finally:
        conn.close()

    return redirect(url_for("index", project_id=project_id) + "#quality-risk")


# =========================================================
# SAMPLE DATA SEED ROUTE
# =========================================================

@app.route("/seed_case_study", methods=["POST"])
def seed_case_study():
    project_id = request.form.get("project_id", type=int)
    if not project_id:
        flash("Select a project to seed sample data.", "error")
        return redirect(url_for("index"))

    conn = get_db()
    try:
        seed_sample_case_study(conn, project_id)
        conn.commit()
        flash("Sample project data successfully loaded for Schedule, Costs, Defects, Quality, and Risks!", "success")
    except sqlite3.Error:
        conn.rollback()
        app.logger.exception("Sample data seeding failed")
        flash("Error loading sample data.", "error")
    finally:
        conn.close()

    return redirect(url_for("index", project_id=project_id) + "#dashboard")


# =========================================================
# APPLICATION START
# =========================================================

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "True").lower() in ("true", "1", "t")
    app.run(host="0.0.0.0", port=port, debug=debug)
