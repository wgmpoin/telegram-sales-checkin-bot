from flask import Flask, request

app = Flask(__name__)

@app.route('/api/webhook', methods=['POST'])
def webhook_test():
    return "Webhook endpoint is working!", 200

@app.route('/', methods=['GET'])
def root_test():
    return "Root endpoint is working!", 200