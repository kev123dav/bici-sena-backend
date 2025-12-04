from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import psycopg2
import bcrypt
import qrcode
from io import BytesIO
import base64

app = FastAPI(title="BiciSENA - FINAL SUPABASE")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    try:
        conn = psycopg2.connect(
            os.environ["DATABASE_URL"],
            sslmode="require",
            connect_timeout=30
        )
        conn.autocommit = True
        return conn
    except Exception as e:
        raise HTTPException(500, detail=f"Error de conexión: {str(e)}")

class Login(BaseModel):
    cedula: str
    contrasena: str

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
        raise HTTPException(409, "Cédula ya registrada")

    hashed = bcrypt.hashpw(contrasena.encode(), bcrypt.gensalt())
    foto_bici_b = await foto_bici.read()
    foto_usuario_b = await foto_usuario.read()

    qr = qrcode.make(codigo)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    qr_b = buffer.getvalue()

    cur.execute("""
        INSERT INTO usuarios (nombre, cedula, telefono, correo, contrasena, codigo, qr_blob, foto_bici_blob, foto_usuario_blob)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (nombre, cedula, telefono, correo, hashed, codigo, qr_b, foto_bici_b, foto_usuario_b))

    db.close()
    return {"mensaje": "¡Registrado!"}

@app.post("/api/usuario/login")
def login(data: Login):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT nombre,cedula,codigo,qr_blob,foto_bici_blob,foto_usuario_blob,contrasena FROM usuarios WHERE cedula=%s", (data.cedula,))
    row = cur.fetchone()
    db.close()
    if row and bcrypt.checkpw(data.contrasena.encode(), row[6]):
        return {
            "nombre": row[0], "cedula": row[1], "codigo": row[2],
            "qr_blob": base64.b64encode(row[3]).decode(),
            "foto_bici_blob": base64.b64encode(row[4]).decode() if row[4] else None,
            "foto_usuario_blob": base64.b64encode(row[5]).decode() if row[5] else None
        }
    raise HTTPException(401, "Credenciales inválidas")

@app.get("/api/usuario/qr/{codigo}")
def qr(codigo: str):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT nombre,cedula,telefono,foto_bici_blob,foto_usuario_blob FROM usuarios WHERE codigo=%s", (codigo,))
    row = cur.fetchone()
    db.close()
    if not row: raise HTTPException(404, "No encontrado")
    return {
        "nombre": row[0], "cedula": row[1], "telefono": row[2],
        "foto_bici_blob": base64.b64encode(row[3]).decode(),
        "foto_usuario_blob": base64.b64encode(row[4]).decode()
    }

@app.post("/api/registro/{codigo}/{accion}")
def registro(codigo: str, accion: str):
    if accion not in ["Entrada","Salida"]: raise HTTPException(400, "Acción inválida")
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM usuarios WHERE codigo=%s", (codigo,))
    uid = cur.fetchone()
    if not uid: raise HTTPException(404, "Código no existe")
    cur.execute("INSERT INTO registros (usuario_id,accion) VALUES (%s,%s)", (uid[0], accion))
    db.close()
    return {"mensaje": f"¡{accion} registrada!"}

@app.get("/health")
def health():
    return {"status":"OK"}

@app.get("/")
def home():
    return {"message":"BiciSENA API - 100% viva"}
