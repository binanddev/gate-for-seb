from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import hashlib
import secrets
import json
import os

app = FastAPI()

ADMIN_TOKEN = "TienLe_AI_SuperSecretToken123"
DB_FILE = "exam_data.json" # Nơi lưu trữ vật lý Link và Hash

# --- CÁC HÀM XỬ LÝ LƯU TRỮ ---
def load_data():
    """Đọc dữ liệu từ file JSON lên"""
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
# Bạn có thể tách làm 2 API riêng, nhưng gom chung sẽ tránh lỗi đồng bộ
# ---------------------------------------------------------
@app.post("/api/update-config")
async def update_config(config: ExamConfig, x_admin_token: str = Header(None)):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Sai mật khẩu Admin")
    
    # 1. Đọc file database cũ
    db = load_data()
    
    # 2. Cập nhật hoặc tạo mới thông tin kỳ thi
    db[config.exam_id] = {
        "bek": config.bek,
        "form_url": config.form_url
    }
    
    # 3. Lưu vật lý xuống ổ cứng
    save_data(db)
    
    return {"status": "success", "message": f"Đã lưu cấu hình vào {DB_FILE}"}

# ---------------------------------------------------------
# API 2: Dành cho SEB (Cổng vào của học sinh)
# ---------------------------------------------------------
@app.get("/go/{exam_id}")
async def seb_gateway(exam_id: str, request: Request):
    db = load_data() # Kéo dữ liệu từ file JSON ra để kiểm tra
    
    if exam_id not in db:
        return {"error": "Kỳ thi không tồn tại."}
        
    config = db[exam_id]
    target_form_url = config["form_url"]
    expected_bek = config["bek"]

    current_url = str(request.url).replace("http://", "https://")
    seb_hash = request.headers.get("x-safeexambrowser-requesthash")
    
    if not seb_hash:
        return {"error": "Truy cập bị từ chối."}
        
    hash_input = current_url + expected_bek
    expected_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
    
    if secrets.compare_digest(seb_hash.lower(), expected_hash.lower()):
        return RedirectResponse(url=target_form_url, status_code=302)
    else:
        return {"error": "Phát hiện phần mềm bị chỉnh sửa!"}