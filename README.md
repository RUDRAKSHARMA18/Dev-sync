# DevSync 🚀
> AI-powered developer activity tracker — Built for **AI Made Hackathon 2026**

DevSync connects your LeetCode, GitHub, Codeforces and CodeChef accounts in one place, tracks your coding activity, and uses **GPT-4o AI** to generate personalized insights and calculate your **Interview Readiness Score**.

---

## ✨ Features

- 📊 **Unified Dashboard** — All your coding stats in one place
- 🤖 **AI Insights** — GPT-4o analyzes your activity and gives personalized feedback
- 🎯 **Readiness Score** — Interview readiness out of 100 (DSA 45% + Projects 30% + Consistency 25%)
- 🔥 **Contribution Heatmap** — 365-day activity heatmap like GitHub
- 🎪 **Goal Tracking** — Set and track coding goals with AI-generated suggestions
- 🔐 **Secure Auth** — JWT + Google OAuth, bcrypt passwords, httpOnly cookies
- 🌙 **Dark / Light Mode**
- ⚡ **Auto Sync** — Platforms auto-refresh every 6 hours

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Tailwind CSS + shadcn/ui + Recharts |
| Backend | FastAPI (Python) + async Motor |
| Database | MongoDB |
| Auth | JWT + Google OAuth |
| AI | OpenAI GPT-4o |
| Email | Resend API |

---

## 📸 Screenshots

> Dashboard — Unified stats, heatmap, weekly chart
> Readiness Score — Interview readiness breakdown
> AI Insights — GPT-4o personalized feedback
> Goals — Track and auto-generate coding goals

---

## 🚀 How to Run Locally

### Prerequisites
- Python 3.9+
- Node.js 16+
- MongoDB (local or Atlas)
- OpenAI API Key — [platform.openai.com](https://platform.openai.com/api-keys)
- Google OAuth Client ID — [console.cloud.google.com](https://console.cloud.google.com)

---

### 1. Clone the repo

```bash
git clone https://github.com/RUDRAKSHARMA18/Dev-sync.git
cd Dev-sync
```

### 2. Start MongoDB

```bash
# If using local MongoDB (Mac)
brew services start mongodb-community

# OR use MongoDB Atlas free cloud instance
# https://www.mongodb.com/cloud/atlas
```

### 3. Setup Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy and fill the environment file:
```bash
cp .env.example .env
nano .env                       # Fill in your keys
```

Start the backend:
```bash
uvicorn server:app --reload --port 8001
```

✅ Backend running at `http://localhost:8001`

---

### 4. Setup Frontend

Open a new terminal tab:

```bash
cd frontend
npm install
cp .env.example .env            # Fill in your keys
npm start
```

✅ Frontend running at `http://localhost:3000`

---

### 5. Environment Variables

**backend/.env**
MONGO_URL=mongodb://localhost:27017
DB_NAME=devsync
JWT_SECRET=generate-with-openssl-rand-hex-32
RESEND_API_KEY=optional_for_email
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret
OPENAI_API_KEY=sk-your_openai_key

**frontend/.env**
REACT_APP_BACKEND_URL=http://localhost:8001
REACT_APP_GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com

---

### 6. Google OAuth Setup (for Google login)

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create project → APIs & Services → Credentials → OAuth 2.0 Client
3. Add Authorized JavaScript Origins: `http://localhost:3000`
4. Add Authorized Redirect URIs: `http://localhost:3000`
5. Copy Client ID and Secret to your `.env` files

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Login |
| GET | `/api/auth/me` | Get current user |
| POST | `/api/platforms/connect` | Connect LeetCode/GitHub/etc |
| GET | `/api/dashboard` | Get all stats |
| GET | `/api/readiness` | Get readiness score |
| GET | `/api/insights` | Get AI insights |
| GET | `/api/goals` | Get goals |
| POST | `/api/goals` | Create goal |

---

## 👨‍💻 Built By

**Rudra Sharma** — [@RUDRAKSHARMA18](https://github.com/RUDRAKSHARMA18)

---

