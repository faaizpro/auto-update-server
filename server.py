import os
import hashlib
from flask import Flask, jsonify, request, send_from_directory, abort
from werkzeug.utils import secure_filename
import json
from datetime import datetime

app = Flask(__name__)

APK_DIR = "apk"
META_FILE = "meta.json"
UPLOAD_TOKEN = os.environ.get("UPLOAD_TOKEN", "my-secret-token")  # change in Secrets tab

os.makedirs(APK_DIR, exist_ok=True)

def read_meta():
    if not os.path.exists(META_FILE):
        meta = {"versionCode": 1, "filename": None, "sha256": None, "updatedAt": None}
        with open(META_FILE, "w") as f:
            json.dump(meta, f)
        return meta
    with open(META_FILE, "r") as f:
        return json.load(f)

def write_meta(meta):
    with open(META_FILE, "w") as f:
        json.dump(meta, f, indent=2)

def compute_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

@app.route("/update.json", methods=["GET"])
def update_json():
    meta = read_meta()
    if not meta.get("filename"):
        return jsonify({"versionCode": 0, "apkUrl": "", "sha256": ""})
    host = request.host_url.rstrip("/")
    apk_url = f"{host}/apk/{meta['filename']}"
    return jsonify({
        "versionCode": meta["versionCode"],
        "apkUrl": apk_url,
        "sha256": meta["sha256"]
    })

@app.route("/apk/<path:filename>", methods=["GET"])
def serve_apk(filename):
    filename = secure_filename(filename)
    filepath = os.path.join(APK_DIR, filename)
    if not os.path.exists(filepath):
        abort(404)
    return send_from_directory(APK_DIR, filename, as_attachment=True)

@app.route("/upload", methods=["POST"])
def upload_apk():
    # Check token (either ?token= or Authorization: Bearer)
    token = request.args.get("token")
    if not token:
        auth = request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(None, 1)[1]
    if token != UPLOAD_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    filename = secure_filename(f.filename)
    path = os.path.join(APK_DIR, filename)
    f.save(path)
    sha = compute_sha256(path)

    meta = read_meta()
    version = int(request.form.get("versionCode", meta["versionCode"] + 1))
    meta.update({
        "versionCode": version,
        "filename": filename,
        "sha256": sha,
        "updatedAt": datetime.utcnow().isoformat() + "Z"
    })
    write_meta(meta)

    host = request.host_url.rstrip("/")
    return jsonify({
        "ok": True,
        "versionCode": version,
        "apkUrl": f"{host}/apk/{filename}",
        "sha256": sha
    })

@app.route("/")
def index():
    meta = read_meta()
    return f"""
    <h3>APK Auto Update Server</h3>
    <p>versionCode: {meta['versionCode']}</p>
    <p>filename: {meta['filename']}</p>
    <p><a href="/update.json">View update.json</a></p>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
