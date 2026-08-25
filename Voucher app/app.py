"""
Electronic Payment Voucher — Baran Telecom Networks / Tech 7 Automation
Systems / Exhenb Engineering Ltd JV
--------------------------------------------------------------------------
A single-file Streamlit app so someone on site or in the office can fill in
a payment voucher, sign it on screen, and download a formatted PDF that
carries the JV letterhead — no install, no training beyond "open the link".

DESIGN DECISIONS (opinionated, on purpose)
--------------------------------------------------------------------------
1. Fields follow the paper sample (PV No. / Dated / Paid To / On Account
   of / Prepared By / Received By), but three changes were made deliberately:

   - "Sum of Rupees" -> "Amount (KES)". The sample template is a generic
     stock template (Rupees), the JV operates in Kenya, so the currency is
     corrected to Kenyan Shillings rather than copied verbatim.

   - "In Words" is no longer a field you type into. It's the single most
     common error on a hand-filled voucher (words not matching the figure),
     so it's now generated automatically from the amount and simply shown
     on the PDF. One source of truth for the amount.

   - A third signature — "Approved By" — was added alongside "Prepared By"
     and "Received By". This is a three-company joint venture; a voucher
     that only needs a preparer and a receiver has no independent check
     before money moves. Prepared / Approved / Received is standard
     segregation of duties and costs nothing extra to collect on screen.

2. An "Entity / Cost Centre" field was added (BTN / Tech 7 / Exhenb /
   Joint Account) — with three partners sharing one JV, every voucher
   needs to say whose budget it sits against, or reconciliation between
   the partners becomes guesswork at month end. Defaults to "Joint
   Account (JV)".

3. "Project / Site" was added as a free-text field. A JV like this will
   be running more than one contract at a time; without it, "On Account
   of" ends up doing two jobs (what the money is for, and which job it
   belongs to).

4. "Payment Details" (bank / paybill / till) was added, optional. The
   sample doesn't ask for it, but a voucher that authorises payment
   without saying where the money goes isn't fully actionable — it's kept
   optional so it doesn't block cash/petty-cash use.

5. Signatures are still captured on an HTML canvas, not typed — closer to
   a wet signature, and it's what made the original app worth having over
   a plain form.

6. The PDF header uses the actual JV letterhead artwork (all three logos
   + the JV name), not a single company logo — this is a joint venture
   document, not a single company's.

7. Every submitted voucher is still appended to voucher_log.csv as an
   audit trail, now including the entity and project fields.
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
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from PIL import Image as PILImage

# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------
JV_NAME = "Baran Telecom Networks, Tech 7 Automation Systems and Exhenb Engineering Ltd JV"
LETTERHEAD_PATH = os.path.join(os.path.dirname(__file__), "letterhead.png")
LOG_PATH = os.path.join(os.path.dirname(__file__), "voucher_log.csv")
CURRENCY = "KES"

ENTITY_OPTIONS = [
    "Joint Account (JV)",
    "Baran Telecom Networks (BTN)",
    "Tech 7 Automation Systems",
    "Exhenb Engineering Ltd",
]

st.set_page_config(page_title="JV Payment Voucher", page_icon="🧾", layout="centered")


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def next_voucher_number() -> str:
    """Sequential voucher number: PV-YYYYMMDD-### based on today's log entries."""
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


def sig_flowable(png_bytes):
    """Return a signature image flowable, or a blank spacer if nothing was signed."""
    if png_bytes:
        return RLImage(io.BytesIO(png_bytes), width=42 * mm, height=16 * mm)
    return Spacer(1, 16 * mm)


def build_pdf(data: dict, signatures: dict) -> bytes:
    """Render the voucher + signatures into a one-page PDF, return as bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=14 * mm, bottomMargin=14 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title2", parent=styles["Heading1"], alignment=TA_CENTER,
                                  fontSize=15, spaceAfter=0)
    label_style = ParagraphStyle("Label", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.5)
    value_style = ParagraphStyle("Value", parent=styles["Normal"], fontSize=9.5, alignment=TA_LEFT)
    sig_name_style = ParagraphStyle("SigName", parent=styles["Normal"], alignment=TA_CENTER, fontSize=9)
    sig_caption_style = ParagraphStyle("SigCaption", parent=styles["Normal"], alignment=TA_CENTER,
                                        fontSize=7.5, textColor=colors.grey)

    story = []

    # --- Letterhead (outside the voucher box, full width) ---
    if os.path.exists(LETTERHEAD_PATH):
        with PILImage.open(LETTERHEAD_PATH) as im:
            w, h = im.size
        target_w = 174 * mm
        target_h = target_w * (h / w)
        story.append(RLImage(LETTERHEAD_PATH, width=target_w, height=target_h))
    story.append(Spacer(1, 3 * mm))
    story.append(Table([[""]], colWidths=[174 * mm], style=TableStyle(
        [("LINEBELOW", (0, 0), (-1, -1), 1.2, colors.black)])))
    story.append(Spacer(1, 5 * mm))

    # --- Voucher number / date row ---
    meta_table = Table(
        [[Paragraph(f"<b>PV No.</b> &nbsp; {data['voucher_no']}", label_style),
          Paragraph(f"<b>Dated:</b> &nbsp; {data['voucher_date']}", label_style)]],
        colWidths=[87 * mm, 87 * mm],
    )
    meta_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))

    # --- Everything below title, boxed like the paper sample ---
    inner = []
    inner.append(Paragraph("PAYMENT VOUCHER", title_style))
    inner.append(Spacer(1, 5 * mm))
    inner.append(meta_table)
    inner.append(Spacer(1, 5 * mm))

    field_rows = [
        ["Paid To", data["paid_to"]],
        ["Payment Details", data["payment_details"] or "-"],
        ["Entity / Cost Centre", data["entity"]],
        ["Project / Site", data["project_site"] or "-"],
        ["On Account Of", data["on_account_of"]],
        ["Payment Mode", data["payment_mode"]],
        ["Amount", f"{CURRENCY} {data['amount']:,.2f}"],
        ["In Words", amount_in_words(data["amount"])],
    ]
    fields_table = Table(
        [[Paragraph(r[0], label_style), Paragraph(r[1], value_style)] for r in field_rows],
        colWidths=[42 * mm, 132 * mm],
    )
    fields_table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    inner.append(fields_table)
    inner.append(Spacer(1, 10 * mm))

    # --- Signatures: Prepared / Approved / Received ---
    col_w = 58 * mm
    sig_table = Table(
        [
            ["Prepared By", "Approved By", "Received By"],
            [sig_flowable(signatures.get("prepared")),
             sig_flowable(signatures.get("approved")),
             sig_flowable(signatures.get("received"))],
            [data["prepared_by_name"] or "", data["approved_by_name"] or "", data["received_by_name"] or ""],
            ["Name & Signature", "Name & Signature", "Name & Signature"],
        ],
        colWidths=[col_w, col_w, col_w],
        rowHeights=[7 * mm, 18 * mm, 6 * mm, 5 * mm],
    )
    sig_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9.5),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 1), (-1, 1), "BOTTOM"),
        ("LINEABOVE", (0, 2), (0, 2), 0.75, colors.black),
        ("LINEABOVE", (1, 2), (1, 2), 0.75, colors.black),
        ("LINEABOVE", (2, 2), (2, 2), 0.75, colors.black),
        ("FONTSIZE", (0, 2), (-1, 2), 9),
        ("FONTSIZE", (0, 3), (-1, 3), 7),
        ("TEXTCOLOR", (0, 3), (-1, 3), colors.grey),
        ("TOPPADDING", (0, 2), (-1, 2), 3),
    ]))
    inner.append(sig_table)

    outer = Table([[inner]], colWidths=[174 * mm])
    outer.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.4, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(outer)

    doc.build(story)
    return buffer.getvalue()


def canvas_to_png_bytes(canvas_result):
    """Convert a signature canvas result to PNG bytes on white background, or None if blank."""
    if canvas_result.image_data is None or canvas_result.image_data[:, :, 3].sum() == 0:
        return None
    sig_img = PILImage.fromarray(canvas_result.image_data.astype("uint8"), "RGBA")
    white_bg = PILImage.new("RGBA", sig_img.size, "WHITE")
    white_bg.paste(sig_img, mask=sig_img)
    buf = io.BytesIO()
    white_bg.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------
# UI
# --------------------------------------------------------------------
if os.path.exists(LETTERHEAD_PATH):
    st.image(LETTERHEAD_PATH, use_container_width=True)
st.title("Payment Voucher")
st.caption("Fill in the details below, sign in each box, then download the PDF.")

if "voucher_no" not in st.session_state:
    st.session_state.voucher_no = next_voucher_number()

with st.form("voucher_form", clear_on_submit=False):
    col1, col2 = st.columns(2)
    with col1:
        voucher_no = st.text_input("PV No.", value=st.session_state.voucher_no)
        paid_to = st.text_input("Paid To *", help="Name of the person or supplier being paid")
        payment_details = st.text_input("Payment Details", help="Bank A/C, paybill or till number (optional)")
        entity = st.selectbox("Entity / Cost Centre *", ENTITY_OPTIONS)
        project_site = st.text_input("Project / Site")
    with col2:
        voucher_date = st.date_input("Dated", value=date.today())
        amount = st.number_input(f"Amount ({CURRENCY}) *", min_value=0.0, step=100.0, format="%.2f")
        payment_mode = st.selectbox("Payment Mode", ["Bank Transfer", "Cheque", "Cash", "Mobile Money"])

    on_account_of = st.text_area("On Account Of *", help="What the payment is for")

    st.markdown("---")
    st.markdown("**Signatures**")

    sig_col1, sig_col2, sig_col3 = st.columns(3)
    with sig_col1:
        st.markdown("Prepared By")
        prepared_by_name = st.text_input("Name", key="prepared_name", label_visibility="collapsed",
                                          placeholder="Name")
        prepared_canvas = st_canvas(
            fill_color="rgba(0,0,0,0)", stroke_width=3, stroke_color="#000000",
            background_color="#FFFFFF", height=110, width=190,
            drawing_mode="freedraw", key="sig_prepared",
        )
    with sig_col2:
        st.markdown("Approved By")
        approved_by_name = st.text_input("Name", key="approved_name", label_visibility="collapsed",
                                          placeholder="Name")
        approved_canvas = st_canvas(
            fill_color="rgba(0,0,0,0)", stroke_width=3, stroke_color="#000000",
            background_color="#FFFFFF", height=110, width=190,
            drawing_mode="freedraw", key="sig_approved",
        )
    with sig_col3:
        st.markdown("Received By")
        received_by_name = st.text_input("Name", key="received_name", label_visibility="collapsed",
                                          placeholder="Name")
        received_canvas = st_canvas(
            fill_color="rgba(0,0,0,0)", stroke_width=3, stroke_color="#000000",
            background_color="#FFFFFF", height=110, width=190,
            drawing_mode="freedraw", key="sig_received",
        )

    submitted = st.form_submit_button("Generate Voucher PDF", type="primary")

if submitted:
    errors = []
    if not paid_to:
        errors.append("Paid To is required.")
    if not amount or amount <= 0:
        errors.append("Amount must be greater than zero.")
    if not on_account_of:
        errors.append("On Account Of is required.")
    if not prepared_by_name:
        errors.append("Prepared By name is required.")
    if not approved_by_name:
        errors.append("Approved By name is required.")

    prepared_png = canvas_to_png_bytes(prepared_canvas)
    approved_png = canvas_to_png_bytes(approved_canvas)
    received_png = canvas_to_png_bytes(received_canvas)

    if prepared_png is None:
        errors.append("Prepared By signature is required.")
    if approved_png is None:
        errors.append("Approved By signature is required.")
    # Received By signature is optional at issue time — the payee often signs
    # on collection, which can happen after this PDF is first generated.

    if errors:
        for e in errors:
            st.error(e)
    else:
        data = dict(
            voucher_no=voucher_no,
            voucher_date=voucher_date.strftime("%Y-%m-%d"),
            paid_to=paid_to,
            payment_details=payment_details,
            entity=entity,
            project_site=project_site,
            on_account_of=on_account_of,
            amount=amount,
            payment_mode=payment_mode,
            prepared_by_name=prepared_by_name,
            approved_by_name=approved_by_name,
            received_by_name=received_by_name,
        )
        signatures = {"prepared": prepared_png, "approved": approved_png, "received": received_png}
        pdf_bytes = build_pdf(data, signatures)

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
        st.session_state.voucher_no = next_voucher_number()
