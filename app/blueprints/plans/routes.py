from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ...permissions import roles_required
from ...extensions import db
from ...models import AnnualPlan, PlanItem, Region, Prison, Template
from ...utils import log_action

plans_bp = Blueprint('plans', __name__, url_prefix='/plans')

@plans_bp.route('/')
@login_required
@roles_required('central_admin','central_operator','central_director')
def index():
    plans = AnnualPlan.query.order_by(AnnualPlan.year.desc()).all()
    return render_template('plans/index.html', plans=plans)

@plans_bp.route('/<int:plan_id>', methods=['GET', 'POST'])
@login_required
@roles_required('central_admin','central_operator','central_director')
def detail(plan_id):
    plan = AnnualPlan.query.get_or_404(plan_id)
    regions = Region.query.order_by(Region.name).all()
    templates = Template.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        item = PlanItem(
            plan=plan,
            title=request.form.get('title'),
            template_id=int(request.form.get('template_id')),
            planned_date=date.fromisoformat(request.form.get('planned_date')),
            notes=request.form.get('notes'),
            allow_region_to_select_prisons=bool(request.form.get('allow_region_to_select_prisons')),
        )
        item.regions = [db.session.get(Region, int(rid)) for rid in request.form.getlist('region_ids')]
        db.session.add(item)
        db.session.commit()
        log_action(current_user.id, 'add_plan_item', 'annual_plan', plan.id, item.title)
        flash('تمت إضافة بند للخطة.', 'success')
        return redirect(url_for('plans.detail', plan_id=plan.id))
    return render_template('plans/detail.html', plan=plan, regions=regions, templates=templates)
