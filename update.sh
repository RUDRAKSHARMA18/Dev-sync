#!/bin/bash
echo "🚀 Starting DevSync Update..."

# 1. Pull latest code from GitHub
echo "📦 Pulling latest code..."
git pull origin main

# 2. Rebuild the frontend
echo "⚛️ Rebuilding React frontend..."
cd frontend
npm install
npm run build
cd ..

# 3. Update Python dependencies
echo "🐍 Updating Python dependencies..."
cd backend
source venv/bin/activate
pip install -r requirements.txt
cd ..

# 4. Restart the systemd service
echo "🔄 Restarting DevSync service..."
sudo systemctl restart devsync.service

echo "✅ Update complete! DevSync is live."
