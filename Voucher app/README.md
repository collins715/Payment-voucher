# JV Payment Voucher — BTN / Tech 7 / Exhenb

A one-file Streamlit app: fill in the voucher, sign it three times on screen
(Prepared / Approved / Received), and download a PDF that carries the JV
letterhead. Every generated voucher is also logged to `voucher_log.csv` for
an audit trail.

## What changed from the paper sample, and why

| Sample field    | This app                          | Why |
|------------------|------------------------------------|-----|
| Sum of Rupees    | **Amount (KES)**                   | The sample is a generic stock template; the JV operates in Kenya. |
| In Words (typed) | **In Words (auto-generated)**      | Removed as a typed field — it's generated from the amount so the figure and the words can never disagree. |
| Prepared By / Received By | **Prepared By / Approved By / Received By** | Added an independent "Approved By" signature. A three-partner JV moving money needs a check between the person who writes the voucher and the person who collects payment. |
| — | **Entity / Cost Centre** (BTN / Tech 7 / Exhenb / Joint Account) | Three partners share this JV — every voucher should say whose budget it's charged to, or month-end reconciliation is guesswork. |
| — | **Project / Site** | The JV will run more than one contract at a time; this keeps "On Account Of" from doing two jobs. |
| — | **Payment Details** (bank/paybill/till, optional) | A voucher that authorises payment should say where the money goes. Optional so it doesn't block cash/petty-cash use. |

The PDF header uses the full JV letterhead (all three logos + the JV name),
and the voucher body is boxed to match the look of the paper sample.

## Before you deploy

`letterhead.png` is already the JV letterhead you supplied — no edit needed
unless the artwork changes. If you want to adjust currency or the entity
list, edit the top of `app.py`:

```python
CURRENCY = "KES"
ENTITY_OPTIONS = [
    "Joint Account (JV)",
    "Baran Telecom Networks (BTN)",
    "Tech 7 Automation Systems",
    "Exhenb Engineering Ltd",
]
```

## Run it locally (to test)

```bash
pip install -r requirements.txt
streamlit run app.py
```

This opens in your browser at `http://localhost:8501`.

## Deploy so the team can use it (no install needed)

**Recommended: Streamlit Community Cloud (free, ~2 minutes)**

1. Push this folder to a GitHub repo (can be private).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub.
3. Click "New app", pick the repo and `app.py` as the entry point, click Deploy.
4. You get a permanent URL to send to whoever issues vouchers. No install,
   works on any device with a browser.

**Alternative: run it on an office server / VM**

```bash
pip install -r requirements.txt
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```
Then share `http://<server-ip>:8501` on the office network. For a permanent
internal deployment, run it under a process manager (e.g. `systemd` or `pm2`)
so it restarts automatically.

## Files

| File               | Purpose                                              |
|--------------------|-------------------------------------------------------|
| `app.py`           | The whole application (form, PDF rendering, logic)   |
| `letterhead.png`   | JV letterhead shown on-screen and in the PDF header   |
| `requirements.txt` | Python dependencies                                    |
| `voucher_log.csv`  | Auto-created audit log of every voucher generated     |

## Notes on the design

- **No database** — deliberately kept simple. `voucher_log.csv` is enough
  audit trail for now. If more than one person will issue vouchers
  concurrently and voucher numbers start colliding, swap the CSV for a
  small SQLite file (a few lines of change).
- **Signatures are drawn, not typed** — captured on an HTML canvas and
  embedded into the PDF as images.
- **Received By signature is optional at generation time** — the payee
  often signs on collection of the payment/cheque, which can happen after
  the voucher PDF is first produced and printed. Prepared By and Approved
  By are required before a PDF can be generated at all.
- **Voucher numbering** is sequential per day (`PV-YYYYMMDD-001`, `-002`, ...),
  derived from the log file, so no separate counter/database is needed.
