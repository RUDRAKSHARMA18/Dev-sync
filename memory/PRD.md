# DevSync - Product Requirements Document

## Original Problem Statement
DevSync is a full-stack SaaS platform connecting LeetCode, GitHub, Codeforces, CodeChef. Tracks developer activity, generates AI insights, assigns goals, calculates readiness score. Critical: strict user isolation.

## Architecture
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI + Recharts
- **Backend**: FastAPI (Python) with async Motor for MongoDB
- **Database**: MongoDB (via MONGO_URL env)
- **Auth**: JWT (httpOnly cookies) + Google OAuth (Emergent Auth)
- **AI**: OpenAI GPT-5.2 via Emergent LLM key
- **Email**: Resend API for password reset emails

## What's Been Implemented
### Backend (April 2026)
- [x] Full auth (register, login, logout, me, refresh, Google OAuth)
- [x] Password reset with Resend email (fallback to token if email fails)
- [x] Profile editing (PUT /api/profile - name)
- [x] Brute force protection (5 attempts = 15min lockout)
- [x] Platform connections (LeetCode, GitHub, Codeforces, CodeChef)
- [x] Contribution heatmap (365 days)
- [x] Auto-sync scheduler (every 6 hours)
- [x] Dashboard, Readiness score, AI Insights, Goals CRUD

### Frontend
- [x] Split-screen auth page (email/password + Google + forgot password)
- [x] Dashboard with stats, weekly chart, heatmap, platform details
- [x] Insights, Goals, Readiness Score, Settings pages
- [x] Inline profile name editing on Settings
- [x] Dark/Light mode toggle

## Test Results (3 iterations)
- Backend: 95-97%, Frontend: 100%
- Critical user isolation: PASSED
- All new features: PASSED

## Prioritized Backlog
### P1
- [ ] Verify Resend domain for production email delivery
- [ ] Export readiness report as PDF
- [ ] Social sharing of readiness score (public URL)

### P2
- [ ] User avatar upload
- [ ] Detailed GitHub contribution graph integration
- [ ] Platform category breakdown (CF/CC problem tags)
- [ ] Email notifications for goal reminders
