from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from ...services.dashboard_service import central_dashboard, region_dashboard, executor_dashboard, prison_director_dashboard, department_dashboard, dg_dashboard


dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def root():
    return redirect(url_for('dashboard.home'))

@dashboard_bp.route('/dashboard')
@login_required
def home():
    role = current_user.role
    if role in ['central_admin', 'central_operator', 'central_director']:
        stats, top_regions, top_departments, charts = central_dashboard(current_user)
        return render_template('dashboard/central.html', stats=stats, top_regions=top_regions, top_departments=top_departments, charts=charts, title='لوحة الإدارة الرئيسية')
    if role == 'region_manager':
        stats, mission_regions, charts = region_dashboard(current_user)
        return render_template('dashboard/region_manager.html', stats=stats, mission_regions=mission_regions, charts=charts, title='لوحة المنطقة')
    if role == 'executor':
        stats, mission_regions, charts = executor_dashboard(current_user)
        return render_template('dashboard/executor.html', stats=stats, mission_regions=mission_regions, charts=charts, title='لوحة المنفذ')
    if role == 'prison_director':
        stats, mission_regions, charts = prison_director_dashboard(current_user)
        return render_template('dashboard/prison_director.html', stats=stats, mission_regions=mission_regions, charts=charts, title='لوحة مدير سجون المنطقة')
    if role in ['department_user', 'department_manager']:
        stats, observations, charts = department_dashboard(current_user)
        return render_template('dashboard/department.html', stats=stats, observations=observations, charts=charts, title='لوحة الإدارة المختصة')
    if role == 'director_general':
        stats, reports, charts = dg_dashboard()
        return render_template('dashboard/dg.html', stats=stats, reports=reports, charts=charts, title='اللوحة القيادية')
    return render_template('dashboard/central.html', stats={}, top_regions=[], top_departments=[], charts={}, title='الرئيسية')
