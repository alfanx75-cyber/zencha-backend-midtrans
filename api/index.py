from flask import Flask, request, jsonify
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Mengizinkan web Lovable mengakses API ini

MIDTRANS_SERVER_KEY = os.environ.get('MIDTRANS_SERVER_KEY')

@app.route('/api/get-token', methods=['POST'])
def get_snap_token():
    try:
        data = request.json
        # 1. Siapkan data pesanan dari web Lovable
        order_id = data.get('order_id')
        gross_amount = data.get('total_harga')
        
        # 2. Susun format permintaan untuk Midtrans Snap
        payload = {
            "transaction_details": {
                "order_id": order_id,
                "gross_amount": gross_amount
            },
            "credit_card": {
                "secure": True
            }
        }
        
        # 3. Minta token QRIS/E-Money ke Midtrans
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

# Endpoint ini untuk mendengarkan jika pelanggan sudah sukses bayar
@app.route('/api/webhook', methods=['POST'])
def midtrans_webhook():
    notif = request.json
    transaction_status = notif.get('transaction_status')
    order_id = notif.get('order_id')
    
    if transaction_status in ['settlement', 'capture']:
        # DI SINI NANTI KITA TAMBAHKAN KODE UNTUK UPDATE FIREBASE JADI "LUNAS"
        print(f"Pesanan {order_id} LUNAS!")
        
    return jsonify({"status": "ok"}), 200