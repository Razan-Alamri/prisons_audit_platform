from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from ...permissions import roles_required
from ...extensions import db
from ...models import Template, TemplateSection, TemplateCriterion, AuditLog
from ...utils import log_action
from sqlalchemy import or_, and_

templates_admin_bp = Blueprint('templates_admin', __name__, url_prefix='/templates-admin')


def _normalize_weight(value):
    try:
        return round(float(value or 0), 2)
    except (ValueError, TypeError):
        return None


def _normalize_text(value):
    return ' '.join((value or '').strip().split())


@templates_admin_bp.route('/')
@login_required
@roles_required('central_admin', 'central_operator', 'central_director')
def index():
    q = Template.query.order_by(Template.created_at.desc())

    search = (request.args.get('search') or '').strip()
    status = (request.args.get('status') or '').strip()

    if search:
        q = q.filter(
            or_(
                Template.name.ilike(f'%{search}%'),
                Template.code.ilike(f'%{search}%')
            )
        )

    if status == 'active':
        q = q.filter(Template.is_active == True)
    elif status == 'inactive':
        q = q.filter(Template.is_active == False)

    templates = q.all()

    stats = {
        'total': len(templates),
        'active': sum(1 for t in templates if t.is_active),
        'inactive': sum(1 for t in templates if not t.is_active),
        'sections': sum(len(t.sections) for t in templates),
        'criteria': sum(sum(len(s.criteria) for s in t.sections) for t in templates),
    }

    return render_template(
        'templates_admin/index.html',
        templates=templates,
        stats=stats,
        filters={
            'search': search,
            'status': status,
        }
    )


@templates_admin_bp.route('/create', methods=['GET', 'POST'])
@login_required
@roles_required('central_admin', 'central_operator', 'central_director')
def create():
    if request.method == 'POST':
        name = _normalize_text(request.form.get('name'))
        code = _normalize_text(request.form.get('code'))
        description = _normalize_text(request.form.get('description'))

        if not name or not code:
            flash('اسم النموذج والكود حقول مطلوبة.', 'danger')
            return redirect(url_for('templates_admin.create'))

        exists = Template.query.filter(
            or_(Template.name == name, Template.code == code)
        ).first()
        if exists:
            flash('يوجد نموذج بنفس الاسم أو الكود.', 'danger')
            return redirect(url_for('templates_admin.create'))

        template = Template(
            name=name,
            code=code,
            description=description,
            is_active=True
        )
        db.session.add(template)
        db.session.commit()

        log_action(current_user.id, 'create_template', 'template', template.id, f'إنشاء نموذج جديد: {template.name}')
        db.session.commit()

        flash('تم إنشاء النموذج بنجاح.', 'success')
        return redirect(url_for('templates_admin.detail', template_id=template.id))

    return render_template('templates_admin/create.html')


@templates_admin_bp.route('/<int:template_id>', methods=['GET', 'POST'])
@login_required
@roles_required('central_admin', 'central_operator', 'central_director')
def detail(template_id):
    template = Template.query.get_or_404(template_id)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_template':
            name = _normalize_text(request.form.get('name'))
            code = _normalize_text(request.form.get('code'))
            description = _normalize_text(request.form.get('description'))

            if not name or not code:
                flash('اسم النموذج والكود حقول مطلوبة.', 'danger')
                return redirect(url_for('templates_admin.detail', template_id=template.id))

            duplicate = Template.query.filter(
                Template.id != template.id,
                or_(Template.name == name, Template.code == code)
            ).first()
            if duplicate:
                flash('يوجد نموذج آخر بنفس الاسم أو الكود.', 'danger')
                return redirect(url_for('templates_admin.detail', template_id=template.id))

            changed_fields = []

            if template.name != name:
                changed_fields.append(f'تعديل الاسم من "{template.name}" إلى "{name}"')
                template.name = name

            if template.code != code:
                changed_fields.append(f'تعديل الكود من "{template.code}" إلى "{code}"')
                template.code = code

            if (template.description or '') != description:
                changed_fields.append('تعديل الوصف')
                template.description = description

            if not changed_fields:
                flash('لا توجد تغييرات للحفظ.', 'info')
                return redirect(url_for('templates_admin.detail', template_id=template.id))

            db.session.commit()

            log_action(
                current_user.id,
                'update_template_info',
                'template',
                template.id,
                ' | '.join(changed_fields)
            )
            db.session.commit()

            flash('تم تحديث بيانات النموذج.', 'success')
            return redirect(url_for('templates_admin.detail', template_id=template.id))

        elif action == 'toggle_template':
            if not template.is_active and round(template.total_weight, 2) != 100.0:
                flash('لا يمكن تفعيل النموذج قبل أن يكون مجموع الأوزان = 100%.', 'danger')
                return redirect(url_for('templates_admin.detail', template_id=template.id))

            template.is_active = not template.is_active
            db.session.commit()

            log_action(
                current_user.id,
                'toggle_template',
                'template',
                template.id,
                f'تغيير حالة النموذج إلى {"مفعل" if template.is_active else "معطل"}'
            )
            db.session.commit()

            flash('تم تحديث حالة النموذج.', 'success')
            return redirect(url_for('templates_admin.detail', template_id=template.id))

        elif action == 'add_section':
            title = _normalize_text(request.form.get('title'))
            weight = _normalize_weight(request.form.get('weight_percentage'))

            if not title:
                flash('اسم الهدف مطلوب.', 'danger')
                return redirect(url_for('templates_admin.detail', template_id=template.id))
            if weight is None:
                flash('الوزن غير صحيح.', 'danger')
                return redirect(url_for('templates_admin.detail', template_id=template.id))

            duplicate_section = TemplateSection.query.filter(
                TemplateSection.template_id == template.id,
                TemplateSection.title == title
            ).first()
            if duplicate_section:
                flash('يوجد هدف بنفس الاسم داخل هذا النموذج.', 'danger')
                return redirect(url_for('templates_admin.detail', template_id=template.id))

            section = TemplateSection(
                template=template,
                title=title,
                weight_percentage=weight,
                sort_order=len(template.sections) + 1
            )
            db.session.add(section)
            db.session.commit()

            log_action(current_user.id, 'add_section', 'template_section', section.id, f'إضافة هدف: {section.title}')
            db.session.commit()

            if round(template.total_weight, 2) != 100.0:
                flash(f'تمت إضافة الهدف. مجموع الأوزان الحالي = {template.total_weight}% ويجب مراجعته لاحقًا.', 'warning')
            else:
                flash('تمت إضافة الهدف بنجاح.', 'success')

            return redirect(url_for('templates_admin.detail', template_id=template.id))

        elif action == 'edit_section_full':
            section = db.session.get(TemplateSection, int(request.form.get('section_id')))
            if not section or section.template_id != template.id:
                flash('الهدف غير موجود.', 'danger')
                return redirect(url_for('templates_admin.detail', template_id=template.id))

            title = _normalize_text(request.form.get('title'))
            weight = _normalize_weight(request.form.get('weight_percentage'))

            if not title:
                flash('اسم الهدف مطلوب.', 'danger')
                return redirect(url_for('templates_admin.detail', template_id=template.id))
            if weight is None:
                flash('الوزن غير صحيح.', 'danger')
                return redirect(url_for('templates_admin.detail', template_id=template.id))

            duplicate_section = TemplateSection.query.filter(
                TemplateSection.template_id == template.id,
                TemplateSection.id != section.id,
                TemplateSection.title == title
            ).first()
            if duplicate_section:
                flash('يوجد هدف آخر بنفس الاسم داخل هذا النموذج.', 'danger')
                return redirect(url_for('templates_admin.detail', template_id=template.id))

            changed = False
            section_changes = []

            if section.title != title:
                section_changes.append(f'تعديل اسم الهدف من "{section.title}" إلى "{title}"')
                section.title = title
                changed = True

            if float(section.weight_percentage or 0) != float(weight):
                section_changes.append(f'تعديل وزن الهدف من {section.weight_percentage}% إلى {weight}%')
                section.weight_percentage = weight
                changed = True

            criterion_ids = request.form.getlist('criterion_id')
            criterion_texts = request.form.getlist('criterion_text')
            criterion_delete_ids = set(request.form.getlist('delete_criterion_ids'))
            new_criteria = request.form.getlist('new_criteria')

            for cid, text in zip(criterion_ids, criterion_texts):
                criterion = db.session.get(TemplateCriterion, int(cid))
                if not criterion or criterion.section_id != section.id:
                    continue

                if str(criterion.id) in criterion_delete_ids:
                    criterion_id = criterion.id
                    db.session.delete(criterion)
                    db.session.flush()
                    log_action(
                        current_user.id,
                        'delete_criterion',
                        'template_criterion',
                        criterion_id,
                        f'حذف معيار من الهدف: {section.title}'
                    )
                    changed = True
                else:
                    new_text = _normalize_text(text)
                    if new_text and criterion.text != new_text:
                        old_text = criterion.text
                        criterion.text = new_text
                        db.session.flush()
                        log_action(
                            current_user.id,
                            'edit_criterion',
                            'template_criterion',
                            criterion.id,
                            f'تعديل معيار من "{old_text}" إلى "{new_text}"'
                        )
                        changed = True

            existing_texts = {
                _normalize_text(c.text)
                for c in section.criteria
                if c.id and str(c.id) not in criterion_delete_ids
            }

            added_new_texts = set()
            for txt in new_criteria:
                txt = _normalize_text(txt)
                if not txt:
                    continue

                if txt in existing_texts or txt in added_new_texts:
                    flash(f'يوجد معيار مكرر داخل الهدف: "{txt}"', 'danger')
                    return redirect(url_for('templates_admin.detail', template_id=template.id))

                new_criterion = TemplateCriterion(
                    section=section,
                    text=txt,
                    sort_order=len(section.criteria) + 1
                )
                db.session.add(new_criterion)
                db.session.flush()
                log_action(
                    current_user.id,
                    'add_criterion',
                    'template_criterion',
                    new_criterion.id,
                    f'إضافة معيار داخل الهدف: {section.title}'
                )
                added_new_texts.add(txt)
                changed = True

            if not changed:
                flash('لا توجد تغييرات للحفظ.', 'info')
                return redirect(url_for('templates_admin.detail', template_id=template.id))

            db.session.commit()

            log_action(
                current_user.id,
                'edit_section',
                'template_section',
                section.id,
                ' | '.join(section_changes) if section_changes else f'تحديث محتوى الهدف: {section.title}'
            )
            db.session.commit()

            if round(template.total_weight, 2) != 100.0:
                flash(f'تم حفظ التعديلات. مجموع الأوزان الحالي = {template.total_weight}% ويجب ضبطه إلى 100%.', 'warning')
            else:
                flash('تم حفظ تعديلات الهدف والمعايير بنجاح.', 'success')

            return redirect(url_for('templates_admin.detail', template_id=template.id))

        elif action == 'delete_section':
            section = db.session.get(TemplateSection, int(request.form.get('section_id')))
            if not section or section.template_id != template.id:
                flash('الهدف غير موجود.', 'danger')
                return redirect(url_for('templates_admin.detail', template_id=template.id))

            section_title = section.title
            section_id = section.id
            db.session.delete(section)
            db.session.commit()

            log_action(current_user.id, 'delete_section', 'template_section', section_id, f'حذف هدف: {section_title}')
            db.session.commit()

            if round(template.total_weight, 2) != 100.0:
                flash(f'تم حذف الهدف. مجموع الأوزان الحالي = {template.total_weight}% ويجب مراجعته.', 'warning')
            else:
                flash('تم حذف الهدف بنجاح.', 'warning')

            return redirect(url_for('templates_admin.detail', template_id=template.id))

        elif action == 'update_weights':
            new_weights = {}
            total = 0
            changed = False

            for section in template.sections:
                value = _normalize_weight(request.form.get(f'weight_{section.id}'))
                if value is None:
                    flash('يوجد وزن غير صحيح.', 'danger')
                    return redirect(url_for('templates_admin.detail', template_id=template.id))

                new_weights[section.id] = value
                total += value

                if float(section.weight_percentage or 0) != float(value):
                    changed = True

            total = round(total, 2)
            if total != 100.0:
                flash('يجب أن يكون مجموع الأوزان 100% قبل الحفظ النهائي.', 'danger')
                return redirect(url_for('templates_admin.detail', template_id=template.id))

            if not changed:
                flash('لا توجد تغييرات للحفظ.', 'info')
                return redirect(url_for('templates_admin.detail', template_id=template.id))

            for section in template.sections:
                section.weight_percentage = new_weights[section.id]

            db.session.commit()

            log_action(current_user.id, 'update_weights', 'template', template.id, 'تحديث أوزان الأهداف')
            db.session.commit()

            flash('تم تحديث الأوزان بنجاح.', 'success')
            return redirect(url_for('templates_admin.detail', template_id=template.id))

        else:
            flash('الإجراء غير معروف.', 'danger')
            return redirect(url_for('templates_admin.detail', template_id=template.id))

    section_ids = [s.id for s in template.sections]
    criterion_ids = [c.id for s in template.sections for c in s.criteria]

    entity_logs = (
        AuditLog.query
        .filter(
            or_(
                and_(AuditLog.entity_type == 'template', AuditLog.entity_id == template.id),
                and_(AuditLog.entity_type == 'template_section', AuditLog.entity_id.in_(section_ids if section_ids else [-1])),
                and_(AuditLog.entity_type == 'template_criterion', AuditLog.entity_id.in_(criterion_ids if criterion_ids else [-1]))
            )
        )
        .order_by(AuditLog.created_at.desc())
        .limit(20)
        .all()
    )

    return render_template('templates_admin/detail.html', template=template, entity_logs=entity_logs)


@templates_admin_bp.route('/<int:template_id>/history')
@login_required
@roles_required('central_admin', 'central_operator', 'central_director')
def history(template_id):
    template = Template.query.get_or_404(template_id)

    section_ids = [s.id for s in template.sections]
    criterion_ids = [c.id for s in template.sections for c in s.criteria]

    logs = (
        AuditLog.query
        .filter(
            or_(
                and_(AuditLog.entity_type == 'template', AuditLog.entity_id == template.id),
                and_(AuditLog.entity_type == 'template_section', AuditLog.entity_id.in_(section_ids if section_ids else [-1])),
                and_(AuditLog.entity_type == 'template_criterion', AuditLog.entity_id.in_(criterion_ids if criterion_ids else [-1]))
            )
        )
        .order_by(AuditLog.created_at.desc())
        .all()
    )

    return render_template('templates_admin/history.html', template=template, logs=logs)