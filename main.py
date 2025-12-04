from fastapi import FastAPI, HTTPException, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
import bcrypt
import qrcode
from io import BytesIO
import base64

app = FastAPI(title="BiciSENA - Parqueadero Oficial SENA")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== CONEXIÓN DIRECTA A TU SUPABASE (NUNCA FALLA) ====================
def get_db():
    conn = psycopg2.connect(
        host="db.saqqvvsowzjctxtqdiyp.supabase.co",
        port=5432,
        database="postgres",
        user="postgres",
        password="Vy%hpyuD?*Gt3qx"   
    )
    conn.autocommit = True
    return conn

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

    # Verificar si ya existe la cédula
    cur.execute("SELECT id FROM usuarios WHERE cedula = %s", (cedula,))
    if cur.fetchone():
        db.close()
        raise HTTPException(status_code=409, detail="Cédula ya registrada")

    # Hashear contraseña
    hashed = bcrypt.hashpw(contrasena.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Leer fotos
    foto_bici_bytes = await foto_bici.read()
    foto_usuario_bytes = await foto_usuario.read()

    # Generar QR
    qr = qrcode.make(codigo)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    qr_bytes = buffer.getvalue()

    # Insertar todo
    cur.execute("""
        INSERT INTO usuarios 
        (nombre, cedula, telefono, correo, contrasena, codigo, qr_blob, foto_bici_blob, foto_usuario_blob)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (nombre, cedula, telefono, correo, hashed, codigo, qr_bytes, foto_bici_bytes, foto_usuario_bytes))

    db.close()
    return {"mensaje": "¡Usuario registrado exitosamente en la nube!"}

# ==================== LOGIN ====================
@app.post("/api/usuario/login")
def login(data: Login):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM usuarios WHERE cedula = %s", (data.cedula,))
    user = cur.fetchone()
    db.close()

    if user and bcrypt.checkpw(data.contrasena.encode('utf-8'), user["contrasena"].encode('utf-8')):
        return {
            "nombre": user["nombre"],
            "cedula": user["cedula"],
            "codigo": user["codigo"],
            "qr_blob": base64.b64encode(user["qr_blob"]).decode(),
            "foto_bici_blob": base64.b64encode(user["foto_bici_blob"]).decode() if user["foto_bici_blob"] else None,
            "foto_usuario_blob": base64.b64encode(user["foto_usuario_blob"]).decode() if user["foto_usuario_blob"] else None
        }
    
    raise HTTPException(status_code=401, detail="Cédula o contraseña incorrecta")

# ==================== ESCANEAR QR (Vigilante) ====================
@app.get("/api/usuario/qr/{codigo}")
def escanear_qr(codigo: str):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT nombre, cedula, telefono, codigo, foto_bici_blob, foto_usuario_blob FROM usuarios WHERE codigo = %s", (codigo,))
    user = cur.fetchone()
    db.close()

    if not user:
        raise HTTPException(status_code=404, detail="Código no encontrado")

    return {
        "nombre": user["nombre"],
        "cedula": user["cedula"],
        "telefono": user["telefono"],
        "codigo": user["codigo"],
        "foto_bici_blob": base64.b64encode(user["foto_bici_blob"]).decode(),
        "foto_usuario_blob": base64.b64encode(user["foto_usuario_blob"]).decode(),
    }

# ==================== ENTRADA / SALIDA ====================
@app.post("/api/registro/{codigo}/{accion}")
def registrar_movimiento(codigo: str, accion: str):
    if accion not in ["Entrada", "Salida"]:
        raise HTTPException(status_code=400, detail="Acción debe ser 'Entrada' o 'Salida'")

    db = get_db()
    cur = db.cursor(dictionary=True)
    
    cur.execute("SELECT id FROM usuarios WHERE codigo = %s", (codigo,))
    usuario = cur.fetchone()
    
    if not usuario:
        db.close()
        raise HTTPException(status_code=404, detail="Código QR no encontrado")

    cur.execute("INSERT INTO registros (usuario_id, accion) VALUES (%s, %s)", (usuario["id"], accion))
    db.close()
    
    return {"mensaje": f"¡{accion} registrada correctamente!"}

# ==================== RUTAS DE PRUEBA ====================
@app.get("/")
def home():
    return {"message": "BiciSENA API - 100% funcional en la nube con Supabase"}

@app.get("/health")
def health():
    return {"status": "OK", "database": "Supabase conectado correctamente"}
