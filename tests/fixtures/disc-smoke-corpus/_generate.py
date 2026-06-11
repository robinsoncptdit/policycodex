"""DISC-16: generate 19 synthetic AGPL-compatible policy PDFs.

Run this once to produce the committed corpus:
  python tests/fixtures/disc-smoke-corpus/_generate.py

PDF 00 is the retention policy (used by screen 6).
PDFs 01..17 are generic policies covering common diocesan topics.
PDF 18 is an INTENTIONALLY image-only PDF (no text layer) to exercise
the per-item failure path from spec §6.
"""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from PIL import Image, ImageDraw
import io

OUT = Path(__file__).parent

POLICIES = [
    ("00-retention-policy.pdf", "Document Retention Policy",
     "Records management lifecycle. Admin records retain 7 years. Operational records retain 3 years. "
     "Categories: HR (10 years), Financial (7 years), Legal (permanent), Operational (3 years)."),
    ("01-code-of-conduct.pdf", "Code of Conduct",
     "All employees and volunteers must adhere to the values of integrity, charity, and respect. "
     "Reports of misconduct are confidential and follow the diocesan reporting structure."),
    ("02-conflict-of-interest.pdf", "Conflict of Interest Policy",
     "Disclose all conflicts annually. Recuse from decisions where a personal financial or family interest exists. "
     "The Audit Committee reviews disclosures quarterly."),
    ("03-whistleblower.pdf", "Whistleblower Policy",
     "Good-faith reports of suspected violations are protected. Retaliation is prohibited. "
     "Reports may be made anonymously through the diocesan ethics line."),
    ("04-travel-expense.pdf", "Travel and Expense Reimbursement",
     "Pre-approval required for travel exceeding 200 miles. Submit expense reports within 30 days. "
     "Per diem rates follow current IRS guidelines."),
    ("05-records-retention.pdf", "Records Retention Schedule",
     "Schedule applies to physical and electronic records. Destruction requires Records Officer approval. "
     "Litigation hold suspends all destruction."),
    ("06-it-acceptable-use.pdf", "IT Acceptable Use",
     "Diocesan computing resources are for ministry-related work. Personal use is incidental. "
     "Monitor consent is implied by login."),
    ("07-social-media.pdf", "Social Media Policy",
     "Official accounts require communications office approval. Personal accounts must not represent the diocese. "
     "All public communication aligns with Catholic teaching."),
    ("08-gift-acceptance.pdf", "Gift Acceptance",
     "Cash gifts under $10,000 are accepted by the Pastor. Larger gifts require Finance Council review. "
     "In-kind gifts are valued at fair market."),
    ("09-harassment.pdf", "Harassment Prevention",
     "Zero tolerance for harassment of any kind. Annual training mandatory. "
     "Complaints investigated by HR within 30 days."),
    ("10-leave.pdf", "Leave Policy",
     "Vacation: 15 days first year, accruing. Sick: 10 days. Sabbatical eligibility at year 7. "
     "Bereavement: 5 days for immediate family."),
    ("11-classified-handling.pdf", "Sensitive Document Handling",
     "Personnel files, donor records, and minor-protection investigations require lockbox storage. "
     "Electronic access logged. Annual access audit."),
    ("12-volunteer-screening.pdf", "Volunteer Screening",
     "Background check required for any role with minor contact. VIRTUS training before placement. "
     "Reverification every 5 years."),
    ("13-financial-controls.pdf", "Financial Controls",
     "Dual signature on checks over $5,000. Monthly bank reconciliation. "
     "Annual external audit. Quarterly variance reports."),
    ("14-data-protection.pdf", "Data Protection",
     "Donor data encrypted at rest and in transit. PII access logged. "
     "Annual security training mandatory. Breach notification per state law."),
    ("15-vendor-management.pdf", "Vendor Management",
     "Vendors over $10,000/year require contract. Insurance certificates current. "
     "Sole-source justification documented."),
    ("16-emergency-preparedness.pdf", "Emergency Preparedness",
     "Each parish maintains evacuation plan. Annual drills. "
     "Off-site backup of critical records monthly."),
    ("17-mass-stipend.pdf", "Mass Stipend Policy",
     "Stipends recorded and applied per Canon Law. Excess stipends transferred to mission fund. "
     "Records retained 10 years."),
]


def make_text_pdf(filename: str, title: str, body: str) -> None:
    """Plain text-bearing PDF — pypdf can extract its content cleanly."""
    c = canvas.Canvas(str(OUT / filename), pagesize=LETTER)
    width, height = LETTER
    c.setFont("Helvetica-Bold", 18)
    c.drawString(1 * inch, height - 1.5 * inch, title)
    c.setFont("Helvetica", 12)
    text = c.beginText(1 * inch, height - 2.5 * inch)
    text.setLeading(16)
    for line in body.split(". "):
        line = line.strip()
        if line:
            text.textLine(line + ".")
    c.drawText(text)
    c.showPage()
    c.save()


def make_image_only_pdf(filename: str, title: str) -> None:
    """Rasterized PDF — no text layer. pypdf extracts empty string."""
    img = Image.new("RGB", (612, 792), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((72, 100), title, fill="black")
    draw.text((72, 140), "This page is intentionally image-only.", fill="black")
    c = canvas.Canvas(str(OUT / filename), pagesize=LETTER)
    width, height = LETTER
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(buf), 0, 0, width=width, height=height)
    c.showPage()
    c.save()


if __name__ == "__main__":
    for filename, title, body in POLICIES:
        make_text_pdf(filename, title, body)
    make_image_only_pdf("18-scanned-compliance-memo.pdf", "Scanned Compliance Memo")
    print(f"Generated 19 PDFs in {OUT}")
