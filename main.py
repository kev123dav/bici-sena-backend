from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import psycopg2
import bcrypt
import qrcode
from io import BytesIO
import base64

app = FastAPI(
    title="BiciSENA - Parqueadero Oficial SENA",
    description="Backend 100% funcional en la nube con Supabase",
    version="2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== CONEXIÓN SEGURA A SUPABASE (FUNCIONA EN RENDER) ====================
def get_db():
    try:
        conn = psycopg2.connect(
            os.environ["DATABASE_URL"],  # Render pone esta variable automáticamente
            sslmode="require"
        )
        conn.autocommit = True
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")

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
    cur = db.cursor()

    cur.execute("SELECT 1 FROM usuarios WHERE cedula = %s", (cedula,))
    if cur.fetchone():
        db.close()
        raise HTTPException(status_code=409, detail="Cédula ya registrada")

    hashed = bcrypt.hashpw(contrasena.encode(), bcrypt.gensalt())

    foto_bici_bytes = await foto_bici.read()
    foto_usuario_bytes = await foto_usuario.read()

    qr = qrcode.make(codigo)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    qr_bytes = buffer.getvalue()

    cur.execute("""
        INSERT INTO usuarios 
        (nombre, cedula, telefono, correo, contrasena, codigo, qr_blob, foto_bici_blob, foto_usuario_blob)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (nombre, cedula, telefono, correo, hashed, codigo, qr_bytes, foto_bici_bytes, foto_usuario_bytes))

    db.close()
    return {"mensaje": "¡Usuario registrado con éxito en la nube!"}

# ==================== LOGIN + QR ====================
@app.post("/api/usuario/login")
def login(data: Login):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT nombre, cedula, codigo, qr_blob, foto_bici_blob, foto_usuario_blob, contrasena FROM usuarios WHERE cedula = %s", (data.cedula,))
    row = cur.fetchone()
    db.close()

    if row and bcrypt.checkpw(data.contrasena.encode(), row[6].encode()):
        return {
            "nombre": row[0],
            "cedula": row[1],
            "codigo": row[2],
            "qr_blob": base64.b64encode(row[3]).decode() if row[3] else None,
            "foto_bici_blob": base64.b64encode(row[4]).decode() if row[4] else None,
            "foto_usuario_blob": base64.b64encode(row[5]).decode() if row[5] else None
        }
    raise HTTPException(status_code=401, detail="Cédula o contraseña incorrecta")

# ==================== ESCANEAR QR ====================
@app.get("/api/usuario/qr/{codigo}")
def escanear_qr(codigo: str):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT nombre, cedula, telefono, foto_bici_blob, foto_usuario_blob FROM usuarios WHERE codigo = %s", (codigo,))
    row = cur.fetchone()
    db.close()

    if not row:
        raise HTTPException(status_code=404, detail="Código no encontrado")

    return {
        "nombre": row[0],
        "cedula": row[1],
        "telefono": row[2],
        "codigo": codigo,
        "foto_bici_blob": base64.b64encode(row[3]).decode(),
        "foto_usuario_blob": base64.b64encode(row[4]).decode(),
    }

# ==================== REGISTRAR ENTRADA/SALIDA ====================
@app.post("/api/registro/{codigo}/{accion}")
def registrar_movimiento(codigo: str, accion: str):
    if accion not in ["Entrada", "Salida"]:
        raise HTTPException(status_code=400, detail="Acción inválida")

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM usuarios WHERE codigo = %s", (codigo,))
    row = cur.fetchone()

    if not row:
        db.close()
        raise HTTPException(status_code=404, detail="Código no encontrado")

    cur.execute("INSERT INTO registros (usuario_id, accion) VALUES (%s, %s)", (row[0], accion))
    db.close()
    return {"mensaje": f"¡{accion} registrada con éxito!"}

# ==================== RUTAS DE PRUEBA ====================
@app.get("/")
def home():
    return {"message": "BiciSENA API - 100% funcional - Listo para el SENA"}

@app.get("/health")
def health():
    return {"status": "OK", "message": "Todo perfecto con Supabase"}
