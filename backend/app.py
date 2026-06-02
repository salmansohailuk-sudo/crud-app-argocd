from flask import Flask, request, jsonify
import os
import mysql.connector

app = Flask(__name__)

db_config = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "database": os.getenv("DB_NAME"),
}

def get_conn():
    return mysql.connector.connect(**db_config)

@app.route("/api/items", methods=["GET"])
def list_items():
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, name FROM items")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)

@app.route("/api/items", methods=["POST"])
def create_item():
    data = request.get_json()
    name = data.get("name")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO items (name) VALUES (%s)", (name,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "created"}), 201

@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM items WHERE id=%s", (item_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "deleted"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
