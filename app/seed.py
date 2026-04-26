from datetime import date, timedelta
from .extensions import db
from .models import (
    Region, Prison, Department, User,
    Template, TemplateSection, TemplateCriterion,
    AnnualPlan, PlanItem,
    Mission, MissionRegion, MissionPrisonReport,
    MissionResponse, Observation, AuditLog,
    SCORE_LABELS
)

REGIONS = [
    'الرياض', 'مكة المكرمة', 'المدينة المنورة', 'القصيم', 'المنطقة الشرقية',
    'عسير', 'تبوك', 'حائل', 'الحدود الشمالية', 'جازان',
    'نجران', 'الباحة', 'الجوف'
]

PRISONS = {
    'الرياض': ['سجن الحائر', 'سجن الملز', 'إصلاحية الرياض'],
    'مكة المكرمة': ['سجن مكة العام', 'إصلاحية جدة', 'سجن الطائف'],
    'المدينة المنورة': ['سجن المدينة العام', 'إصلاحية ينبع'],
    'القصيم': ['سجن بريدة', 'إصلاحية عنيزة'],
    'المنطقة الشرقية': ['سجن الدمام', 'إصلاحية الأحساء', 'سجن الجبيل'],
    'عسير': ['سجن أبها', 'إصلاحية خميس مشيط'],
    'تبوك': ['سجن تبوك العام'],
    'حائل': ['سجن حائل العام'],
    'الحدود الشمالية': ['سجن عرعر العام'],
    'جازان': ['سجن جازان العام'],
    'نجران': ['سجن نجران العام'],
    'الباحة': ['سجن الباحة العام'],
    'الجوف': ['سجن سكاكا العام'],
}

DEPARTMENTS = [
    ('إدارة تقنية المعلومات', 'IT'),
    ('إدارة السلامة', 'SAFETY'),
    ('إدارة العمليات', 'OPS'),
    ('إدارة المخزون', 'WAREHOUSE'),
    ('إدارة الموارد البشرية', 'HR'),
    ('الإدارة المالية', 'FIN'),
]


def add_log(user_id, action, entity_type, entity_id, notes):
    db.session.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            notes=notes
        )
    )


def seed_if_empty():
    if User.query.first():
        return

    regions = {}
    for r in REGIONS:
        obj = Region(name=r)
        db.session.add(obj)
        regions[r] = obj
    db.session.flush()

    departments = {}
    for d_name, d_code in DEPARTMENTS:
        obj = Department(name=d_name, code=d_code)
        db.session.add(obj)
        departments[d_name] = obj
    db.session.flush()

    prisons = {}
    for region_name, items in PRISONS.items():
        for prison_name in items:
            obj = Prison(name=prison_name, region=regions[region_name])
            db.session.add(obj)
            prisons[prison_name] = obj
    db.session.flush()

    def add_user(username, full_name, role, job_title, region=None, department=None, org_unit_type='regional'):
        u = User(
            username=username,
            full_name=full_name,
            role=role,
            job_title=job_title,
            region=region,
            department=department,
            org_unit_type=org_unit_type
        )
        u.set_password('123456')
        db.session.add(u)
        return u

    central_admin = add_user('central_admin', 'تركي العتيبي', 'central_admin', 'مختص إدارة المراجعة الداخلية', org_unit_type='central')
    central_operator = add_user('central_operator', 'محمد الحربي', 'central_operator', 'مختص إدارة المراجعة الداخلية', org_unit_type='central')
    central_director = add_user('central_director', 'عبدالله السبيعي', 'central_director', 'مدير إدارة المراجعة الداخلية', org_unit_type='central')
    dg = add_user('dg', 'سلمان الشهراني', 'director_general', 'المدير العام', org_unit_type='central')

    region_managers = {}
    prison_directors = {}
    executors = {}

    for idx, region_name in enumerate(REGIONS, start=1):
        reg = regions[region_name]
        region_managers[region_name] = add_user(
            f'region_mgr_{idx}',
            f'مدير شعبة مراجعة {region_name}',
            'region_manager',
            'مدير شعبة المراجعة بالمنطقة',
            region=reg
        )
        prison_directors[region_name] = add_user(
            f'prison_dir_{idx}',
            f'مدير سجون {region_name}',
            'prison_director',
            'مدير سجون المنطقة',
            region=reg
        )
        executors[region_name] = [
            add_user(f'executor_{idx}_1', f'منفذ أول {region_name}', 'executor', 'أخصائي مراجعة', region=reg),
            add_user(f'executor_{idx}_2', f'منفذ ثان {region_name}', 'executor', 'أخصائي مراجعة', region=reg),
        ]

    add_user('dept_it', 'محمد الدوسري', 'department_manager', 'مدير الإدارة المختصة', department=departments['إدارة تقنية المعلومات'], org_unit_type='central')
    add_user('dept_ops', 'راشد القحطاني', 'department_manager', 'مدير الإدارة المختصة', department=departments['إدارة العمليات'], org_unit_type='central')
    add_user('dept_safety', 'خالد الشهري', 'department_manager', 'مدير الإدارة المختصة', department=departments['إدارة السلامة'], org_unit_type='central')
    db.session.flush()

    t1 = Template(
        name='نشاط مراجعة السلامة في السجون',
        code='SAFETY-001',
        description='نموذج رقابي لمراجعة السلامة داخل السجون',
        is_active=True
    )
    t2 = Template(
        name='جولة تفتيشية لنشاط الأمانات النقدية والعينية',
        code='TREASURY-001',
        description='نموذج تفتيشي للأمانات النقدية والعينية',
        is_active=True
    )
    db.session.add_all([t1, t2])
    db.session.flush()

    def build_template(template, sec1, sec2, sec3):
        s1 = TemplateSection(template=template, title=sec1, weight_percentage=35, sort_order=1)
        s2 = TemplateSection(template=template, title=sec2, weight_percentage=40, sort_order=2)
        s3 = TemplateSection(template=template, title=sec3, weight_percentage=25, sort_order=3)
        db.session.add_all([s1, s2, s3])
        db.session.flush()

        criteria = [
            (s1, 'الالتزام بالتعاميم المعتمدة', 1),
            (s1, 'وجود محاضر محدثة', 2),
            (s1, 'توثيق الجولات السابقة', 3),

            (s2, 'جاهزية الطفايات', 1),
            (s2, 'سلامة التمديدات الكهربائية', 2),
            (s2, 'وضوح مخارج الطوارئ', 3),
            (s2, 'عمل أنظمة الإنذار', 4),
            (s2, 'توافر أدوات الإسعاف', 5),

            (s3, 'إقفال الملاحظات السابقة', 1),
            (s3, 'اكتمال ملفات المتابعة', 2),
            (s3, 'رفع التقارير في الوقت', 3),
        ]
        for sec, text, order in criteria:
            db.session.add(TemplateCriterion(section=sec, text=text, sort_order=order))

    build_template(t1, 'الالتزام الإجرائي', 'الجاهزية التشغيلية', 'التوثيق والمتابعة')
    build_template(t2, 'الضبط والرقابة', 'إدارة العهد', 'التوثيق والمتابعة')
    db.session.flush()

    plan = AnnualPlan(
        title='الخطة السنوية للجولات والأنشطة الرقابية 2026',
        year=2026,
        notes='خطة تجريبية للعرض'
    )
    db.session.add(plan)
    db.session.flush()

    db.session.add(
        PlanItem(
            plan=plan,
            title='مراجعة السلامة - الربع الأول',
            template=t1,
            planned_date=date.today() + timedelta(days=15),
            notes='عنصر من الخطة السنوية'
        )
    )

    db.session.add(
        PlanItem(
            plan=plan,
            title='تفتيش الأمانات النقدية والعينية - أبريل',
            template=t2,
            planned_date=date.today() + timedelta(days=30),
            notes='عنصر من الخطة السنوية'
        )
    )
    db.session.flush()

    mission_specs = [
        {
            'reference_no': 'IA-2026-001',
            'title': 'مراجعة السلامة على السجون الرئيسة للربع الأول',
            'template': t1,
            'mission_classification': 'annual_plan',
            'priority_level': 'high',
            'assignment_mode': 'region_manager_selects',
            'regions': ['الرياض', 'مكة المكرمة', 'عسير']
        },
        {
            'reference_no': 'IA-2026-002',
            'title': 'جولة تفتيشية على الأمانات النقدية والعينية',
            'template': t2,
            'mission_classification': 'quarterly_plan',
            'priority_level': 'critical',
            'assignment_mode': 'central_defined',
            'regions': ['المنطقة الشرقية', 'القصيم', 'المدينة المنورة']
        },
    ]

    for spec in mission_specs:
        mission = Mission(
            reference_no=spec['reference_no'],
            title=spec['title'],
            template=spec['template'],
            mission_classification=spec['mission_classification'],
            priority_level=spec['priority_level'],
            assignment_mode=spec['assignment_mode'],
            planned_date=date.today() + timedelta(days=7),
            due_date=date.today() + timedelta(days=21),
            task_instructions='تنفيذ المهمة وفق النموذج المعتمد ورفع الملاحظات ومعالجة التلافي حسب الصلاحية.',
            status='in_progress',
            created_by=central_admin.id,
        )
        db.session.add(mission)
        db.session.flush()

        add_log(central_admin.id, 'create_mission', 'mission', mission.id, f'إنشاء المهمة {mission.reference_no}')

        for region_name in spec['regions']:
            mission_region = MissionRegion(
                mission=mission,
                region=regions[region_name],
                status='assigned',
                allow_region_to_select_prisons=(spec['assignment_mode'] == 'region_manager_selects'),
                region_notes=f'نطاق المنطقة: {region_name}'
            )
            db.session.add(mission_region)
            db.session.flush()

            add_log(region_managers[region_name].id, 'create_mission_region', 'mission_region', mission_region.id, f'إضافة منطقة {region_name} إلى المهمة')

            region_prisons = regions[region_name].prisons[:2]
            for idx, prison in enumerate(region_prisons, start=1):
                prison_report = MissionPrisonReport(
                    mission_region=mission_region,
                    prison=prison,
                    status='assigned' if spec['assignment_mode'] != 'region_manager_selects' else 'in_progress',
                    visit_date=date.today() - timedelta(days=idx),
                    visit_day_name='الأحد',
                    visit_start_time='09:00',
                    visit_end_time='11:00',
                    visit_type='مجدولة',
                    visited_entity=prison.name,
                    report_summary=f'ملخص أولي لزيارة {prison.name}',
                    recommendations='استمرار المتابعة وتعزيز الرقابة',
                    submitted_at=None,
                )
                db.session.add(prison_report)
                db.session.flush()

                assigned_users = executors[region_name][:1]
                if spec['assignment_mode'] == 'central_defined':
                    assigned_users = [central_operator]

                prison_report.assignees = assigned_users

                template = mission.template
                score_cycle = ['ممتاز', 'جيد جدًا', 'مقبول', 'جيد جدًا', 'سيئ']
                i = 0
                for section in template.sections:
                    for criterion in section.criteria:
                        label = score_cycle[i % len(score_cycle)]
                        db.session.add(
                            MissionResponse(
                                mission_prison_report=prison_report,
                                criterion=criterion,
                                score_label=label,
                                score_value=SCORE_LABELS[label]
                            )
                        )
                        i += 1

                db.session.flush()
                prison_report.refresh_score()

                obs1 = Observation(
                    mission_prison_report=prison_report,
                    observation_type='criterion',
                    criterion_id=template.sections[1].criteria[0].id if template.sections and template.sections[1].criteria else None,
                    title=f'قصور في الجاهزية التشغيلية - {prison.name}',
                    description='لوحظ وجود تأخر في معالجة متطلبات الجاهزية التشغيلية ووجود عناصر بحاجة إلى استكمال.',
                    category='تشغيلي',
                    department=departments['إدارة السلامة'],
                    severity='عالية',
                    priority='عاجلة',
                    sla_option='7bd',
                    due_date=date.today() + timedelta(days=7),
                    status='under_treatment',
                    remediation_recommendation='استكمال النواقص ورفع ما يثبت المعالجة خلال المدة المحددة',
                    escalated=False
                )
                db.session.add(obs1)
                db.session.flush()
                add_log(assigned_users[0].id, 'add_observation', 'observation', obs1.id, f'إضافة ملاحظة على {prison.name}')

                obs2 = Observation(
                    mission_prison_report=prison_report,
                    observation_type='other',
                    title=f'ضعف في التوثيق - {prison.name}',
                    description='ظهرت ملاحظة إضافية تتعلق بعدم اكتمال بعض سجلات التوثيق الدورية.',
                    category='توثيق',
                    department=departments['إدارة تقنية المعلومات'],
                    severity='متوسطة',
                    priority='مهمة',
                    sla_option='14bd',
                    due_date=date.today() + timedelta(days=14),
                    status='new',
                    remediation_recommendation='استكمال السجلات وتوحيد آلية التوثيق'
                )
                db.session.add(obs2)
                db.session.flush()
                add_log(assigned_users[0].id, 'add_observation', 'observation', obs2.id, f'إضافة ملاحظة إضافية على {prison.name}')

                add_log(assigned_users[0].id, 'save_execution', 'mission_prison_report', prison_report.id, f'تحديث تنفيذ السجن {prison.name}')

        db.session.flush()

    db.session.commit()