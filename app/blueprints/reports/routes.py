from io import BytesIO
from flask import Blueprint, send_file, render_template
from flask_login import login_required
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from ...models import Mission

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/')
@login_required
def index():
    missions = Mission.query.order_by(Mission.updated_at.desc()).all()
    return render_template('reports/index.html', missions=missions, title='التقارير المجمعة')

@reports_bp.route('/mission/<int:mission_id>/excel')
@login_required
def mission_excel(mission_id):
    mission = Mission.query.get_or_404(mission_id)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Mission'
    ws.append(['رقم المرجع', mission.reference_no])
    ws.append(['العنوان', mission.title])
    ws.append(['الحالة', mission.overall_status_label()])
    ws.append(['نوع الجدولة', mission.schedule_type])
    ws.append([])
    ws.append(['المنطقة', 'الحالة', 'السجون', 'الدرجة', 'مستوى المخاطر', 'عدد الملاحظات'])
    for mr in mission.regions:
        ws.append([
            mr.region.name,
            mr.status,
            '، '.join(p.name for p in mr.prisons),
            mr.score_percentage,
            mr.risk_level(),
            len(mr.observations),
        ])
    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return send_file(bio, as_attachment=True, download_name=f'{mission.reference_no}.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@reports_bp.route('/mission/<int:mission_id>/pdf')
@login_required
def mission_pdf(mission_id):
    mission = Mission.query.get_or_404(mission_id)
    bio = BytesIO()
    c = canvas.Canvas(bio, pagesize=A4)
    width, height = A4
    y = height - 50
    c.setFont('Helvetica-Bold', 14)
    c.drawString(50, y, f'Mission Report: {mission.reference_no}')
    y -= 22
    c.setFont('Helvetica', 11)
    c.drawString(50, y, mission.title)
    y -= 24
    c.drawString(50, y, f'Status: {mission.overall_status_label()}')
    y -= 28
    for mr in mission.regions:
        c.drawString(50, y, f"Region: {mr.region.name} | Score: {mr.score_percentage} | Risk: {mr.risk_level} | Obs: {len(mr.observations)}")
        y -= 18
        if y < 60:
            c.showPage(); y = height - 50
    c.save()
    bio.seek(0)
    return send_file(bio, as_attachment=True, download_name=f'{mission.reference_no}.pdf', mimetype='application/pdf')
