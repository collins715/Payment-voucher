# Electronic Payment Voucher

A one-file Streamlit app: a Project Manager opens a link, fills in the voucher,
signs on screen, and downloads a formatted PDF. Every generated voucher is
also logged to `voucher_log.csv` for an audit trail.

## Before you deploy

1. Replace `logo.png` with your actual company logo (same filename, any
   reasonable size — it's auto-scaled).
2. Open `app.py` and edit the three lines near the top:
   ```python
   COMPANY_NAME = "Your Company Ltd"
   COMPANY_ADDRESS = "P.O. Box 00000-00100, Nairobi, Kenya"
   CURRENCY = "KES"
   ```

## Run it locally (to test)

```bash
pip install -r requirements.txt
streamlit run app.py
```

This opens in your browser at `http://localhost:8501`.

## Deploy so the Project Manager can use it (no install needed)

**Recommended: Streamlit Community Cloud (free, ~2 minutes)**

1. Push this folder to a GitHub repo (can be private).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub.
3. Click "New app", pick the repo and `app.py` as the entry point, click Deploy.
4. You get a permanent URL (e.g. `https://yourcompany-voucher.streamlit.app`)
   to send to the Project Manager. No install, works on any device with a browser.

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
| `logo.png`         | Company logo shown on-screen and in the PDF header    |
| `requirements.txt` | Python dependencies                                    |
| `voucher_log.csv`  | Auto-created audit log of every voucher generated     |

## Notes on the design

- **No database** — deliberately kept simple. `voucher_log.csv` is enough
  audit trail for a single PM's use. If more than one person will issue
  vouchers concurrently, swap the CSV for a small SQLite file (a few lines
  of change) so voucher numbers don't collide.
- **Signature is drawn, not typed** — captured on an HTML canvas and
  embedded into the PDF as an image.
- **Voucher numbering** is sequential per day (`PV-YYYYMMDD-001`, `-002`, ...),
  derived from the log file, so no separate counter/database is needed.
