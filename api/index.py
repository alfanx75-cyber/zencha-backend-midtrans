import os
import json
import requests
from flask import Flask, request, jsonify, make_response
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai

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

# ==========================================
# 3. KONFIGURASI KUNCI RAHASIA & AI
# ==========================================
MIDTRANS_SERVER_KEY = os.environ.get('MIDTRANS_SERVER_KEY')
FONNTE_TOKEN = os.environ.get("FONNTE_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

gemini_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        SYSTEM_INSTRUCTION = """
        Anda adalah asisten AI resmi dari ZENCHA, brand minuman sehat premium yang fokus pada Matcha dan Taro. 
        Gunakan bahasa yang ramah, asik, sopan, dan kekinian.

        Informasi Produk:
        - Harga semua menu (Matcha Latte & Taro Latte) adalah Rp 8.000.
        - Pembeli bisa memilih opsi tambahan pemanis sehat: Tetes Stevia (0, 1, atau 2 tetes).
        - Manfaat Taro: Melancarkan pencernaan, mengontrol gula darah, dan memberikan energi.
        - Manfaat Matcha: Tinggi antioksidan, meningkatkan fokus, dan membakar kalori.

        Tugas Anda:
        1. Jawab pertanyaan pelanggan seputar menu dan manfaatnya.
        2. Jika pelanggan ingin memesan, arahkan mereka untuk memesan dan membayar secara otomatis melalui website katalog kita di: https://zencha-project.lovable.app/
        3. Jangan menerima pembayaran langsung di chat, selalu arahkan ke link website di atas.
        """
        gemini_model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=SYSTEM_INSTRUCTION)
        print("✅ Gemini AI berhasil diinisialisasi")
    except Exception as e:
        print("❌ Gemini Init Error:", str(e))


# ==========================================
# 4. ENDPOINT: MEMINTA TOKEN PEMBAYARAN MIDTRANS
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
# 5. ENDPOINT: WEBHOOK MIDTRANS (UPDATE KASIR OTOMATIS)
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
                pesanan_ref = db.collection('pesanan_masuk').where('order_id', '==', order_id).limit(1)
                docs = pesanan_ref.stream()
                
                for doc in docs:
                    doc.reference.update({
                        'status': 'Lunas',
                        'metode_bayar': payment_type
                    })
                    print(f"✅ Firebase Updated: Pesanan {order_id} LUNAS!")
                
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        print("❌ Webhook Error:", str(e))
        return jsonify({"error": str(e)}), 500

# ==========================================
# 6. ENDPOINT: MENERIMA PESAN WA DARI FONNTE
# ==========================================
@app.route('/api/whatsapp-bot', methods=['POST', 'GET'])
def whatsapp_bot():
    if request.method == 'GET':
        return "Bot ZENCHA menyala!", 200
        
    try:
        # Fonnte mengirim data via Form Data atau JSON
        data = request.form if request.form else request.json
        
        incoming_msg = data.get('message', '').strip()
        sender_number = data.get('sender', '') 
        
        # Abaikan jika pesan kosong atau dari grup
        if not incoming_msg or not sender_number or "-" in sender_number:
            return jsonify({"status": "ignored"}), 200

        print(f"Pesan masuk dari {sender_number}: {incoming_msg}")

        # Jika Gemini gagal di-load, berikan pesan default
        if not gemini_model:
             bot_reply = "Mohon maaf, sistem AI kami sedang dalam perbaikan. Silakan pesan langsung melalui https://zencha-project.lovable.app/"
        else:
            # 1. Minta Gemini memikirkan balasannya
            response = gemini_model.generate_content(incoming_msg)
            bot_reply = response.text

        # 2. Kirim balasan tersebut ke pelanggan via Fonnte API
        if FONNTE_TOKEN:
            headers = {
                "Authorization": FONNTE_TOKEN
            }
            payload = {
                "target": sender_number,
                "message": bot_reply
            }
            requests.post("https://api.fonnte.com/send", headers=headers, data=payload)
            print(f"✅ Balasan terkirim ke {sender_number}")
        else:
            print("⚠️ FONNTE_TOKEN belum dipasang!")

        return jsonify({"status": "sent"}), 200
        
    except Exception as e:
        print("❌ Bot Error:", str(e))
        return jsonify({"error": str(e)}), 500