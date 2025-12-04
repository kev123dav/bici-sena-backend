from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import psycopg2
from urllib.parse import urlparse
import bcrypt
import qrcode
from io import BytesIO
import base64

# Para pruebas locales con MySQL (opcional)
try:
    import mysql.connector
except ImportError:
    mysql = None

app = FastAPI(title="BiciSENA - Backend Global")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== CONEXIÓN A BD ====================
def get_db():
    if os.getenv("DATABASE_URL"):  # Render + Supabase
        url = urlparse(os.getenv("postgresql://postgres:Vy%hpyuD?*Gt3qx@db.saqqvvsowzjctxtqdiyip.supabase.co:5432/postgres"))
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port or 5432
        )
        conn.autocommit = True
        return conn
    else:  # Local MySQL
        if not mysql:
            raise Exception("Instala mysql-connector-python para pruebas locales")
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="Sena2025!F3QL",
            database="bicisena"
        )

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
        raise HTTPException617, "Cédula ya registrada"

    hashed = bcrypt.hashpw(contrasena.encode(), bcrypt.gensalt()).decode()
    foto_bici_b = await foto_bici.read()
    foto_usuario_b = await foto_usuario.read()

    cursor.execute("""
        INSERT INTO usuarios 
        (nombre, cedula, telefono, correo, contrasena, codigo, foto_bici_blob, foto_usuario_blob)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (nombre, cedula, telefono, correo, hashed, codigo, foto_bici_b, foto_usuario_b))

    db.close()
    return {"mensaje": "¡Registrado con éxito!"}

# ==================== LOGIN + QR ====================
@app.post("/api/usuario/login")
def login(data: Login):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE cedula = %s", (data.cedula,))
    user = cursor.fetchone()
    db.close()

    if user and bcrypt.checkpw(data.contrasena.encode(), user["contrasena"].encode()):
        qr = qrcode.make(user["codigo"])
        buffer = BytesIO()
        qr.save(buffer, format="PNG")
        qr_b64 = base64.b64encode(buffer.getvalue()).decode()

        return {
            "nombre": user["nombre"],
            "cedula": user["cedula"],
            "codigo": user["codigo"],
            "qr_blob": qr_b64,
            "foto_bici_blob": base64.b64encode(user["foto_bici_blob"]).decode() if user["foto_bici_blob"] else None,
            "foto_usuario_blob": base64.b64encode(user["foto_usuario_blob"]).decode() if user["foto_usuario_blob"] else None
        }
    raise HTTPException(401, "Credenciales inválidas")

# ==================== ESCANEAR QR (VIGILANTE) ====================
@app.get("/api/usuario/qr/{codigo}")
def escanear_qr(codigo: str):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE codigo = %s", (codigo,))
    user = cursor.fetchone()
    db.close()

    if not user:
        raise HTTPException(404, "Usuario no encontrado")

    return {
        "nombre": user["nombre"],
        "cedula": user["cedula"],
        "telefono": user["telefono"],
        "codigo": user["codigo"],
        "foto_bici_blob": base64.b64encode(user["foto_bici_blob"]).decode(),
        "foto_usuario_blob": base64.b64encode(user["foto_usuario_blob"]).decode(),
    }

# ==================== REGISTRAR ENTRADA/SALIDA ====================
@app.post("/api/registro/{codigo}/{accion}")
def registrar_movimiento(codigo: str, accion: str):
    if accion not in ["Entrada", "Salida"]:
        raise HTTPException(400, "Acción inválida")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id FROM usuarios WHERE codigo = %s", (codigo,))
    usuario = cursor.fetchone()

    if not usuario:
        db.close()
        raise HTTPException(404, "Usuario no encontrado")

    cursor.execute("INSERT INTO registros (usuario_id, accion) VALUES (%s, %s)", (usuario["id"], accion))
    db.close()
    return {"mensaje": f"¡{accion} registrada!"}

@app.get("/health")
def health():
    return {"status": "ok", "backend": "BiciSENA Global con Supabase"}

@app.get("/")
def root():
    return {"message": "BiciSENA API - 100% funcional"}

