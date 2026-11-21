"""Самостоятельный PDF-отчёт из той же личной аналитики, что показана в кабинете."""
import io
from pathlib import Path
from xml.sax.saxutils import escape
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle
from .analytics import StudyPeriodForm, period_values, study_report

FONT_DIR = Path(__file__).parent/"fonts"
pdfmetrics.registerFont(TTFont("StudyRegular", str(FONT_DIR/"DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("StudyBold", str(FONT_DIR/"DejaVuSans-Bold.ttf")))


def build_study_pdf(user, report):
    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, leftMargin=44, rightMargin=44, topMargin=44, bottomMargin=48,
        title="Отчёт об учебном времени", author="Такт - Очкина София Леонидовна")
    styles = {"body": ParagraphStyle("body", fontName="StudyRegular", fontSize=9, leading=13, spaceAfter=7),
        "title": ParagraphStyle("title", fontName="StudyBold", fontSize=21, leading=26, spaceAfter=16),
        "heading": ParagraphStyle("heading", fontName="StudyBold", fontSize=12, leading=16, spaceBefore=15, spaceAfter=9),
        "header": ParagraphStyle("header", fontName="StudyBold", fontSize=9, leading=12, textColor=colors.white)}
    def paragraph(text, style="body"):
        return Paragraph(escape(str(text)), styles[style])
    content = [paragraph("Отчёт об учебном времени", "title"),
        paragraph(f"Пользователь: {user.get_username()}"),
        paragraph(f"Период: {report['start']:%d.%m.%Y} - {report['end']:%d.%m.%Y}"),
        paragraph(f"Сформирован: {timezone.localtime():%d.%m.%Y %H:%M}"),
        paragraph("Показатели периода", "heading"),
        paragraph(f"План по дедлайнам: {report['planned']} мин. Фактические записи: {report['actual']} мин."),
        paragraph(f"Завершено задач с дедлайном в периоде: {report['completed_count']} из {report['task_count']}. Остались просроченными: {report['overdue_count']}."),
        paragraph("Распределение по дням", "heading")]
    rows = [[paragraph(title, "header") for title in ["Дата", "План по дедлайнам, мин", "Записано, мин"]]]
    rows += [[paragraph(day["date"].strftime("%d.%m.%Y")), paragraph(day["planned"]), paragraph(day["actual"])] for day in report["days"]]
    table = LongTable(rows, colWidths=[document.width*.25, document.width*.4, document.width*.35], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#176b5a")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f6f4")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    content += [table, paragraph("Дисциплины и точность оценки", "heading")]
    for subject in report["subjects"]:
        content.append(paragraph(f"{subject['task__subject__name'] or 'Без дисциплины'}: {subject['minutes']} мин."))
    if not report["subjects"]:
        content.append(paragraph("Записей времени в выбранном периоде нет."))
    if report["estimate_count"]:
        content.append(paragraph(f"Средняя абсолютная ошибка плана: {report['mae']:.1f} мин. Завершённых задач с записями: {report['estimate_count']}."))
    else:
        content.append(paragraph("Для оценки точности нет завершённых задач с записями."))
    content += [paragraph("Как читать результат", "heading"),
        paragraph("План относится к дедлайнам, факт - к дням работы. Для ошибки оценки используется всё записанное время завершённых задач с дедлайнами в периоде. Неполный учёт влияет на показатель. Отчёт не доказывает влияние приложения на успеваемость.")]
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("StudyRegular", 7.5)
        canvas.setFillColor(colors.HexColor("#52675f"))
        canvas.drawString(doc.leftMargin, 25, "Такт - Очкина София Леонидовна")
        canvas.drawRightString(A4[0]-doc.rightMargin, 25, f"Страница {doc.page}")
        canvas.restoreState()
    document.build(content, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


@login_required
def study_pdf(request):
    form = StudyPeriodForm(period_values(request))
    if not form.is_valid():
        return HttpResponseBadRequest(form.errors.as_text(), content_type="text/plain; charset=utf-8")
    response = HttpResponse(build_study_pdf(request.user, study_report(request.user, **form.cleaned_data)), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="study-report.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response
