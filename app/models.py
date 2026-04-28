from __future__ import annotations
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db, login_manager


mission_prison_assignees = db.Table(
    'mission_prison_assignees',
    db.Column('mission_prison_report_id', db.Integer, db.ForeignKey('mission_prison_report.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
)

plan_item_regions = db.Table(
    'plan_item_regions',
    db.Column('plan_item_id', db.Integer, db.ForeignKey('plan_item.id'), primary_key=True),
    db.Column('region_id', db.Integer, db.ForeignKey('region.id'), primary_key=True),
)

plan_item_prisons = db.Table(
    'plan_item_prisons',
    db.Column('plan_item_id', db.Integer, db.ForeignKey('plan_item.id'), primary_key=True),
    db.Column('prison_id', db.Integer, db.ForeignKey('prison.id'), primary_key=True),
)


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Region(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    prisons = db.relationship('Prison', back_populates='region', cascade='all, delete-orphan')
    users = db.relationship('User', back_populates='region')


class Prison(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    region_id = db.Column(db.Integer, db.ForeignKey('region.id'), nullable=False)

    region = db.relationship('Region', back_populates='prisons')


class Department(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)


class User(UserMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    job_title = db.Column(db.String(150), nullable=True)
    region_id = db.Column(db.Integer, db.ForeignKey('region.id'))
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    org_unit_type = db.Column(db.String(20), default='regional')
    is_active_user = db.Column(db.Boolean, default=True, nullable=False)

    region = db.relationship('Region', back_populates='users')
    department = db.relationship('Department')

    def set_password(self, raw_password: str):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_active(self):
        return self.is_active_user

    def has_role(self, *roles):
        return self.role in roles


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Template(TimestampMixin, db.Model):
    __table_args__ = (
        db.UniqueConstraint('name', name='uq_template_name'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    sections = db.relationship(
        'TemplateSection',
        back_populates='template',
        cascade='all, delete-orphan',
        order_by='TemplateSection.sort_order'
    )

    @property
    def total_weight(self):
        return round(sum(s.weight_percentage for s in self.sections), 2)


class TemplateSection(TimestampMixin, db.Model):
    __table_args__ = (
        db.UniqueConstraint('template_id', 'title', name='uq_template_section_title'),
    )

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('template.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    weight_percentage = db.Column(db.Float, nullable=False, default=0)
    sort_order = db.Column(db.Integer, default=1, nullable=False)

    template = db.relationship('Template', back_populates='sections')
    criteria = db.relationship(
        'TemplateCriterion',
        back_populates='section',
        cascade='all, delete-orphan',
        order_by='TemplateCriterion.sort_order'
    )


class TemplateCriterion(TimestampMixin, db.Model):
    __table_args__ = (
        db.UniqueConstraint('section_id', 'text', name='uq_template_criterion_text'),
    )

    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('template_section.id'), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    sort_order = db.Column(db.Integer, default=1, nullable=False)

    section = db.relationship('TemplateSection', back_populates='criteria')


class AnnualPlan(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text)

    items = db.relationship(
        'PlanItem',
        back_populates='plan',
        cascade='all, delete-orphan',
        order_by='PlanItem.planned_date'
    )


class PlanItem(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    annual_plan_id = db.Column(db.Integer, db.ForeignKey('annual_plan.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('template.id'), nullable=False)
    planned_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text)
    auto_create = db.Column(db.Boolean, default=False, nullable=False)
    allow_region_to_select_prisons = db.Column(db.Boolean, default=True, nullable=False)

    plan = db.relationship('AnnualPlan', back_populates='items')
    template = db.relationship('Template')
    regions = db.relationship('Region', secondary=plan_item_regions, lazy='subquery')
    prisons = db.relationship('Prison', secondary=plan_item_prisons, lazy='subquery')


class Mission(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference_no = db.Column(db.String(30), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('template.id'), nullable=False)

    mission_classification = db.Column(db.String(30), nullable=False, default='ad_hoc')
    priority_level = db.Column(db.String(20), nullable=False, default='normal')

    assignment_mode = db.Column(db.String(40), nullable=False, default='region_manager_selects')
    planned_date = db.Column(db.Date)
    due_date = db.Column(db.Date)

    status = db.Column(db.String(30), default='created', nullable=False)

    task_instructions = db.Column(db.Text)
    final_summary = db.Column(db.Text)
    final_recommendations = db.Column(db.Text)
    internal_audit_opinion = db.Column(db.Text)
    dg_decision = db.Column(db.Text)
    sent_to_dg_at = db.Column(db.DateTime)

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_by_user = db.relationship('User')
    template = db.relationship('Template')

    regions = db.relationship(
        'MissionRegion',
        back_populates='mission',
        cascade='all, delete-orphan',
        order_by='MissionRegion.id'
    )

    attachments = db.relationship(
        'Attachment',
        primaryjoin="and_(Attachment.entity_type=='mission', foreign(Attachment.entity_id)==Mission.id)",
        viewonly=True
    )

    def overall_status_label(self):
        mapping = {
            'created': 'جديدة',
            'in_progress': 'قيد التنفيذ',
            'under_central_review': 'قيد مراجعة إدارة المراجعة الداخلية',
            'awaiting_remediation': 'بانتظار التلافي',
            'ready_for_dg': 'جاهزة للمدير العام',
            'closed': 'مغلقة'
        }
        return mapping.get(self.status, self.status)


class MissionRegion(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mission_id = db.Column(db.Integer, db.ForeignKey('mission.id'), nullable=False)
    region_id = db.Column(db.Integer, db.ForeignKey('region.id'), nullable=False)

    status = db.Column(db.String(40), default='pending_region_setup', nullable=False)
    allow_region_to_select_prisons = db.Column(db.Boolean, default=True, nullable=False)

    region_notes = db.Column(db.Text)
    report_summary = db.Column(db.Text)
    recommendations = db.Column(db.Text)
    prison_director_comments = db.Column(db.Text)
    central_review_notes = db.Column(db.Text)
    sent_to_central_at = db.Column(db.DateTime)
    approved_by_central_at = db.Column(db.DateTime)

    mission = db.relationship('Mission', back_populates='regions')
    region = db.relationship('Region')

    prison_reports = db.relationship(
        'MissionPrisonReport',
        back_populates='mission_region',
        cascade='all, delete-orphan',
        order_by='MissionPrisonReport.id'
    )

    attachments = db.relationship(
        'Attachment',
        primaryjoin="and_(Attachment.entity_type=='mission_region', foreign(Attachment.entity_id)==MissionRegion.id)",
        viewonly=True
    )

    @property
    def score_percentage(self):
        scored_reports = [p.score_percentage for p in self.prison_reports if p.has_started]
        if not scored_reports:
            return None
        return round(sum(scored_reports) / len(scored_reports), 2)

    @property
    def risk_level(self):
        score = self.score_percentage
        if score is None:
            return None
        if score >= 85:
            return 'منخفضة'
        if score >= 70:
            return 'متوسطة'
        if score >= 50:
            return 'مرتفعة'
        return 'حرجة'

    @property
    def status_label(self):
        return MISSION_REGION_STATUS_LABELS.get(self.status, self.status)

    @property
    def completed_prisons_count(self):
        return sum(1 for p in self.prison_reports if p.status == 'submitted')

    @property
    def started_prisons_count(self):
        return sum(1 for p in self.prison_reports if p.has_started)

    def open_observations_count(self):
        return sum(p.open_observations_count() for p in self.prison_reports)


class MissionPrisonReport(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mission_region_id = db.Column(db.Integer, db.ForeignKey('mission_region.id'), nullable=False)
    prison_id = db.Column(db.Integer, db.ForeignKey('prison.id'), nullable=False)

    status = db.Column(db.String(40), default='pending_assignment', nullable=False)

    visit_day_name = db.Column(db.String(20))
    visit_date = db.Column(db.Date)
    visit_start_time = db.Column(db.String(10))
    visit_end_time = db.Column(db.String(10))
    visit_type = db.Column(db.String(20), default='scheduled')
    visited_entity = db.Column(db.String(150))

    report_summary = db.Column(db.Text)
    recommendations = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime)

    central_comment = db.Column(db.Text)
    central_commented_at = db.Column(db.DateTime)

    score_percentage_value = db.Column(db.Float, default=0, nullable=False)

    mission_region = db.relationship('MissionRegion', back_populates='prison_reports')
    prison = db.relationship('Prison')

    assignees = db.relationship('User', secondary=mission_prison_assignees, lazy='subquery')

    responses = db.relationship(
        'MissionResponse',
        back_populates='mission_prison_report',
        cascade='all, delete-orphan'
    )

    observations = db.relationship(
        'Observation',
        back_populates='mission_prison_report',
        cascade='all, delete-orphan',
        order_by='Observation.id.desc()'
    )

    attachments = db.relationship(
        'Attachment',
        primaryjoin="and_(Attachment.entity_type=='mission_prison_report', foreign(Attachment.entity_id)==MissionPrisonReport.id)",
        viewonly=True
    )

    @property
    def has_started(self):
        return bool(
            self.visit_date or
            self.responses or
            self.observations or
            self.report_summary or
            self.recommendations or
            self.status in ['in_progress', 'submitted']
        )

    def calculate_score_percentage(self):
        template = self.mission_region.mission.template
        if not template or not template.sections:
            return 0

        total = 0
        response_map = {r.criterion_id: r.score_value for r in self.responses}

        for section in template.sections:
            count = max(len(section.criteria), 1)
            criterion_weight = section.weight_percentage / count
            for criterion in section.criteria:
                value = response_map.get(criterion.id, 0)
                total += (value / 5.0) * criterion_weight

        return round(total, 2)

    @property
    def score_percentage(self):
        if not self.has_started:
            return None
        return round(self.score_percentage_value or 0, 2)

    def refresh_score(self):
        self.score_percentage_value = self.calculate_score_percentage()
        return self.score_percentage_value

    @property
    def risk_level(self):
        score = self.score_percentage
        if score is None:
            return None
        if score >= 85:
            return 'منخفضة'
        if score >= 70:
            return 'متوسطة'
        if score >= 50:
            return 'مرتفعة'
        return 'حرجة'

    @property
    def status_label(self):
        return MISSION_PRISON_REPORT_STATUS_LABELS.get(self.status, self.status)

    def open_observations_count(self):
        return sum(1 for o in self.observations if o.status not in ('closed', 'resolved'))


class MissionResponse(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mission_prison_report_id = db.Column(db.Integer, db.ForeignKey('mission_prison_report.id'), nullable=False)
    criterion_id = db.Column(db.Integer, db.ForeignKey('template_criterion.id'), nullable=False)
    score_label = db.Column(db.String(20), nullable=False)
    score_value = db.Column(db.Integer, nullable=False)

    mission_prison_report = db.relationship('MissionPrisonReport', back_populates='responses')
    criterion = db.relationship('TemplateCriterion')


class Observation(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mission_prison_report_id = db.Column(db.Integer, db.ForeignKey('mission_prison_report.id'), nullable=False)
    criterion_id = db.Column(db.Integer, db.ForeignKey('template_criterion.id'))

    observation_type = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))

    severity = db.Column(db.String(20), nullable=False)
    priority = db.Column(db.String(20), nullable=False)
    sla_option = db.Column(db.String(30), nullable=False)
    due_date = db.Column(db.Date)

    status = db.Column(db.String(30), nullable=False, default='new')
    escalation_reason = db.Column(db.Text)
    escalation_at = db.Column(db.DateTime)

    remediation_recommendation = db.Column(db.Text)
    closure_reason = db.Column(db.Text)
    prison_director_action = db.Column(db.Text)
    department_response = db.Column(db.Text)
    escalated = db.Column(db.Boolean, default=False, nullable=False)

    mission_prison_report = db.relationship('MissionPrisonReport', back_populates='observations')
    criterion = db.relationship('TemplateCriterion')
    department = db.relationship('Department')

    attachments = db.relationship(
        'Attachment',
        primaryjoin="and_(Attachment.entity_type=='observation', foreign(Attachment.entity_id)==Observation.id)",
        viewonly=True
    )


class Attachment(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(30), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    user = db.relationship('User')


class AuditLog(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text)

    user = db.relationship('User')


SCORE_LABELS = {
    'ممتاز': 5,
    'جيد جدًا': 4,
    'مقبول': 3,
    'سيئ': 2,
    'سيئ جدًا': 1,
}

OBS_STATUS = {
    'new': 'جديدة',
    'sent_to_department': 'محالة للإدارة المختصة',
    'under_treatment': 'قيد المعالجة',
    'awaiting_prison_director': 'بانتظار اعتماد مدير المنطقة',
    'awaiting_central': 'بانتظار مراجعة إدارة المراجعة الداخلية',
    'resolved': 'تم التلافي',
    'closed': 'مغلقة',
}

SLA_OPTIONS = {
    '24h': '24 ساعة',
    '3bd': '3 أيام عمل',
    '5bd': '5 أيام عمل',
    '7bd': '7 أيام عمل',
    '14bd': '14 يوم عمل',
    '30d': '30 يومًا',
}

MISSION_CLASSIFICATIONS = {
    'annual_plan': 'ضمن الخطة السنوية',
    'quarterly_plan': 'ضمن الخطة الربع سنوية',
    'follow_up': 'متابعة',
    'ad_hoc': 'مهمة غير مجدولة',
}

PRIORITY_LEVELS = {
    'normal': 'عادية',
    'medium': 'متوسطة',
    'high': 'عالية',
    'critical': 'حرجة',
}

ASSIGNMENT_MODES = {
    'region_manager_selects': 'يترك لمدير شعبة المراجعة بالمنطقة',
    'central_defined': 'يحدد من إدارة المراجعة الداخلية',
    'central_with_region_completion': 'إسناد من إدارة المراجعة الداخلية مع استكمال من المنطقة',
}

ROLE_LABELS = {
    'central_admin': 'مختص إدارة المراجعة الداخلية',
    'central_operator': 'مختص إدارة المراجعة الداخلية',
    'central_director': 'مدير إدارة المراجعة الداخلية',
    'director_general': 'المدير العام',
    'region_manager': 'مدير شعبة المراجعة بالمنطقة',
    'executor': 'منفذ جولات المراجعة',
    'prison_director': 'مدير سجون المنطقة',
    'department_user': 'الإدارة المختصة',
    'department_manager': 'الإدارة المختصة',
}

MISSION_CLASSIFICATION_LABELS = {
    'annual_plan': 'خطة سنوية',
    'quarterly_plan': 'خطة ربع سنوية',
    'follow_up': 'متابعة',
    'ad_hoc': 'مهمة عادية',
}

PRIORITY_LEVEL_LABELS = {
    'normal': 'عادية',
    'medium': 'متوسطة',
    'high': 'عالية',
    'critical': 'حرجة',
}

MISSION_STATUS_LABELS = {
    'created': 'جديدة',
    'in_progress': 'قيد التنفيذ',
    'under_central_review': 'قيد مراجعة إدارة المراجعة الداخلية',
    'awaiting_remediation': 'بانتظار التلافي',
    'ready_for_dg': 'جاهزة للمدير العام',
    'closed': 'مغلقة',
}

ASSIGNMENT_MODE_LABELS = {
    'region_manager_selects': 'يترك لمدير المنطقة',
    'central_defined': 'إسناد من إدارة المراجعة الداخلية',
    'central_with_region_completion': 'إسناد من إدارة المراجعة الداخلية مع استكمال من المنطقة',
}

MISSION_REGION_STATUS_LABELS = {
    'pending_region_setup': 'بانتظار التجهيز',
    'assigned': 'مجهزة',
    'in_progress': 'قيد التنفيذ',
    'submitted_to_central': 'مرفوعة إلى إدارة المراجعة الداخلية',
}

MISSION_PRISON_REPORT_STATUS_LABELS = {
    'pending_assignment': 'بانتظار الإسناد',
    'assigned': 'مسندة',
    'in_progress': 'قيد التنفيذ',
    'submitted': 'مرفوعة',
}