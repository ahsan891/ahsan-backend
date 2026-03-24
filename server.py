from flask import Flask, request, jsonify
from flask_cors import CORS
import urllib.request
import urllib.error
import json
import datetime
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
CORS(app)

# ─────────────────────────────────────────────
# CONFIG — update these if anything changes
# ─────────────────────────────────────────────
VAPI_API_KEY      = "6e86e577-27c2-4d0a-a4a6-f45270c260a8"
VAPI_PHONE_ID     = "f68ad6d5-b32c-4051-8f85-67e96d8d2a5a"   # Vapi +1 973 929 9737
VAPI_ASSISTANT_ID = "c1e9bac8-7843-4a1b-bee0-e0a2bd1b330e"   # AHSAN

# Google Sheets (optional — leave blank to skip logging)
GOOGLE_SHEET_ID   = ""   # Paste your Google Sheet ID here
GOOGLE_CREDS_FILE = "google_creds.json"  # Service account JSON file

# ─────────────────────────────────────────────
# GOOGLE SHEETS LOGGER
# ─────────────────────────────────────────────
def log_to_sheets(name, phone, program, call_id, status):
    """Log lead info to Google Sheets. Silently skips if not configured."""
    if not GOOGLE_SHEET_ID:
        return
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds  = Credentials.from_service_account_file(GOOGLE_CREDS_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        sheet  = client.open_by_key(GOOGLE_SHEET_ID).sheet1
        now    = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, name, phone, program, call_id, status])
        print(f"✅ Logged to Google Sheets: {name}")
    except Exception as e:
        print(f"⚠️  Google Sheets logging failed (non-critical): {e}")

# ─────────────────────────────────────────────
# CALL TRIGGER ENDPOINT
# ─────────────────────────────────────────────
@app.route("/call", methods=["POST"])
def trigger_call():
    data    = request.get_json()
    name    = data.get("name", "").strip()
    phone   = data.get("phone", "").strip()
    program = data.get("program", "UAE Golden Visa").strip()

    # Basic validation
    if not name or not phone:
        return jsonify({"error": "Name and phone are required"}), 400

    # Normalize phone: ensure it starts with +
    if not phone.startswith("+"):
        phone = "+" + phone

    print(f"\n📞 Incoming lead: {name} | {phone} | {program}")

    # Build Vapi payload
    payload = {
        "phoneNumberId": VAPI_PHONE_ID,
        "customer": {
            "number": phone,
            "name":   name
        },
        "assistantId": VAPI_ASSISTANT_ID,
        "assistantOverrides": {
            "variableValues": {
                "leadName": name,
                "program":  program
            }
        }
    }

    # Call Vapi API
    try:
        req = urllib.request.Request(
            "https://api.vapi.ai/call/phone",
            data    = json.dumps(payload).encode("utf-8"),
            headers = {
                "Authorization": f"Bearer {VAPI_API_KEY}",
                "Content-Type":  "application/json"
            },
            method  = "POST"
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            result  = json.loads(res.read().decode("utf-8"))
            call_id = result.get("id", "unknown")
            print(f"✅ Call triggered! ID: {call_id}")
            log_to_sheets(name, phone, program, call_id, "queued")
            return jsonify({"success": True, "callId": call_id})

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"❌ Vapi error {e.code}: {error_body}")
        log_to_sheets(name, phone, program, "N/A", f"error_{e.code}")
        return jsonify({"error": f"Vapi error {e.code}: {error_body}"}), 500

    except Exception as e:
        print(f"❌ Server error: {e}")
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "AHSAN backend running ✅"})

if __name__ == "__main__":
    print("🚀 AHSAN backend starting on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
