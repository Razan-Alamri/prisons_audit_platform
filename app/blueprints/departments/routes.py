from flask import Blueprint, render_template
from flask_login import login_required, current_user
from ...permissions import roles_required
from ...models import Observation

departments_bp = Blueprint('departments', __name__, url_prefix='/departments')

@departments_bp.route('/observations')
@login_required
@roles_required('department_user','department_manager')
def observations():
    observations = Observation.query.filter_by(department_id=current_user.department_id).order_by(Observation.created_at.desc()).all()
    return render_template('departments/observations.html', observations=observations)
