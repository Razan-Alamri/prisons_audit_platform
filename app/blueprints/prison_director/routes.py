from flask import Blueprint, redirect, url_for
from flask_login import login_required

prison_director_bp = Blueprint('prison_director', __name__, url_prefix='/prison-director')

@prison_director_bp.route('/')
@login_required
def root():
    return redirect(url_for('dashboard.home'))
