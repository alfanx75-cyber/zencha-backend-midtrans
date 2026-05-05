from flask import Flask, request, jsonify, make_response
import requests
import os

app = Flask(__name__)

# Fungsi penjinak Satpam CORS
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

MIDTRANS_SERVER_KEY = os.environ.get('MIDTRANS_SERVER_KEY')

@app.route('/api/get-token', methods=['POST', 'OPTIONS'])
def get_snap_token():
    # Tangani sapaan awal dari browser (Preflight)
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