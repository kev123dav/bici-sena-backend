from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import mysql.connector
import bcrypt
import qrcode
from io import BytesIO
import base64
import os

app = FastAPI(title="BiciSENA - Backend Oficial")

# CORS para que funcionen las dos apps (estudiante y vigilante)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== CONEXIÓN A BD LOCAL O EN LA NUBE (Render + PlanetScale) ======
def get_db():
    if os.getenv("DATABASE_URL"):  # En Render / nube
        from urllib.parse import urlparse
        url = urlparse(os.getenv("DATABASE_URL"))
        return mysql.connector.connect(
            host=url.hostname,
            port=url.port or 3306,
            user=url.username,
            password=url.password,
            database=url.path[1:],
            ssl_mode="REQUIRED",
            ssl_verify_cert=True
        )
    else:  # En tu PC (local)
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="Sena2025!F3QL",
            database="bicisena"
        )

# Modelo login
class Login(BaseModel):
    cedula: str
    contrasena: str

# ==================== REGISTRO ====================
@app.post("/api/usuario/registrar")
async def registrar(
    nombre: str = Form(...),
    cedula: str = Form(...),
    telefono: str = Form(...),
    correo: str = Form(...),
    contrasena: str = Form(...),
    codigo: str = Form(...),
    foto_bici: UploadFile = File(...),
    foto_usuario: UploadFile = File(...)
):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT cedula FROM usuarios WHERE cedula = %s", (cedula,))
    if cursor.fetchone():
        db.close()
        raise HTTPException(400, "Esta cédula ya está registrada")

    hashed = bcrypt.hashpw(contrasena.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    foto_bici_bytes = await foto_bici.read()
    foto_usuario_bytes = await foto_usuario.read()

    sql = """
    INSERT INTO usuarios 
    (nombre, cedula, telefono, correo, contrasena, codigo, qr_blob, foto_bici_blob, foto_usuario_blob) 
    VALUES (%s, %s, %s, %s, %s, %s, NULL, %s, %s)
    """
    cursor.execute(sql, (nombre, cedula, telefono, correo, hashed, codigo, foto_bici_bytes, foto_usuario_bytes))
    db.commit()
    db.close()
    return {"mensaje": "Usuario creado con éxito"}

# ==================== LOGIN (con QR generado) ====================
@app.post("/api/usuario/login")
def login(data: Login):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE cedula = %s", (data.cedula,))
    user = cursor.fetchone()
    db.close()

    if user and bcrypt.checkpw(data.contrasena.encode('utf-8'), user['contrasena'].encode('utf-8')):
        # Generar QR en base64
        qr = qrcode.make(user['codigo'])
        buffered = BytesIO()
        qr.save(buffered, format="PNG")
        qr_blob = base64.b64encode(buffered.getvalue()).decode()

        return {
            "nombre": user['nombre'],
            "cedula": user['cedula'],
            "telefono": user['telefono'],
            "correo": user['correo'],
            "codigo": user['codigo'],
            "qr_blob": qr_blob,
            "foto_bici_blob": base64.b64encode(user['foto_bici_blob']).decode() if user['foto_bici_blob'] else None,
            "foto_usuario_blob": base64.b64encode(user['foto_usuario_blob']).decode() if user['foto_usuario_blob'] else None
        }
    raise HTTPException(401, "Credenciales inválidas")

# ==================== VIGILANTE ESCANEA QR ====================
@app.get("/api/usuario/qr/{codigo}")
def vigilante_escanea(codigo: str):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE codigo = %s", (codigo,))
    user = cursor.fetchone()
    db.close()

    if not user:
        raise HTTPException(404, "Estudiante no encontrado")

    return {
        "nombre": user["nombre"],
        "cedula": user["cedula"],
        "telefono": user["telefono"],
        "correo": user["correo"],
        "codigo": user["codigo"],
        "foto_bici_blob": base64.b64encode(user["foto_bici_blob"]).decode(),
        "foto_usuario_blob": base64.b64encode(user["foto_usuario_blob"]).decode(),
    }

# ==================== SALUD ====================
@app.get("/health")
def health():
    return {"status": "ok", "message": "BiciSENA Backend 100% operativo - Global Ready"}

@app.get("/")
def root():
    return {"message": "BiciSENA API - Bienvenido crack"}