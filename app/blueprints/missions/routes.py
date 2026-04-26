from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy import or_

from ...extensions import db
from ...permissions import roles_required
from ...utils import save_uploaded_files, compute_due_date, log_action

from ...models import (
    Mission, MissionRegion, MissionPrisonReport,
    Region, Prison, User, Template, TemplateSection, TemplateCriterion,
    MissionResponse, Observation, Attachment, Department,
    SCORE_LABELS, OBS_STATUS, SLA_OPTIONS,
    MISSION_CLASSIFICATIONS, PRIORITY_LEVELS, ASSIGNMENT_MODES,
    AuditLog,
    MISSION_CLASSIFICATION_LABELS, PRIORITY_LEVEL_LABELS,
    MISSION_STATUS_LABELS, ASSIGNMENT_MODE_LABELS
)

missions_bp = Blueprint('missions', __name__, url_prefix='/missions')


def _next_reference():
    count = Mission.query.count() + 1
    return f'IA-{date.today().year}-{count:03d}'


def _score_options():
    return list(SCORE_LABELS.keys())


def _normalize_text(value):
    return ' '.join((value or '').strip().split())


@missions_bp.route('/')
@login_required
def index():
    q = Mission.query.options(
        joinedload(Mission.regions).joinedload(MissionRegion.region),
        joinedload(Mission.template)
    ).order_by(Mission.created_at.desc())

    if current_user.role == 'director_general':
        q = q.filter(Mission.status.in_(['ready_for_dg', 'closed']))

    search = (request.args.get('search') or '').strip()
    template_id = (request.args.get('template_id') or '').strip()
    mission_classification = (request.args.get('mission_classification') or '').strip()
    priority_level = (request.args.get('priority_level') or '').strip()
    status = (request.args.get('status') or '').strip()

    if search:
        q = q.filter(
            or_(
                Mission.title.ilike(f'%{search}%'),
                Mission.reference_no.ilike(f'%{search}%')
            )
        )

    if template_id:
        q = q.filter(Mission.template_id == int(template_id))

    if mission_classification:
        q = q.filter(Mission.mission_classification == mission_classification)

    if priority_level:
        q = q.filter(Mission.priority_level == priority_level)

    if status:
        q = q.filter(Mission.status == status)

    missions = q.all()
    templates = Template.query.filter_by(is_active=True).order_by(Template.name.asc()).all()

    stats = {
        'total': len(missions),
        'new': sum(1 for m in missions if m.status == 'created'),
        'in_progress': sum(1 for m in missions if m.status in ['in_progress', 'under_central_review', 'awaiting_remediation']),
        'critical': sum(1 for m in missions if m.priority_level == 'critical'),
        'ready_for_dg': sum(1 for m in missions if m.status == 'ready_for_dg'),
    }

    return render_template(
        'missions/index.html',
        missions=missions,
        templates=templates,
        stats=stats,
        mission_classification_labels=MISSION_CLASSIFICATION_LABELS,
        priority_level_labels=PRIORITY_LEVEL_LABELS,
        status_labels=MISSION_STATUS_LABELS,
        assignment_mode_labels=ASSIGNMENT_MODE_LABELS,
        filters={
            'search': search,
            'template_id': template_id,
            'mission_classification': mission_classification,
            'priority_level': priority_level,
            'status': status,
        }
    )


@missions_bp.route('/create', methods=['GET', 'POST'])
@login_required
@roles_required('central_admin', 'central_operator', 'central_director')
def create():
    templates = Template.query.filter_by(is_active=True).order_by(Template.name).all()
    regions = Region.query.options(joinedload(Region.prisons)).order_by(Region.name).all()
    candidate_users = User.query.filter(
        User.role == 'executor',
        User.is_active_user == True
    ).order_by(User.full_name).all()

    form_data = {
        'title': '',
        'template_id': '',
        'mission_classification': '',
        'priority_level': '',
        'planned_date': '',
        'due_date': '',
        'global_prison_scope': '',
        'assignment_mode': '',
        'task_instructions': '',
        'region_ids': [],
        'prison_scope': {},
        'selected_prisons': {},
        'selected_assignees': {}
    }

    if request.method == 'POST':
        form_data = {
            'title': request.form.get('title', ''),
            'template_id': request.form.get('template_id', ''),
            'mission_classification': request.form.get('mission_classification', ''),
            'priority_level': request.form.get('priority_level', ''),
            'planned_date': request.form.get('planned_date', ''),
            'due_date': request.form.get('due_date', ''),
            'global_prison_scope': request.form.get('global_prison_scope', ''),
            'assignment_mode': request.form.get('assignment_mode', ''),
            'task_instructions': request.form.get('task_instructions', ''),
            'region_ids': request.form.getlist('region_ids'),
            'prison_scope': {},
            'selected_prisons': {},
            'selected_assignees': {}
        }

        for region in regions:
            rid = str(region.id)
            form_data['prison_scope'][rid] = request.form.get(f'prison_scope_{rid}', 'defer')
            form_data['selected_prisons'][rid] = request.form.getlist(f'prisons_{rid}')
            form_data['selected_assignees'][rid] = request.form.getlist(f'central_assignees_{rid}')

        title = _normalize_text(form_data['title'])
        template_id = form_data['template_id']
        mission_classification = form_data['mission_classification']
        priority_level = form_data['priority_level']
        assignment_mode = form_data['assignment_mode']
        planned_date = form_data['planned_date']
        due_date = form_data['due_date']
        task_instructions = (form_data['task_instructions'] or '').strip()
        region_ids = form_data['region_ids']

        if not title:
            flash('عنوان المهمة حقل إلزامي.', 'danger')
            return render_template(
                'missions/create.html',
                templates=templates,
                regions=regions,
                candidate_users=candidate_users,
                form_data=form_data
            )

        if not template_id:
            flash('اختيار النموذج حقل إلزامي.', 'danger')
            return render_template(
                'missions/create.html',
                templates=templates,
                regions=regions,
                candidate_users=candidate_users,
                form_data=form_data
            )

        if not mission_classification:
            flash('تصنيف المهمة حقل إلزامي.', 'danger')
            return render_template(
                'missions/create.html',
                templates=templates,
                regions=regions,
                candidate_users=candidate_users,
                form_data=form_data
            )

        if not priority_level:
            flash('أولوية التنفيذ حقل إلزامي.', 'danger')
            return render_template(
                'missions/create.html',
                templates=templates,
                regions=regions,
                candidate_users=candidate_users,
                form_data=form_data
            )

        if not planned_date:
            flash('تاريخ التنفيذ المستهدف حقل إلزامي.', 'danger')
            return render_template(
                'missions/create.html',
                templates=templates,
                regions=regions,
                candidate_users=candidate_users,
                form_data=form_data
            )

        if not due_date:
            flash('تاريخ الاستحقاق حقل إلزامي.', 'danger')
            return render_template(
                'missions/create.html',
                templates=templates,
                regions=regions,
                candidate_users=candidate_users,
                form_data=form_data
            )

        if not form_data['global_prison_scope']:
            flash('نطاق السجون حقل إلزامي.', 'danger')
            return render_template(
                'missions/create.html',
                templates=templates,
                regions=regions,
                candidate_users=candidate_users,
                form_data=form_data
            )

        if not assignment_mode:
            flash('آلية الإسناد حقل إلزامي.', 'danger')
            return render_template(
                'missions/create.html',
                templates=templates,
                regions=regions,
                candidate_users=candidate_users,
                form_data=form_data
            )

        if not region_ids:
            flash('يجب اختيار منطقة واحدة على الأقل.', 'danger')
            return render_template(
                'missions/create.html',
                templates=templates,
                regions=regions,
                candidate_users=candidate_users,
                form_data=form_data
            )

        # التحقق من صحة التواريخ
        try:
            planned_date_obj = date.fromisoformat(planned_date)
            due_date_obj = date.fromisoformat(due_date)
        except ValueError:
            flash('صيغة التاريخ غير صحيحة.', 'danger')
            return render_template(
                'missions/create.html',
                templates=templates,
                regions=regions,
                candidate_users=candidate_users,
                form_data=form_data
            )

        if due_date_obj < planned_date_obj:
            flash('تاريخ الاستحقاق يجب أن يكون مساويًا أو بعد تاريخ التنفيذ المستهدف.', 'danger')
            return render_template(
                'missions/create.html',
                templates=templates,
                regions=regions,
                candidate_users=candidate_users,
                form_data=form_data
            )

        mission = Mission(
            reference_no=_next_reference(),
            title=title,
            template_id=int(template_id),
            mission_classification=mission_classification,
            priority_level=priority_level,
            assignment_mode=assignment_mode,
            planned_date=planned_date_obj,
            due_date=due_date_obj,
            task_instructions=task_instructions or None,
            status='created',
            created_by=current_user.id
        )
        db.session.add(mission)
        db.session.flush()

        for rid in region_ids:
            region = db.session.get(Region, int(rid))
            if not region:
                db.session.rollback()
                flash('تعذر العثور على إحدى المناطق المحددة.', 'danger')
                return render_template(
                    'missions/create.html',
                    templates=templates,
                    regions=regions,
                    candidate_users=candidate_users,
                    form_data=form_data
                )

            prison_scope = request.form.get(f'prison_scope_{rid}') or request.form.get('global_prison_scope') or 'defer'
            selected_prison_ids = request.form.getlist(f'prisons_{rid}')
            selected_assignee_ids = request.form.getlist(f'central_assignees_{rid}')

            if assignment_mode == 'central_defined' and prison_scope != 'fixed':
                db.session.rollback()
                flash(f'عند اختيار الإسناد المسبق من إدارة المراجعة الداخلية يجب تحديد السجون مسبقًا في منطقة {region.name}.', 'danger')
                return render_template(
                    'missions/create.html',
                    templates=templates,
                    regions=regions,
                    candidate_users=candidate_users,
                    form_data=form_data
                )

            if assignment_mode in ['central_defined', 'central_with_region_completion'] and prison_scope == 'fixed' and not selected_assignee_ids:
                db.session.rollback()
                flash(f'تم اختيار إسناد مسبق في منطقة {region.name} بدون تحديد منفذين.', 'danger')
                return render_template(
                    'missions/create.html',
                    templates=templates,
                    regions=regions,
                    candidate_users=candidate_users,
                    form_data=form_data
                )

            mission_region = MissionRegion(
                mission=mission,
                region=region,
                status='pending_region_setup',
                allow_region_to_select_prisons=(prison_scope != 'fixed'),
                region_notes=''
            )
            db.session.add(mission_region)
            db.session.flush()

            if prison_scope == 'fixed':
                if not selected_prison_ids:
                    db.session.rollback()
                    flash(f'تم اختيار تحديد السجون الآن في منطقة {region.name} بدون اختيار أي سجن.', 'danger')
                    return render_template(
                        'missions/create.html',
                        templates=templates,
                        regions=regions,
                        candidate_users=candidate_users,
                        form_data=form_data
                    )

                selected_users = []
                if selected_assignee_ids:
                    for uid in selected_assignee_ids:
                        user = db.session.get(User, int(uid))
                        if user:
                            selected_users.append(user)

                for pid in selected_prison_ids:
                    prison = db.session.get(Prison, int(pid))
                    if not prison:
                        continue

                    prison_report = MissionPrisonReport(
                        mission_region=mission_region,
                        prison=prison,
                        status='assigned' if selected_users else 'pending_assignment'
                    )

                    if selected_users:
                        prison_report.assignees = selected_users

                    db.session.add(prison_report)

                if selected_users:
                    mission_region.status = 'assigned'

            log_action(
                current_user.id,
                'create_mission_region',
                'mission_region',
                mission_region.id,
                f'إنشاء نطاق منطقة: {region.name}'
            )

        db.session.flush()

        save_uploaded_files(
            request.files.getlist('attachments'),
            'mission',
            mission.id,
            current_user.id,
            Attachment
        )

        log_action(current_user.id, 'create_mission', 'mission', mission.id, 'إنشاء مهمة جديدة')
        db.session.commit()

        flash('تم إنشاء المهمة بنجاح.', 'success')
        return redirect(url_for('missions.detail', mission_id=mission.id))

    return render_template(
        'missions/create.html',
        templates=templates,
        regions=regions,
        candidate_users=candidate_users,
        form_data=form_data
    )


@missions_bp.route('/<int:mission_id>')
@login_required
def detail(mission_id):
    mission = Mission.query.options(
        joinedload(Mission.template).joinedload(Template.sections).joinedload(TemplateSection.criteria),
        joinedload(Mission.regions).joinedload(MissionRegion.region),
        joinedload(Mission.regions).joinedload(MissionRegion.prison_reports).joinedload(MissionPrisonReport.prison),
        joinedload(Mission.regions).joinedload(MissionRegion.prison_reports).joinedload(MissionPrisonReport.assignees),
        joinedload(Mission.regions).joinedload(MissionRegion.prison_reports).joinedload(MissionPrisonReport.observations)
    ).get_or_404(mission_id)

    region_ids = [mr.id for mr in mission.regions] or [0]
    prison_report_ids = [pr.id for mr in mission.regions for pr in mr.prison_reports] or [0]
    observation_ids = [o.id for mr in mission.regions for pr in mr.prison_reports for o in pr.observations] or [0]

    entity_logs = AuditLog.query.filter(
        ((AuditLog.entity_type == 'mission') & (AuditLog.entity_id == mission.id)) |
        ((AuditLog.entity_type == 'mission_region') & (AuditLog.entity_id.in_(region_ids))) |
        ((AuditLog.entity_type == 'mission_prison_report') & (AuditLog.entity_id.in_(prison_report_ids))) |
        ((AuditLog.entity_type == 'observation') & (AuditLog.entity_id.in_(observation_ids)))
    ).order_by(AuditLog.created_at.desc()).limit(80).all()

    return render_template(
        'missions/detail.html',
        mission=mission,
        mission_classifications=MISSION_CLASSIFICATIONS,
        priority_levels=PRIORITY_LEVELS,
        entity_logs=entity_logs
    )


@missions_bp.route('/region/<int:mission_region_id>/setup', methods=['GET', 'POST'])
@login_required
@roles_required('region_manager', 'central_admin', 'central_operator', 'central_director')
def region_setup(mission_region_id):
    mr = MissionRegion.query.options(
        joinedload(MissionRegion.region).joinedload(Region.prisons),
        joinedload(MissionRegion.prison_reports).joinedload(MissionPrisonReport.prison),
        joinedload(MissionRegion.prison_reports).joinedload(MissionPrisonReport.assignees),
        joinedload(MissionRegion.mission)
    ).get_or_404(mission_region_id)

    if current_user.role == 'region_manager' and current_user.region_id != mr.region_id:
        flash('لا يمكن الوصول إلى هذه المنطقة.', 'danger')
        return redirect(url_for('missions.index'))

    users = User.query.filter(
        User.role == 'executor',
        User.is_active_user == True,
        db.or_(User.region_id == mr.region_id, User.org_unit_type == 'central')
    ).order_by(User.full_name).all()

    if request.method == 'POST':
        selected_prison_ids = request.form.getlist('prison_ids')
        if not selected_prison_ids:
            flash('يجب اختيار سجن واحد على الأقل.', 'danger')
            return render_template('missions/region_setup.html', mr=mr, users=users)

        selected_assignee_ids = request.form.getlist('assignee_ids')
        selected_users = [db.session.get(User, int(uid)) for uid in selected_assignee_ids] if selected_assignee_ids else []

        existing_reports_by_prison = {r.prison_id: r for r in mr.prison_reports}

        for report in list(mr.prison_reports):
            if str(report.prison_id) not in selected_prison_ids:
                db.session.delete(report)

        for pid in selected_prison_ids:
            prison_id = int(pid)
            prison = db.session.get(Prison, prison_id)

            if prison_id in existing_reports_by_prison:
                report = existing_reports_by_prison[prison_id]
            else:
                report = MissionPrisonReport(
                    mission_region=mr,
                    prison=prison
                )
                db.session.add(report)

            report.assignees = selected_users
            report.status = 'assigned' if selected_users else 'pending_assignment'

        mr.region_notes = request.form.get('region_notes')
        mr.status = 'assigned' if selected_users else 'pending_region_setup'

        db.session.flush()
        log_action(current_user.id, 'setup_region_task', 'mission_region', mr.id, 'تحديد السجون والمنفذين على مستوى المنطقة')
        db.session.commit()

        flash('تم تحديث تجهيز المنطقة.', 'success')
        return redirect(url_for('missions.detail', mission_id=mr.mission_id))

    return render_template('missions/region_setup.html', mr=mr, users=users)


@missions_bp.route('/prison-report/<int:prison_report_id>/execute', methods=['GET', 'POST'])
@login_required
@roles_required('executor', 'region_manager', 'central_admin', 'central_operator', 'central_director')
def prison_execute(prison_report_id):
    pr = MissionPrisonReport.query.options(
        joinedload(MissionPrisonReport.mission_region).joinedload(MissionRegion.region),
        joinedload(MissionPrisonReport.mission_region).joinedload(MissionRegion.mission).joinedload(Mission.template).joinedload(Template.sections).joinedload(TemplateSection.criteria),
        joinedload(MissionPrisonReport.prison),
        joinedload(MissionPrisonReport.assignees),
        joinedload(MissionPrisonReport.responses),
        joinedload(MissionPrisonReport.observations)
    ).get_or_404(prison_report_id)

    if current_user.role == 'executor' and current_user not in pr.assignees:
        flash('هذا التقرير غير مسند لك.', 'danger')
        return redirect(url_for('missions.index'))

    departments = Department.query.order_by(Department.name).all()

    if request.method == 'POST':
        pr.visit_date = date.fromisoformat(request.form.get('visit_date')) if request.form.get('visit_date') else date.today()
        pr.visit_day_name = request.form.get('visit_day_name') or pr.visit_date.strftime('%A')
        pr.visit_start_time = request.form.get('visit_start_time')
        pr.visit_end_time = request.form.get('visit_end_time')
        pr.visit_type = request.form.get('visit_type') or 'scheduled'
        pr.visited_entity = request.form.get('visited_entity') or pr.prison.name
        pr.report_summary = request.form.get('report_summary')
        pr.recommendations = request.form.get('recommendations')

        template = pr.mission_region.mission.template
        for section in template.sections:
            for criterion in section.criteria:
                field = f'score_{criterion.id}'
                label = request.form.get(field)
                if not label:
                    continue

                existing = MissionResponse.query.filter_by(
                    mission_prison_report_id=pr.id,
                    criterion_id=criterion.id
                ).first()

                if existing:
                    existing.score_label = label
                    existing.score_value = SCORE_LABELS[label]
                else:
                    db.session.add(
                        MissionResponse(
                            mission_prison_report=pr,
                            criterion=criterion,
                            score_label=label,
                            score_value=SCORE_LABELS[label]
                        )
                    )

        if request.form.get('obs_title') and request.form.get('obs_description'):
            obs = Observation(
                mission_prison_report=pr,
                observation_type=request.form.get('observation_type'),
                criterion_id=int(request.form.get('criterion_id')) if request.form.get('criterion_id') else None,
                title=request.form.get('obs_title'),
                description=request.form.get('obs_description'),
                category=request.form.get('category'),
                department_id=int(request.form.get('department_id')) if request.form.get('department_id') else None,
                severity=request.form.get('severity'),
                priority=request.form.get('priority'),
                sla_option=request.form.get('sla_option'),
                due_date=compute_due_date(request.form.get('sla_option')),
                remediation_recommendation=request.form.get('remediation_recommendation'),
                status='new'
            )
            db.session.add(obs)
            db.session.flush()

            save_uploaded_files(
                request.files.getlist('observation_attachments'),
                'observation',
                obs.id,
                current_user.id,
                Attachment
            )

        save_uploaded_files(
            request.files.getlist('report_attachments'),
            'mission_prison_report',
            pr.id,
            current_user.id,
            Attachment
        )

        pr.refresh_score()
        pr.status = 'in_progress'

        mr = pr.mission_region
        mr.status = 'in_progress'
        if mr.mission.status == 'created':
            mr.mission.status = 'in_progress'

        log_action(current_user.id, 'save_execution', 'mission_prison_report', pr.id, 'تحديث تنفيذ السجن والملاحظات')
        db.session.commit()

        flash('تم حفظ التنفيذ بنجاح.', 'success')
        return redirect(url_for('missions.prison_execute', prison_report_id=pr.id))

    return render_template(
        'missions/prison_execute.html',
        pr=pr,
        departments=departments,
        score_options=_score_options(),
        sla_options=SLA_OPTIONS
    )


@missions_bp.route('/prison-report/<int:prison_report_id>/submit', methods=['POST'])
@login_required
@roles_required('executor', 'region_manager', 'central_admin', 'central_operator', 'central_director')
def submit_prison_report(prison_report_id):
    pr = MissionPrisonReport.query.options(joinedload(MissionPrisonReport.mission_region).joinedload(MissionRegion.mission)).get_or_404(prison_report_id)

    if current_user.role == 'executor' and current_user not in pr.assignees:
        flash('لا يمكن تنفيذ هذا الإجراء.', 'danger')
        return redirect(url_for('missions.index'))

    pr.status = 'submitted'
    pr.submitted_at = datetime.utcnow()

    mr = pr.mission_region
    if all(r.status == 'submitted' for r in mr.prison_reports):
        mr.status = 'submitted_to_central'
        mr.sent_to_central_at = datetime.utcnow()
        if mr.mission.status == 'created':
            mr.mission.status = 'under_central_review'
        elif mr.mission.status == 'in_progress':
            mr.mission.status = 'under_central_review'

    log_action(current_user.id, 'submit_prison_report', 'mission_prison_report', pr.id, 'رفع تقرير السجن')
    db.session.commit()

    flash('تم رفع تقرير السجن.', 'success')
    return redirect(url_for('missions.detail', mission_id=mr.mission_id))


@missions_bp.route('/observation/<int:observation_id>', methods=['GET', 'POST'])
@login_required
def observation_detail(observation_id):
    observation = Observation.query.options(
        joinedload(Observation.mission_prison_report).joinedload(MissionPrisonReport.prison),
        joinedload(Observation.mission_prison_report).joinedload(MissionPrisonReport.mission_region).joinedload(MissionRegion.mission),
        joinedload(Observation.department),
        joinedload(Observation.criterion)
    ).get_or_404(observation_id)

    if request.method == 'POST':
        action = request.form.get('action')

        if current_user.role in ['department_user', 'department_manager'] and current_user.department_id == observation.department_id:
            observation.department_response = request.form.get('department_response')
            observation.status = request.form.get('status') or 'under_treatment'

        elif current_user.role == 'prison_director' and current_user.region_id == observation.mission_prison_report.mission_region.region_id:
            observation.prison_director_action = request.form.get('prison_director_action')
            observation.status = request.form.get('status') or 'awaiting_central'

        elif current_user.role in ['central_admin', 'central_operator', 'central_director']:
            observation.status = request.form.get('status') or observation.status
            observation.closure_reason = request.form.get('closure_reason')
            observation.escalated = bool(request.form.get('escalated'))
            observation.escalation_reason = request.form.get('escalation_reason')
            observation.escalation_at = datetime.utcnow() if observation.escalated else None

        if request.form.get('closure_reason'):
            observation.closure_reason = request.form.get('closure_reason')

        save_uploaded_files(
            request.files.getlist('attachments'),
            'observation',
            observation.id,
            current_user.id,
            Attachment
        )

        log_action(current_user.id, 'update_observation', 'observation', observation.id, action or 'تحديث الملاحظة')
        db.session.commit()

        flash('تم تحديث الملاحظة.', 'success')
        return redirect(url_for('missions.observation_detail', observation_id=observation.id))

    return render_template('missions/observation_detail.html', observation=observation, obs_status=OBS_STATUS)


@missions_bp.route('/region/<int:mission_region_id>/prison-director', methods=['GET', 'POST'])
@login_required
@roles_required('prison_director', 'central_admin', 'central_operator', 'central_director')
def prison_director_review(mission_region_id):
    mr = MissionRegion.query.options(
        joinedload(MissionRegion.prison_reports).joinedload(MissionPrisonReport.prison),
        joinedload(MissionRegion.prison_reports).joinedload(MissionPrisonReport.observations).joinedload(Observation.department),
        joinedload(MissionRegion.region),
        joinedload(MissionRegion.mission)
    ).get_or_404(mission_region_id)

    if current_user.role == 'prison_director' and current_user.region_id != mr.region_id:
        flash('لا يمكن الوصول لهذا التقرير.', 'danger')
        return redirect(url_for('dashboard.home'))

    if request.method == 'POST':
        mr.prison_director_comments = request.form.get('prison_director_comments')

        for pr in mr.prison_reports:
            for obs in pr.observations:
                status = request.form.get(f'status_{obs.id}')
                if status:
                    obs.status = status

        log_action(current_user.id, 'prison_director_review', 'mission_region', mr.id, 'اعتماد ومتابعة ملاحظات المنطقة')
        db.session.commit()

        flash('تم تحديث مراجعة مدير سجون المنطقة.', 'success')
        return redirect(url_for('missions.prison_director_review', mission_region_id=mr.id))

    return render_template('missions/prison_director_review.html', mr=mr, obs_status=OBS_STATUS)


@missions_bp.route('/<int:mission_id>/central-review', methods=['GET', 'POST'])
@login_required
@roles_required('central_admin', 'central_operator', 'central_director')
def central_review(mission_id):
    mission = Mission.query.options(
        joinedload(Mission.regions).joinedload(MissionRegion.region),
        joinedload(Mission.regions).joinedload(MissionRegion.prison_reports).joinedload(MissionPrisonReport.prison),
        joinedload(Mission.regions).joinedload(MissionRegion.prison_reports).joinedload(MissionPrisonReport.observations)
    ).get_or_404(mission_id)

    if request.method == 'POST':
        mission.final_summary = request.form.get('final_summary')
        mission.final_recommendations = request.form.get('final_recommendations')
        mission.internal_audit_opinion = request.form.get('internal_audit_opinion')

        action = request.form.get('central_action')
        if action == 'send_dg':
            mission.status = 'ready_for_dg'
            mission.sent_to_dg_at = datetime.utcnow()
        elif action == 'await_remediation':
            mission.status = 'awaiting_remediation'
        else:
            mission.status = 'under_central_review'

        log_action(current_user.id, 'central_review_mission', 'mission', mission.id, f'إجراء: {action}')
        db.session.commit()

        flash('تم تحديث المراجعة المركزية.', 'success')
        return redirect(url_for('missions.central_review', mission_id=mission.id))

    return render_template('missions/central_review.html', mission=mission)


@missions_bp.route('/<int:mission_id>/dg-review', methods=['GET', 'POST'])
@login_required
@roles_required('director_general')
def dg_review(mission_id):
    mission = Mission.query.options(
        joinedload(Mission.regions).joinedload(MissionRegion.region)
    ).get_or_404(mission_id)

    if mission.status not in ['ready_for_dg', 'closed']:
        flash('هذا التقرير لم يرسل للمدير العام بعد.', 'warning')
        return redirect(url_for('dashboard.home'))

    if request.method == 'POST':
        mission.dg_decision = request.form.get('dg_decision')
        if request.form.get('action') == 'close':
            mission.status = 'closed'

        log_action(current_user.id, 'dg_review', 'mission', mission.id, 'قرار المدير العام')
        db.session.commit()

        flash('تم حفظ قرار المدير العام.', 'success')
        return redirect(url_for('missions.dg_review', mission_id=mission.id))

    return render_template('missions/dg_review.html', mission=mission)


@missions_bp.route('/attachments/<filename>')
@login_required
def attachment(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename, as_attachment=True)