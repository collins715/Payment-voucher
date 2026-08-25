"""
Electronic Payment Voucher
---------------------------
A single-file Streamlit app so a Project Manager can fill in a payment
voucher, sign it on screen, and download a formatted PDF — no install,
no training needed beyond "open the link".

Design choices (opinionated, on purpose):
- Streamlit, not Flask/Tkinter: PM opens a browser link, nothing to
  install locally, and it deploys for free on Streamlit Community Cloud
  in about two minutes.
- Signature is captured on an HTML canvas (streamlit-drawable-canvas),
  not typed text — closer to an actual wet signature.
- PDF is built with ReportLab for exact control over layout (logo,
  table, signature placement) rather than converting HTML.
- Every submitted voucher is also appended to a local CSV log
  (voucher_log.csv) so there's an audit trail beyond the PDF itself.
  This is the one opinionated addition beyond "just make a PDF" —
  a PM signing off on payments needs a record, not just a download.
"""

import os
import io
import csv
from datetime import date, datetime

import streamlit as st
from streamlit_drawable_canvas import st_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from PIL import Image as PILImage

# --------------------------------------------------------------------
# Configuration — edit these for your organisation
# --------------------------------------------------------------------
COMPANY_NAME = "Your Company Ltd"
COMPANY_ADDRESS = "P.O. Box 00000-00100, Nairobi, Kenya"
LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo.png")
LOG_PATH = os.path.join(os.path.dirname(__file__), "voucher_log.csv")
CURRENCY = "KES"

st.set_page_config(page_title="Payment Voucher", page_icon="🧾", layout="centered")


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def next_voucher_number() -> str:
    """Simple sequential voucher number: PV-YYYYMMDD-### based on today's log entries."""
    today_str = date.today().strftime("%Y%m%d")
    count_today = 1
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, newline="") as f:
            rows = list(csv.DictReader(f))
            count_today += sum(1 for r in rows if r.get("voucher_no", "").startswith(f"PV-{today_str}"))
    return f"PV-{today_str}-{count_today:03d}"


def amount_in_words(amount: float) -> str:
    """Minimal number-to-words for KES amounts (whole shillings + cents)."""
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
             "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def two_digit(n):
        if n < 10:
            return ones[n]
        if n < 20:
            return teens[n - 10]
        return (tens[n // 10] + (" " + ones[n % 10] if n % 10 else "")).strip()

    def three_digit(n):
        if n >= 100:
            return (ones[n // 100] + " Hundred" + (" " + two_digit(n % 100) if n % 100 else "")).strip()
        return two_digit(n)

    whole = int(amount)
    cents = round((amount - whole) * 100)

    if whole == 0:
        words = "Zero"
    else:
        parts = []
        for value, label in [(1_000_000, "Million"), (1_000, "Thousand")]:
            chunk, whole = divmod(whole, value)
            if chunk:
                parts.append(f"{three_digit(chunk)} {label}")
        if whole:
            parts.append(three_digit(whole))
        words = " ".join(parts)

    result = f"{words} Shillings"
    if cents:
        result += f" and {two_digit(cents)} Cents"
    return result + " Only"


def build_pdf(data: dict, signature_png: bytes) -> bytes:
    """Render the voucher + signature into a one-page PDF, return as bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title2", parent=styles["Heading1"], alignment=TA_CENTER, fontSize=16)
    small_center = ParagraphStyle("SmallCenter", parent=styles["Normal"], alignment=TA_CENTER, fontSize=9)
    right_style = ParagraphStyle("Right", parent=styles["Normal"], alignment=TA_RIGHT)

    story = []

    # Header: logo + company name
    header_cells = []
    if os.path.exists(LOGO_PATH):
        header_cells.append(RLImage(LOGO_PATH, width=45 * mm, height=13.5 * mm))
    else:
        header_cells.append(Paragraph(COMPANY_NAME, styles["Heading2"]))
    header_table = Table(
        [[header_cells[0], Paragraph(f"<b>{data['voucher_no']}</b><br/>Date: {data['voucher_date']}", right_style)]],
        colWidths=[100 * mm, 65 * mm],
    )
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(header_table)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(COMPANY_ADDRESS, small_center))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("PAYMENT VOUCHER", title_style))
    story.append(Spacer(1, 6 * mm))

    # Voucher details table
    rows = [
        ["Payee", data["payee"]],
        ["Paid To A/C No.", data["account_no"] or "-"],
        ["Description / Purpose", data["description"]],
        ["Account Code", data["account_code"] or "-"],
        ["Amount", f"{CURRENCY} {data['amount']:,.2f}"],
        ["Amount in Words", amount_in_words(data["amount"])],
        ["Payment Mode", data["payment_mode"]],
    ]
    table = Table(rows, colWidths=[45 * mm, 120 * mm])
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.75, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 14 * mm))

    # Signature block
    sig_img = RLImage(io.BytesIO(signature_png), width=50 * mm, height=20 * mm)
    sig_table = Table(
        [
            ["Prepared By", "Approved / Signed By"],
            ["", sig_img],
            [data["prepared_by"], data["approver_name"]],
            [datetime.now().strftime("%Y-%m-%d %H:%M"), data["voucher_date"]],
        ],
        colWidths=[82.5 * mm, 82.5 * mm],
        rowHeights=[8 * mm, 22 * mm, 6 * mm, 6 * mm],
    )
    sig_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 1), (-1, 1), "BOTTOM"),
        ("LINEBELOW", (0, 2), (0, 2), 0.75, colors.black),
        ("LINEBELOW", (1, 2), (1, 2), 0.75, colors.black),
        ("FONTSIZE", (0, 3), (-1, 3), 8),
        ("TEXTCOLOR", (0, 3), (-1, 3), colors.grey),
    ]))
    story.append(sig_table)

    doc.build(story)
    return buffer.getvalue()


# --------------------------------------------------------------------
# UI
# --------------------------------------------------------------------
if os.path.exists(LOGO_PATH):
    st.image(LOGO_PATH, width=220)
st.title("Electronic Payment Voucher")
st.caption("Fill in the details below, sign in the box, then download the PDF.")

if "voucher_no" not in st.session_state:
    st.session_state.voucher_no = next_voucher_number()

with st.form("voucher_form", clear_on_submit=False):
    col1, col2 = st.columns(2)
    with col1:
        voucher_no = st.text_input("Voucher No.", value=st.session_state.voucher_no)
        payee = st.text_input("Payee Name *")
        account_no = st.text_input("Payee Account No.")
        amount = st.number_input(f"Amount ({CURRENCY}) *", min_value=0.0, step=100.0, format="%.2f")
    with col2:
        voucher_date = st.date_input("Date", value=date.today())
        account_code = st.text_input("Account / Cost Code")
        payment_mode = st.selectbox("Payment Mode", ["Bank Transfer", "Cheque", "Cash", "Mobile Money"])
        prepared_by = st.text_input("Prepared By *")

    description = st.text_area("Description / Purpose of Payment *")
    approver_name = st.text_input("Approver Name *", help="The person signing below")

    st.markdown("**Signature** — sign in the box below")
    canvas_result = st_canvas(
        fill_color="rgba(0,0,0,0)",
        stroke_width=3,
        stroke_color="#000000",
        background_color="#FFFFFF",
        height=150,
        width=400,
        drawing_mode="freedraw",
        key="signature_canvas",
    )

    submitted = st.form_submit_button("Generate Voucher PDF", type="primary")

if submitted:
    errors = []
    if not payee:
        errors.append("Payee Name is required.")
    if not amount or amount <= 0:
        errors.append("Amount must be greater than zero.")
    if not description:
        errors.append("Description / Purpose is required.")
    if not prepared_by:
        errors.append("Prepared By is required.")
    if not approver_name:
        errors.append("Approver Name is required.")
    if canvas_result.image_data is None or canvas_result.image_data[:, :, 3].sum() == 0:
        errors.append("Please sign in the signature box before generating the PDF.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        # Convert the signature canvas (RGBA numpy array) to PNG bytes
        sig_img = PILImage.fromarray(canvas_result.image_data.astype("uint8"), "RGBA")
        white_bg = PILImage.new("RGBA", sig_img.size, "WHITE")
        white_bg.paste(sig_img, mask=sig_img)
        sig_buf = io.BytesIO()
        white_bg.convert("RGB").save(sig_buf, format="PNG")

        data = dict(
            voucher_no=voucher_no,
            voucher_date=voucher_date.strftime("%Y-%m-%d"),
            payee=payee,
            account_no=account_no,
            description=description,
            account_code=account_code,
            amount=amount,
            payment_mode=payment_mode,
            prepared_by=prepared_by,
            approver_name=approver_name,
        )
        pdf_bytes = build_pdf(data, sig_buf.getvalue())

        # Append to audit log
        log_exists = os.path.exists(LOG_PATH)
        with open(LOG_PATH, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(data.keys()) + ["generated_at"])
            if not log_exists:
                writer.writeheader()
            writer.writerow({**data, "generated_at": datetime.now().isoformat(timespec="seconds")})

        st.success(f"Voucher {voucher_no} generated.")
        st.download_button(
            label="⬇ Download Voucher PDF",
            data=pdf_bytes,
            file_name=f"{voucher_no}.pdf",
            mime="application/pdf",
        )
        # reset voucher number for the next entry
        st.session_state.voucher_no = next_voucher_number()
