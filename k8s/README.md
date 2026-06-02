Project 1:
1. Target architecture
•	Frontend: Nginx container serving static HTML/JS, calling backend via /api/...
•	Backend: Python (Flask) API container, talking to RDS (MySQL/MariaDB)
•	Kubernetes: 2 Deployments + 2 Services
•	Argo CD: Watches GitHub repo and syncs manifests
•	RDS: Public endpoint, credentials via K8s Secret
2. GitHub repo structure
text
crud-app/
  backend/
    app.py
    requirements.txt
    Dockerfile
  frontend/
    index.html
    nginx.conf
    Dockerfile
  k8s/
    namespace.yaml
    secret-db.yaml
    configmap-backend.yaml
    deployment-backend.yaml
    service-backend.yaml
    deployment-frontend.yaml
    service-frontend.yaml
    ingress.yaml   # optional if you use ingress
  argocd/
    application.yaml
You’ll push this whole repo to GitHub.
3. Backend: simple Python CRUD API
backend/app.py (example with MySQL)
python
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
Make sure your RDS DB has a table:
sql
CREATE TABLE items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL
);
backend/requirements.txt
text
flask
mysql-connector-python
backend/Dockerfile
dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV FLASK_ENV=production

EXPOSE 5000

CMD ["python", "app.py"]
4. Frontend: Nginx static UI
frontend/index.html (very simple)
html
<!DOCTYPE html>
<html>
<head>
  <title>Simple CRUD</title>
</head>
<body>
  <h1>Items</h1>
  <input id="itemName" placeholder="Item name" />
  <button onclick="createItem()">Add</button>
  <ul id="items"></ul>

  <script>
    const API_BASE = '/api';

    async function loadItems() {
      const res = await fetch(`${API_BASE}/items`);
      const data = await res.json();
      const list = document.getElementById('items');
      list.innerHTML = '';
      data.forEach(item => {
        const li = document.createElement('li');
        li.textContent = item.name + ' ';
        const btn = document.createElement('button');
        btn.textContent = 'Delete';
        btn.onclick = () => deleteItem(item.id);
        li.appendChild(btn);
        list.appendChild(li);
      });
    }

    async function createItem() {
      const name = document.getElementById('itemName').value;
      await fetch(`${API_BASE}/items`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name})
      });
      document.getElementById('itemName').value = '';
      loadItems();
    }

    async function deleteItem(id) {
      await fetch(`${API_BASE}/items/${id}`, { method: 'DELETE' });
      loadItems();
    }

    loadItems();
  </script>
</body>
</html>
frontend/nginx.conf
nginx
events {}

http {
    server {
        listen 80;

        root /usr/share/nginx/html;
        index index.html;

        location / {
            try_files $uri /index.html;
        }

        location /api/ {
            proxy_pass http://backend:5000/;
        }
    }
}
frontend/Dockerfile
dockerfile
FROM nginx:alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY index.html /usr/share/nginx/html/index.html

EXPOSE 80
5. Build and push images
You can use Docker Hub or ECR. Example with Docker Hub:
bash
# from repo root
docker build -t YOUR_DOCKER_USER/crud-backend:v1 ./backend
docker build -t YOUR_DOCKER_USER/crud-frontend:v1 ./frontend

docker push YOUR_DOCKER_USER/crud-backend:v1
docker push YOUR_DOCKER_USER/crud-frontend:v1
We’ll reference these in K8s manifests.
6. Kubernetes manifests (k8s/)
k8s/namespace.yaml
yaml
apiVersion: v1
kind: Namespace
metadata:
  name: crud-app
k8s/secret-db.yaml
yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
  namespace: crud-app
type: Opaque
data:
  DB_USER: <base64-username>
  DB_PASS: <base64-password>
  DB_NAME: <base64-dbname>
Encode with: echo -n 'value' | base64
k8s/configmap-backend.yaml
yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: backend-config
  namespace: crud-app
data:
  DB_HOST: "your-rds-endpoint.rds.amazonaws.com"
k8s/deployment-backend.yaml
yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: crud-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
        - name: backend
          image: YOUR_DOCKER_USER/crud-backend:v1
          ports:
            - containerPort: 5000
          env:
            - name: DB_HOST
              valueFrom:
                configMapKeyRef:
                  name: backend-config
                  key: DB_HOST
            - name: DB_USER
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: DB_USER
            - name: DB_PASS
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: DB_PASS
            - name: DB_NAME
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: DB_NAME
k8s/service-backend.yaml
yaml
apiVersion: v1
kind: Service
metadata:
  name: backend
  namespace: crud-app
spec:
  selector:
    app: backend
  ports:
    - port: 5000
      targetPort: 5000
k8s/deployment-frontend.yaml
yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: crud-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
        - name: frontend
          image: YOUR_DOCKER_USER/crud-frontend:v1
          ports:
            - containerPort: 80
k8s/service-frontend.yaml
yaml
apiVersion: v1
kind: Service
metadata:
  name: frontend
  namespace: crud-app
spec:
  type: LoadBalancer
  selector:
    app: frontend
  ports:
    - port: 80
      targetPort: 80
If you already have an Ingress controller and prefer Ingress instead of LoadBalancer, we can swap this later.
7. Argo CD Application (argocd/application.yaml)
Assuming:
•	Argo CD is installed in argocd namespace
•	Your GitHub repo: https://github.com/YOUR_USER/crud-app.git
yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: crud-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: 'https://github.com/YOUR_USER/crud-app.git'
    targetRevision: main
    path: k8s
  destination:
    server: 'https://kubernetes.default.svc'
    namespace: crud-app
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
8. Step by step flow
1.	Prepare RDS
o	Ensure DB + items table exist.
o	Note endpoint, username, password, dbname.
2.	Clone repo locally
o	Create structure as above.
o	Fill in backend, frontend, k8s, argocd files.
3.	Build & push images
o	Replace YOUR_DOCKER_USER with your Docker Hub/ECR.
o	Build + push backend and frontend images.
4.	Update K8s manifests
o	Set correct image names.
o	Set DB_HOST in ConfigMap.
o	Base64 encode DB creds in Secret.
5.	Push to GitHub
o	Commit and push to main (or your chosen branch).
6.	Create Argo CD Application
o	Apply:
bash
kubectl apply -f argocd/application.yaml
o	Or create via Argo CD UI using same values.
7.	Wait for sync
o	In Argo CD UI, check crud-app Application.
o	It should sync and create namespace, Deployments, Services.
8.	Access app
o	Get frontend service:
bash
kubectl get svc -n crud-app
o	Use the EXTERNAL-IP of frontend LoadBalancer on port 80.
o	Open in browser → test CRUD.
