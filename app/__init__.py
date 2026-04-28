from flask import Flask
from .config import Config
from .extensions import db, login_manager


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    from .blueprints.auth.routes import auth_bp
    from .blueprints.dashboard.routes import dashboard_bp
    from .blueprints.missions.routes import missions_bp
    from .blueprints.templates_admin.routes import templates_admin_bp
    from .blueprints.reports.routes import reports_bp
    from .blueprints.plans.routes import plans_bp
    from .blueprints.departments.routes import departments_bp
    from .blueprints.prison_director.routes import prison_director_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(missions_bp)
    app.register_blueprint(templates_admin_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(plans_bp)
    app.register_blueprint(departments_bp)
    app.register_blueprint(prison_director_bp)

    from .models import User, Region, Prison, Department, Template, Mission, MissionRegion, Observation, Attachment, AnnualPlan, PlanItem

    @app.context_processor
    def inject_globals():
        return dict(app_name='منصة المراجعة الداخلية والرقابة بالسجون')

    from .models import (
        ROLE_LABELS,
        OBS_STATUS,
        SLA_OPTIONS,
        MISSION_CLASSIFICATION_LABELS,
        PRIORITY_LEVEL_LABELS,
        MISSION_STATUS_LABELS,
        ASSIGNMENT_MODE_LABELS,
        MISSION_REGION_STATUS_LABELS,
        MISSION_PRISON_REPORT_STATUS_LABELS
    )

    @app.context_processor
    def inject_reference_labels():
        return {
            'ROLE_LABELS': ROLE_LABELS,
            'OBS_STATUS': OBS_STATUS,
            'SLA_OPTIONS': SLA_OPTIONS,
            'MISSION_CLASSIFICATION_LABELS': MISSION_CLASSIFICATION_LABELS,
            'PRIORITY_LEVEL_LABELS': PRIORITY_LEVEL_LABELS,
            'MISSION_STATUS_LABELS': MISSION_STATUS_LABELS,
            'ASSIGNMENT_MODE_LABELS': ASSIGNMENT_MODE_LABELS,
            'MISSION_REGION_STATUS_LABELS': MISSION_REGION_STATUS_LABELS,
            'MISSION_PRISON_REPORT_STATUS_LABELS': MISSION_PRISON_REPORT_STATUS_LABELS,
        }

    with app.app_context():
        db.create_all()
        from .seed import seed_if_empty
        seed_if_empty()

    return app