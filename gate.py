from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import hashlib
import secrets
import json
import os

app = FastAPI()

# --- CẤU HÌNH CORS CHO RENDER ---
# Đoạn này mở cổng để file admin.html dưới máy tính của bạn có thể gọi API lên Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ADMIN_TOKEN = "TienLe_AI_SuperSecretToken123"
DB_FILE = "exam_data.json"

# --- CÁC HÀM XỬ LÝ LƯU TRỮ ---
def load_data():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

class ExamConfig(BaseModel):
    exam_id: str
    bek: str
    form_url: str

# ---------------------------------------------------------
# API 1: API Cập nhật cấu hình kỳ thi
# ---------------------------------------------------------
@app.post("/api/update-config")
async def update_config(config: ExamConfig, x_admin_token: str = Header(None)):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Sai mật khẩu Admin")
    
    db = load_data()
    db[config.exam_id] = {
        "bek": config.bek,
        "form_url": config.form_url
    }
    save_data(db)
    return {"status": "success", "message": f"Đã lưu thành công kỳ thi: {config.exam_id}"}

# ---------------------------------------------------------
# API 2: Cổng gác an ninh cho phần mềm SEB
# ---------------------------------------------------------
@app.get("/go/{exam_id}")
async def seb_gateway(exam_id: str, request: Request):
    db = load_data()
    
    if exam_id not in db:
        return {"error": "Kỳ thi không tồn tại hoặc chưa được mở."}
        
    config = db[exam_id]
    target_form_url = config["form_url"]
    expected_bek = config["bek"]

    # Đảm bảo URL luôn là https để khớp với cách SEB tạo mã Hash
    current_url = str(request.url).replace("http://", "https://")
    seb_hash = request.headers.get("x-safeexambrowser-requesthash")
    
    if not seb_hash:
        return {"error": "Truy cập bị từ chối. Vui lòng mở bằng file cấu hình SEB đã được cung cấp."}
        
    # Tính toán Hash mong đợi: SHA256(URL + BEK)
    hash_input = current_url + expected_bek
    expected_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
    
    # So sánh Hash
    if secrets.compare_digest(seb_hash.lower(), expected_hash.lower()):
        # Hợp lệ: Bẻ lái sang Google Form
        return RedirectResponse(url=target_form_url, status_code=302)
    else:
        # Không hợp lệ (mã nguồn bị sửa): Báo lỗi
        return {"error": "Phát hiện phần mềm bị chỉnh sửa. Không thể truy cập đề thi!"}