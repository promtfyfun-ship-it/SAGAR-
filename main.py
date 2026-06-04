import os
import sys
import shutil
import zipfile
import subprocess
import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='public')

# --- CORS SETTINGS ---
CORS(app, resources={r"/*": {"origins": "*"}})

app.secret_key = "super_secret_bothost_key_v1"
UPLOAD_FOLDER = "user_uploads"

# Secure Master Password
MASTER_PASSWORD = "s@go₹"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# রানিং প্রসেস স্টোরেজ: { 'pid': { 'process': Pobj, 'start_time': datetime } }
running_processes = {}

# --- SERVE FRONTEND ---
@app.route('/')
def serve_index():
    return send_from_directory('public', 'index.html')

# --- SMART FILE FINDER ---
def find_bot_file(folder_path):
    priority_files = ["main.py", "bot.py", "app.py", "index.py", "start.py", "run.py"]
    
    for f in priority_files:
        if os.path.exists(os.path.join(folder_path, f)):
            return os.path.join(folder_path, f), folder_path
            
    for root, dirs, files in os.walk(folder_path):
        if "__pycache__" in root or ".git" in root: continue
        for f in priority_files:
            if f in files: return os.path.join(root, f), root
        for f in files:
            if f.endswith(".py"): return os.path.join(root, f), root
                
    return None, None

# --- AUTO REQUIREMENTS INSTALLER ---
def install_requirements(folder_path):
    req_path = os.path.join(folder_path, "requirements.txt")
    
    if not os.path.exists(req_path):
        for root, dirs, files in os.walk(folder_path):
            if "requirements.txt" in files:
                req_path = os.path.join(root, "requirements.txt")
                break
    
    if os.path.exists(req_path):
        print(f"[*] Found requirements.txt at {req_path}. Installing...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_path], 
                         check=False, cwd=os.path.dirname(req_path))
        except Exception as e:
            print(f"[!] Error installing requirements: {e}")

# --- API ROUTES ---

@app.route('/api/status')
def home():
    return jsonify({
        "status": "Online",
        "message": "Bot Host BD Backend V1 is Active",
        "system": "Advanced Bot Runner"
    })

# ১. পাসওয়ার্ড অথেনটিকেশন
@app.route('/auth', methods=['POST'])
def auth():
    data = request.json
    password = data.get('password', '')
    if password == MASTER_PASSWORD:
        return jsonify({"success": True, "message": "Access Granted"})
    return jsonify({"success": False, "message": "Wrong Password!"}), 401

# ২. ফাইল আপলোড এবং ডিপ্লয়
@app.route('/upload', methods=['POST'])
def upload():
    if request.form.get('password') != MASTER_PASSWORD:
        return jsonify({"error": "Unauthorized"}), 403

    if 'file' not in request.files:
        return jsonify({"error": "No file sent"}), 400
        
    file = request.files['file']
    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in ['.zip', '.py']:
        return jsonify({"error": "Invalid file type. Only .zip or .py"}), 400
        
    app_name = os.path.splitext(filename)[0]
    app_dir = os.path.join(UPLOAD_FOLDER, app_name)
    
    # আগের ভার্সন ডিলিট
    if os.path.exists(app_dir):
        try: shutil.rmtree(app_dir)
        except: pass
    os.makedirs(app_dir, exist_ok=True)
    
    save_path = os.path.join(app_dir, filename)
    file.save(save_path)
    
    # ZIP হলে এক্সট্র্যাক্ট করা
    if ext == '.zip':
        try:
            with zipfile.ZipFile(save_path, 'r') as z:
                z.extractall(app_dir)
            os.remove(save_path)
            
            # লাইব্রেরি ইন্সটল ফাংশন কল
            install_requirements(app_dir)
            
        except Exception as e:
            return jsonify({"error": f"Zip failed: {str(e)}"}), 500
            
    return jsonify({"message": "Deploy Successful!"})

# ৩. অ্যাপ লিস্ট (Runtime Timer সহ)
@app.route('/my_apps', methods=['POST'])
def my_apps():
    # পাসওয়ার্ড ভেরিফিকেশন
    if request.json.get('password') != MASTER_PASSWORD:
        return jsonify({"error": "Unauthorized"}), 403

    apps = []
    if not os.path.exists(UPLOAD_FOLDER): return jsonify({"apps": []})
    
    for app_name in os.listdir(UPLOAD_FOLDER):
        full_path = os.path.join(UPLOAD_FOLDER, app_name)
        if os.path.isdir(full_path):
            pid = f"bot_{app_name}"
            
            is_running = False
            start_time = None
            
            # প্রসেস চেক এবং সময় বের করা
            if pid in running_processes:
                p_data = running_processes[pid]
                if p_data['process'].poll() is None:
                    is_running = True
                    start_time = p_data['start_time'].strftime("%Y-%m-%d %H:%M:%S")
                else:
                    del running_processes[pid]
            
            # লগ পড়া
            logs = "Waiting for logs..."
            log_file = os.path.join(full_path, "logs.txt")
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', errors='ignore') as f:
                        f.seek(0, 2)
                        size = f.tell()
                        f.seek(max(size - 4000, 0)) # শেষ ৪০০০ অক্ষর
                        logs = f.read()
                except: pass
                
            apps.append({
                "name": app_name, 
                "running": is_running, 
                "logs": logs, 
                "start_time": start_time
            })
            
    return jsonify({"apps": apps})

# ৪. একশন (Start/Stop/Delete)
@app.route('/action', methods=['POST'])
def action():
    data = request.json
    if data.get('password') != MASTER_PASSWORD:
        return jsonify({"error": "Unauthorized"}), 403

    act = data.get('action')
    app_name = data.get('app_name')
    
    pid = f"bot_{app_name}"
    app_dir = os.path.join(UPLOAD_FOLDER, app_name)
    
    if act == "start":
        if pid in running_processes and running_processes[pid]['process'].poll() is None:
            return jsonify({"message": "Already Running!"})
            
        script_path, script_dir = find_bot_file(app_dir)
        
        if not script_path:
            return jsonify({"error": "No Python file found!"}), 404
            
        log_file = open(os.path.join(app_dir, "logs.txt"), "a")
        
        try:
            my_env = os.environ.copy()
            
            proc = subprocess.Popen(
                [sys.executable, "-u", os.path.basename(script_path)],
                cwd=script_dir,
                stdout=log_file,
                stderr=log_file,
                text=True,
                env=my_env
            )
            
            running_processes[pid] = {
                'process': proc,
                'start_time': datetime.datetime.now()
            }
            return jsonify({"message": "Bot Started!"})
        except Exception as e:
            return jsonify({"error": f"Start failed: {str(e)}"}), 500

    elif act == "stop":
        if pid in running_processes:
            p = running_processes[pid]['process']
            p.terminate()
            try: p.wait(timeout=2)
            except: p.kill()
            del running_processes[pid]
            return jsonify({"message": "Stopped!"})
        return jsonify({"error": "Not running"})

    elif act == "delete":
        if pid in running_processes:
            try:
                running_processes[pid]['process'].kill()
                del running_processes[pid]
            except: pass
            
        if os.path.exists(app_dir):
            shutil.rmtree(app_dir)
            return jsonify({"message": "Deleted!"})
        return jsonify({"error": "Not found"})

    return jsonify({"error": "Bad Request"}), 400

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
