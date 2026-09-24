from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import hashlib
import secrets
import json
import os

app = FastAPI()

# --- CẤU HÌNH CORS (Khắc phục lỗi Failed to fetch khi dùng HTML test) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép mọi nguồn (bao gồm file HTML local)
    allow_credentials=True,
    allow_methods=["*"],  # Cho phép mọi phương thức (GET, POST...)
    allow_headers=["*"],  # Cho phép mọi header (bao gồm x-admin-token)
)

# Mật khẩu quản trị và file lưu trữ
ADMIN_TOKEN = "TienLe_AI_SuperSecretToken123"
DB_FILE = "exam_data.json"

# --- CÁC HÀM XỬ LÝ LƯU TRỮ ---
def load_data():
    """Đọc dữ liệu cấu hình kỳ thi từ file JSON"""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(data):
    """Ghi đè dữ liệu mới vào file JSON"""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

class ExamConfig(BaseModel):
    exam_id: str
    bek: str
    form_url: str

# ---------------------------------------------------------
# API 1: Dành cho Admin (Cập nhật Link Form VÀ mã Hash)
# ---------------------------------------------------------
@app.post("/api/update-config")
async def update_config(config: ExamConfig, x_admin_token: str = Header(None)):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Sai mật khẩu Admin!")
    
    # Đọc dữ liệu cũ
    db = load_data()
    
    # Cập nhật hoặc tạo mới thông tin kỳ thi
    db[config.exam_id] = {
        "bek": config.bek,
        "form_url": config.form_url
    }
    
    # Lưu vật lý xuống ổ cứng
    save_data(db)
    
    return {"status": "success", "message": f"Đã lưu cấu hình kỳ thi '{config.exam_id}' vào {DB_FILE}"}

# ---------------------------------------------------------
# API 2: Dành cho SEB (Cổng vào của học sinh)
# ---------------------------------------------------------
@app.get("/go/{exam_id}")
async def seb_gateway(exam_id: str, request: Request):
    db = load_data()
    
    if exam_id not in db:
        return {"error": "Kỳ thi không tồn tại hoặc chưa được mở."}
        
    config = db[exam_id]
    target_form_url = config["form_url"]
    expected_bek = config["bek"]

    # Xử lý URL: Render dùng proxy nên nhận http, nhưng SEB tính hash bằng https.
    # Cấu trúc if này giúp bạn test local (cổng 5000) không bị sai hash, lên mây vẫn chuẩn.
    current_url = str(request.url)
    if "localhost" not in current_url and "127.0.0.1" not in current_url:
        current_url = current_url.replace("http://", "https://")
        
    seb_hash = request.headers.get("x-safeexambrowser-requesthash")
    
    if not seb_hash:
        return {"error": "Truy cập bị từ chối. Vui lòng mở bằng file cấu hình SEB chuẩn."}
        
    # Tính toán Hash: SHA256(URL hiện tại + BEK)
    hash_input = current_url + expected_bek
    expected_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
    
    # So sánh mã Hash an toàn (tránh Timing Attack)
    if secrets.compare_digest(seb_hash.lower(), expected_hash.lower()):
        # Nếu khớp, bẻ lái sang Google Form
        return RedirectResponse(url=target_form_url, status_code=302)
    else:
        # Nếu sai (Mã nguồn bị sửa, config bị đổi)
        return {"error": "Phát hiện phần mềm bị chỉnh sửa! Mã kiểm tra không khớp."}