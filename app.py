import os
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import requests
from datetime import datetime

# --- CONFIGURACIÓN ---
# Las "credenciales" ya no se escriben aquí. Se configuran en el servidor.
# Esto es mucho más seguro, como guardar los secretos en el vestuario.
MP_ACCESS_TOKEN = os.environ.get('MP_ACCESS_TOKEN')
DATABASE_URL = os.environ.get('DATABASE_URL')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELO DE LA BASE DE DATOS (El molde para nuestros trofeos) ---
# Así es como se verá cada registro en nuestra base de datos.
class Transaccion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.String(100))
    monto = db.Column(db.Float)
    moneda = db.Column(db.String(10))
    concepto = db.Column(db.String(200))
    email_pagador = db.Column(db.String(100))
    estado = db.Column(db.String(50))
    pago_id = db.Column(db.BigInteger, unique=True) # ID único de Mercado Pago

    def __repr__(self):
        return f'<Transaccion {self.pago_id}>'

# --- RUTA PRINCIPAL (La página que todos verán) ---
@app.route('/')
def index():
    # Buscamos todas las transacciones en la base de datos, ordenadas de la más nueva a la más vieja
    transacciones = Transaccion.query.order_by(Transaccion.id.desc()).all()
    # Se las pasamos a nuestra "camiseta" (el archivo HTML) para que las muestre
    return render_template('index.html', transacciones=transacciones)

# --- WEBHOOK (Sigue siendo nuestra antena para recibir pases de Mercado Pago) ---
@app.route('/webhook-mercadopago', methods=['POST'])
def webhook_mp():
    data = request.json
    if data and data.get("action") == "payment.created":
        payment_id = data["data"]["id"]
        url = f"https://api.mercadopago.com/v1/payments/{payment_id}"
        headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}
        
        try:
            response = requests.get(url, headers=headers)
            payment_details = response.json()
            
            if response.status_code == 200 and payment_details.get("status") == "approved":
                print(">>> PAGO APROBADO. Guardando en la base de datos...")
                
                # Creamos un nuevo objeto "Transaccion" con los datos del pago
                nueva_transaccion = Transaccion(
                    fecha=payment_details.get('date_approved', 'N/A'),
                    monto=payment_details.get('transaction_amount', 0),
                    moneda=payment_details.get('currency_id', ''),
                    concepto=payment_details.get('description', 'Sin concepto'),
                    email_pagador=payment_details.get('payer', {}).get('email', 'N/A'),
                    estado=payment_details.get('status', 'N/A'),
                    pago_id=payment_details.get('id', 0)
                )
                
                # Lo agregamos a la base de datos
                db.session.add(nueva_transaccion)
                db.session.commit()
                print(">>> ¡Transacción guardada en la base de datos con éxito!")
                
        except Exception as e:
            print(f"!!! Error al procesar el pago: {e}")

    return jsonify({"status": "received"}), 200

# Esta línea es para crear las tablas en la base de datos la primera vez
with app.app_context():
    db.create_all()