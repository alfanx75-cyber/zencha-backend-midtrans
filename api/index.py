import os
import json
import requests
from flask import Flask, request, jsonify, make_response
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# ==========================================
# 1. PENJINAK CORS (AGAR LOVABLE BISA MENGAKSES)
# ==========================================
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# ==========================================
# 2. INISIALISASI FIREBASE ADMIN
# ==========================================
db = None
try:
    if not firebase_admin._apps:
        firebase_cert_string = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
        if firebase_cert_string:
            firebase_cert = json.loads(firebase_cert_string)
            cred = credentials.Certificate(firebase_cert)
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            print("✅ Firebase Admin berhasil diinisialisasi")
        else:
            print("⚠️ FIREBASE_SERVICE_ACCOUNT belum dipasang di Vercel Env")
except Exception as e:
    print("❌ Firebase Admin Init Error:", str(e))

MIDTRANS_SERVER_KEY = os.environ.get('MIDTRANS_SERVER_KEY')

# ==========================================
# 3. ENDPOINT: MEMINTA TOKEN PEMBAYARAN MIDTRANS
# ==========================================
@app.route('/api/get-token', methods=['POST', 'OPTIONS'])
def get_snap_token():
    if request.method == 'OPTIONS':
        return make_response(jsonify({}), 200)

    try:
        data = request.json
        order_id = data.get('order_id')
        gross_amount = data.get('total_harga')
        
        payload = {
            "transaction_details": {
                "order_id": order_id,
                "gross_amount": gross_amount
            },
            "credit_card": {
                "secure": True
            }
        }
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            "https://app.sandbox.midtrans.com/snap/v1/transactions",
            json=payload,
            auth=(MIDTRANS_SERVER_KEY, ''),
            headers=headers
        )
        
        midtrans_data = response.json()
        return jsonify({"token": midtrans_data.get('token')}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# 4. ENDPOINT: WEBHOOK MIDTRANS (UPDATE KASIR OTOMATIS)
# ==========================================
@app.route('/api/webhook', methods=['POST', 'OPTIONS'])
def midtrans_webhook():
    if request.method == 'OPTIONS':
        return make_response(jsonify({}), 200)
        
    try:
        notif = request.json
        transaction_status = notif.get('transaction_status')
        order_id = notif.get('order_id')
        payment_type = notif.get('payment_type')
        
        # Jika pelanggan sukses membayar (uang masuk)
        if transaction_status in ['settlement', 'capture']:
            if db:
                # Cari pesanan di Firestore berdasarkan order_id
                pesanan_ref = db.collection('pesanan_masuk').where('order_id', '==', order_id).limit(1)
                docs = pesanan_ref.stream()
                
                for doc in docs:
                    # Ubah statusnya menjadi Lunas agar KDS berubah hijau
                    doc.reference.update({
                        'status': 'Lunas',
                        'metode_bayar': payment_type
                    })
                    print(f"✅ Firebase Updated: Pesanan {order_id} LUNAS!")
                
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        print("❌ Webhook Error:", str(e))
        return jsonify({"error": str(e)}), 500