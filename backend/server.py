from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
import os
import logging
import uuid
import secrets
import httpx
import aiohttp
import asyncio
import json
import bcrypt
import jwt
import resend
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from bson import ObjectId

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Resend setup
resend.api_key = os.environ.get("RESEND_API_KEY", "")

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT config
JWT_ALGORITHM = "HS256"

def get_jwt_secret():
    return os.environ["JWT_SECRET"]

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")


from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"status": "DevSync Backend Running"}



# ======================== MODELS ========================

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str

class LoginRequest(BaseModel):
    email: str
    password: str

class PlatformConnectRequest(BaseModel):
    platform: str
    username: str
    pat_token: Optional[str] = None

class GoalCreate(BaseModel):
    title: str
    description: str
    target_value: int = 1
    category: str = "general"

class GoalUpdate(BaseModel):
    current_value: Optional[int] = None
    completed: Optional[bool] = None

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None

# ======================== PASSWORD HASHING ========================

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

# ======================== JWT TOKENS ========================

def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        "type": "access"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "refresh"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=3600, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")

def clear_auth_cookies(response: Response):
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    response.delete_cookie(key="session_token", path="/")

# ======================== AUTH HELPER ========================

async def get_current_user(request: Request) -> dict:
    # Try session_token first (Google OAuth)
    session_token = request.cookies.get("session_token")
    if session_token:
        session = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
        if session:
            expires_at = session.get("expires_at")
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at and expires_at > datetime.now(timezone.utc):
                user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
                if user:
                    user.pop("password_hash", None)
                    return user

    # Try JWT access_token
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ======================== AUTH ENDPOINTS ========================

@api_router.post("/auth/register")
async def register(req: RegisterRequest, response: Response):
    email = req.email.strip().lower()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    password_hash = hash_password(req.password)

    user_doc = {
        "user_id": user_id,
        "email": email,
        "name": req.name.strip(),
        "password_hash": password_hash,
        "role": "user",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "auth_provider": "email"
    }
    await db.users.insert_one(user_doc)

    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    set_auth_cookies(response, access_token, refresh_token)

    return {
        "user_id": user_id,
        "email": email,
        "name": req.name.strip(),
        "role": "user"
    }

@api_router.post("/auth/login")
async def login(req: LoginRequest, request: Request, response: Response):
    email = req.email.strip().lower()
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown").split(",")[0].strip()
    identifier = f"{ip}:{email}"

    # Brute force check
    attempt = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0})
    if attempt and attempt.get("count", 0) >= 5:
        locked_at = attempt.get("locked_at")
        if locked_at:
            if isinstance(locked_at, str):
                locked_at = datetime.fromisoformat(locked_at)
            if locked_at.tzinfo is None:
                locked_at = locked_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - locked_at < timedelta(minutes=15):
                raise HTTPException(status_code=429, detail="Too many login attempts. Try again in 15 minutes.")

    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not user.get("password_hash"):
        # Increment failed attempts
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"locked_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(req.password, user["password_hash"]):
        result = await db.login_attempts.find_one_and_update(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"locked_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
            return_document=ReturnDocument.AFTER
        )
        new_count = result.get("count", 1) if result else 1
        if new_count >= 5:
            raise HTTPException(status_code=429, detail="Too many login attempts. Try again in 15 minutes.")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Clear failed attempts on success
    await db.login_attempts.delete_one({"identifier": identifier})

    access_token = create_access_token(user["user_id"], email)
    refresh_token = create_refresh_token(user["user_id"])
    set_auth_cookies(response, access_token, refresh_token)

    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user.get("name", ""),
        "role": user.get("role", "user")
    }

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    # Delete session from DB if exists
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    clear_auth_cookies(response)
    return {"message": "Logged out successfully"}

@api_router.get("/auth/me")
async def get_me(request: Request):
    user = await get_current_user(request)
    return user

@api_router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        access_token = create_access_token(user["user_id"], user["email"])
        response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=3600, path="/")
        return {"message": "Token refreshed"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

# ======================== PASSWORD RESET ========================

async def send_reset_email(email: str, token: str, user_name: str):
    """Send password reset email via Resend."""
    sender_email = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")

    html_content = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 560px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <div style="display: inline-block; background: #3B82F6; color: white; font-weight: bold; font-size: 18px; width: 44px; height: 44px; line-height: 44px; border-radius: 10px;">DS</div>
            <h1 style="font-size: 24px; color: #09090B; margin: 16px 0 0;">DevSync</h1>
        </div>
        <h2 style="font-size: 20px; color: #09090B; margin-bottom: 8px;">Reset your password</h2>
        <p style="color: #52525B; font-size: 15px; line-height: 1.6;">Hi {user_name},</p>
        <p style="color: #52525B; font-size: 15px; line-height: 1.6;">We received a request to reset your password. Use the token below to set a new password:</p>
        <div style="background: #F4F4F5; border: 1px solid #E4E4E7; border-radius: 8px; padding: 16px; text-align: center; margin: 24px 0;">
            <code style="font-size: 16px; font-weight: 600; color: #09090B; letter-spacing: 0.5px; word-break: break-all;">{token}</code>
        </div>
        <p style="color: #52525B; font-size: 15px; line-height: 1.6;">Copy this token and paste it in the password reset form on DevSync.</p>
        <p style="color: #A1A1AA; font-size: 13px; margin-top: 32px;">This token expires in 1 hour. If you didn't request a password reset, you can safely ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #E4E4E7; margin: 24px 0;" />
        <p style="color: #A1A1AA; font-size: 12px; text-align: center;">DevSync - Track your developer journey</p>
    </div>
    """

    try:
        params = {
            "from": sender_email,
            "to": [email],
            "subject": "DevSync - Password Reset",
            "html": html_content
        }
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Password reset email sent to {email}, id: {result.get('id', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send reset email to {email}: {e}")
        return False

@api_router.post("/auth/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    email = req.email.strip().lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    # Always return success to prevent email enumeration
    if not user or user.get("auth_provider") == "google":
        return {"message": "If an account exists with that email, a reset link has been sent."}

    token = secrets.token_urlsafe(32)
    await db.password_reset_tokens.insert_one({
        "token": token,
        "user_id": user["user_id"],
        "email": email,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "used": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    # Send email via Resend
    user_name = user.get("name", email.split("@")[0])
    email_sent = await send_reset_email(email, token, user_name)

    logger.info(f"Password reset token for {email}: {token}")

    response_data = {"message": "If an account exists with that email, a reset link has been sent."}
    # Include token in response as fallback (for dev/testing, or if email fails)
    if not email_sent:
        response_data["reset_token"] = token
        response_data["email_note"] = "Email delivery failed. Use the token above to reset your password."
    else:
        response_data["email_sent"] = True

    return response_data

@api_router.post("/auth/reset-password")
async def reset_password(req: ResetPasswordRequest):
    token_doc = await db.password_reset_tokens.find_one({"token": req.token, "used": False}, {"_id": 0})
    if not token_doc:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    expires_at = token_doc.get("expires_at", "")
    if expires_at:
        exp_time = datetime.fromisoformat(expires_at)
        if exp_time.tzinfo is None:
            exp_time = exp_time.replace(tzinfo=timezone.utc)
        if exp_time < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Reset token has expired")

    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    new_hash = hash_password(req.new_password)
    await db.users.update_one(
        {"user_id": token_doc["user_id"]},
        {"$set": {"password_hash": new_hash}}
    )
    await db.password_reset_tokens.update_one(
        {"token": req.token},
        {"$set": {"used": True}}
    )

    return {"message": "Password reset successfully"}

# ======================== PROFILE ========================

@api_router.put("/profile")
async def update_profile(req: ProfileUpdateRequest, request: Request):
    user = await get_current_user(request)
    update_dict = {}
    if req.name is not None:
        name = req.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        if len(name) > 100:
            raise HTTPException(status_code=400, detail="Name too long (max 100 characters)")
        update_dict["name"] = name

    if not update_dict:
        raise HTTPException(status_code=400, detail="Nothing to update")

    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": update_dict}
    )

    updated_user = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    updated_user.pop("password_hash", None)
    return updated_user

# ======================== GOOGLE OAUTH (EMERGENT AUTH) ========================

@api_router.post("/auth/google/session")
async def google_session(request: Request, response: Response):
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")

    # Exchange session_id for user data from Emergent Auth
    async with httpx.AsyncClient() as http_client:
        resp = await http_client.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id}
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid session")
        google_data = resp.json()

    email = google_data["email"].lower()
    name = google_data.get("name", email.split("@")[0])
    picture = google_data.get("picture", "")
    session_token_value = google_data.get("session_token", secrets.token_urlsafe(32))

    # Find or create user
    existing_user = await db.users.find_one({"email": email}, {"_id": 0})
    if existing_user:
        user_id = existing_user["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": name, "picture": picture, "last_login": datetime.now(timezone.utc).isoformat()}}
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "role": "user",
            "auth_provider": "google",
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    # Create session
    await db.user_sessions.delete_many({"user_id": user_id})
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token_value,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    response.set_cookie(key="session_token", value=session_token_value, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")

    # Also set JWT tokens for compatibility
    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    set_auth_cookies(response, access_token, refresh_token)

    return {
        "user_id": user_id,
        "email": email,
        "name": name,
        "picture": picture,
        "role": "user"
    }

# ======================== PLATFORM CONNECTIONS ========================

@api_router.post("/platforms/connect")
async def connect_platform(req: PlatformConnectRequest, request: Request):
    user = await get_current_user(request)
    user_id = user["user_id"]
    platform = req.platform.lower()

    if platform not in ["leetcode", "github", "codeforces", "codechef"]:
        raise HTTPException(status_code=400, detail="Unsupported platform")

    # Delete existing connection for this user + platform
    await db.platform_connections.delete_many({"user_id": user_id, "platform": platform})

    connection = {
        "connection_id": f"conn_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "platform": platform,
        "username": req.username.strip(),
        "pat_token": req.pat_token if platform == "github" and req.pat_token else None,
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "last_synced": None,
        "status": "connected"
    }
    await db.platform_connections.insert_one(connection)

    # Initial sync
    sync_data = await sync_platform_data(user_id, platform, req.username.strip(), req.pat_token)

    return {"message": f"{platform} connected successfully", "connection": {k: v for k, v in connection.items() if k != "_id"}, "sync_data": sync_data}

@api_router.get("/platforms")
async def get_platforms(request: Request):
    user = await get_current_user(request)
    connections = await db.platform_connections.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).to_list(100)
    # Remove PAT from response
    for conn in connections:
        conn.pop("pat_token", None)
    return {"platforms": connections}

@api_router.delete("/platforms/{platform}")
async def disconnect_platform(platform: str, request: Request):
    user = await get_current_user(request)
    result = await db.platform_connections.delete_many({"user_id": user["user_id"], "platform": platform.lower()})
    await db.platform_data.delete_many({"user_id": user["user_id"], "platform": platform.lower()})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Platform not connected")
    return {"message": f"{platform} disconnected"}

@api_router.post("/platforms/{platform}/sync")
async def sync_platform(platform: str, request: Request):
    user = await get_current_user(request)
    user_id = user["user_id"]
    conn = await db.platform_connections.find_one({"user_id": user_id, "platform": platform.lower()}, {"_id": 0})
    if not conn:
        raise HTTPException(status_code=404, detail="Platform not connected")

    sync_data = await sync_platform_data(user_id, platform.lower(), conn["username"], conn.get("pat_token"))

    await db.platform_connections.update_one(
        {"user_id": user_id, "platform": platform.lower()},
        {"$set": {"last_synced": datetime.now(timezone.utc).isoformat()}}
    )

    return {"message": "Sync complete", "data": sync_data}

# ======================== PLATFORM DATA FETCHING ========================

async def sync_platform_data(user_id: str, platform: str, username: str, pat_token: str = None) -> dict:
    try:
        if platform == "leetcode":
            data = await fetch_leetcode_data(username)
        elif platform == "github":
            data = await fetch_github_data(username, pat_token)
        elif platform == "codeforces":
            data = await fetch_codeforces_data(username)
        elif platform == "codechef":
            data = await fetch_codechef_data(username)
        else:
            data = {}

        data["user_id"] = user_id
        data["platform"] = platform
        data["username"] = username
        data["synced_at"] = datetime.now(timezone.utc).isoformat()

        await db.platform_data.delete_many({"user_id": user_id, "platform": platform})
        await db.platform_data.insert_one(data)
        data.pop("_id", None)
        return data
    except Exception as e:
        logger.error(f"Error syncing {platform} for user {user_id}: {e}")
        return {"error": str(e), "platform": platform}

async def fetch_leetcode_data(username: str) -> dict:
    query = """
    query getUserProfile($username: String!) {
        matchedUser(username: $username) {
            username
            submitStatsGlobal: submitStats {
                acSubmissionNum {
                    difficulty
                    count
                    submissions
                }
            }
            profile {
                ranking
                reputation
                starRating
            }
            submissionCalendar
        }
        userContestRanking(username: $username) {
            attendedContestsCount
            rating
            globalRanking
        }
    }
    """
    async with httpx.AsyncClient(timeout=15.0) as http_client:
        resp = await http_client.post(
            "https://leetcode.com/graphql",
            json={"query": query, "variables": {"username": username}},
            headers={"Content-Type": "application/json", "Referer": "https://leetcode.com"}
        )
        if resp.status_code != 200:
            return {"error": "Failed to fetch LeetCode data", "problems_solved": 0}

        result = resp.json()
        user_data = result.get("data", {}).get("matchedUser")
        if not user_data:
            return {"error": "LeetCode user not found", "problems_solved": 0}

        stats = user_data.get("submitStatsGlobal", {}).get("acSubmissionNum", [])
        total = 0
        easy = 0
        medium = 0
        hard = 0
        for s in stats:
            if s["difficulty"] == "All":
                total = s["count"]
            elif s["difficulty"] == "Easy":
                easy = s["count"]
            elif s["difficulty"] == "Medium":
                medium = s["count"]
            elif s["difficulty"] == "Hard":
                hard = s["count"]

        contest = result.get("data", {}).get("userContestRanking") or {}
        profile = user_data.get("profile", {})

        # Parse submission calendar for streak
        calendar_str = user_data.get("submissionCalendar", "{}")
        try:
            calendar = json.loads(calendar_str) if isinstance(calendar_str, str) else calendar_str
        except:
            calendar = {}

        streak = calculate_streak(calendar)

        return {
            "problems_solved": total,
            "easy": easy,
            "medium": medium,
            "hard": hard,
            "ranking": profile.get("ranking", 0),
            "contest_rating": contest.get("rating", 0),
            "contests_attended": contest.get("attendedContestsCount", 0),
            "streak": streak,
            "submission_calendar": calendar
        }

def calculate_streak(calendar: dict) -> int:
    if not calendar:
        return 0
    today = datetime.now(timezone.utc).date()
    streak = 0
    current = today
    while True:
        ts = int(datetime(current.year, current.month, current.day, tzinfo=timezone.utc).timestamp())
        if str(ts) in calendar and calendar[str(ts)] > 0:
            streak += 1
            current -= timedelta(days=1)
        else:
            break
    return streak

async def fetch_github_data(username: str, pat_token: str = None) -> dict:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if pat_token:
        headers["Authorization"] = f"token {pat_token}"

    async with httpx.AsyncClient(timeout=15.0) as http_client:
        # Fetch user info
        user_resp = await http_client.get(f"https://api.github.com/users/{username}", headers=headers)
        if user_resp.status_code != 200:
            return {"error": "GitHub user not found", "total_repos": 0, "total_commits": 0}

        user_info = user_resp.json()

        # Fetch repos
        repos_resp = await http_client.get(
            f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated",
            headers=headers
        )
        repos = repos_resp.json() if repos_resp.status_code == 200 else []

        total_stars = sum(r.get("stargazers_count", 0) for r in repos if isinstance(r, dict))
        languages = {}
        for r in repos:
            if isinstance(r, dict) and r.get("language"):
                languages[r["language"]] = languages.get(r["language"], 0) + 1

        # Fetch recent events for commit count
        events_resp = await http_client.get(
            f"https://api.github.com/users/{username}/events?per_page=100",
            headers=headers
        )
        events = events_resp.json() if events_resp.status_code == 200 else []
        total_commits = 0
        weekly_commits = {}
        for event in events:
            if isinstance(event, dict) and event.get("type") == "PushEvent":
                commits_count = len(event.get("payload", {}).get("commits", []))
                total_commits += commits_count
                created = event.get("created_at", "")[:10]
                weekly_commits[created] = weekly_commits.get(created, 0) + commits_count

        return {
            "total_repos": user_info.get("public_repos", 0),
            "total_stars": total_stars,
            "followers": user_info.get("followers", 0),
            "following": user_info.get("following", 0),
            "total_commits": total_commits,
            "languages": languages,
            "weekly_commits": weekly_commits,
            "bio": user_info.get("bio", ""),
            "avatar_url": user_info.get("avatar_url", "")
        }

async def fetch_codeforces_data(username: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as http_client:
        # User info
        info_resp = await http_client.get(f"https://codeforces.com/api/user.info?handles={username}")
        if info_resp.status_code != 200:
            return {"error": "Codeforces user not found", "rating": 0}

        info = info_resp.json()
        if info.get("status") != "OK":
            return {"error": "Codeforces user not found", "rating": 0}

        user_info = info["result"][0]

        # User submissions
        sub_resp = await http_client.get(f"https://codeforces.com/api/user.status?handle={username}&from=1&count=1000")
        submissions = []
        if sub_resp.status_code == 200:
            sub_data = sub_resp.json()
            if sub_data.get("status") == "OK":
                submissions = sub_data["result"]

        problems_solved = len(set(
            f"{s['problem'].get('contestId', 0)}-{s['problem'].get('index', '')}"
            for s in submissions
            if s.get("verdict") == "OK"
        ))

        # Rating history
        rating_resp = await http_client.get(f"https://codeforces.com/api/user.rating?handle={username}")
        rating_history = []
        if rating_resp.status_code == 200:
            rating_data = rating_resp.json()
            if rating_data.get("status") == "OK":
                rating_history = [{"contest": r.get("contestName", ""), "rating": r.get("newRating", 0)} for r in rating_data["result"][-10:]]

        return {
            "rating": user_info.get("rating", 0),
            "max_rating": user_info.get("maxRating", 0),
            "rank": user_info.get("rank", "unrated"),
            "max_rank": user_info.get("maxRank", "unrated"),
            "problems_solved": problems_solved,
            "contests_participated": len(rating_history),
            "rating_history": rating_history
        }

async def fetch_codechef_data(username: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as http_client:
        resp = await http_client.get(f"https://codechef-api.vercel.app/{username}")
        if resp.status_code != 200:
            return {"error": "CodeChef user not found", "problems_solved": 0, "rating": 0}

        data = resp.json()
        if not data or data.get("success") is False:
            return {"error": "CodeChef user not found", "problems_solved": 0, "rating": 0}

        return {
            "rating": data.get("currentRating", 0),
            "max_rating": data.get("highestRating", 0),
            "stars": data.get("stars", "0"),
            "problems_solved": data.get("totalProblemsSolved", 0) if data.get("totalProblemsSolved") else 0,
            "global_rank": data.get("globalRank", 0),
            "country_rank": data.get("countryRank", 0),
            "country": data.get("countryName", ""),
        }

# ======================== CONTRIBUTION HEATMAP ========================

@api_router.get("/heatmap")
async def get_heatmap(request: Request):
    user = await get_current_user(request)
    user_id = user["user_id"]

    platform_data_list = await db.platform_data.find({"user_id": user_id}, {"_id": 0}).to_list(10)

    # Aggregate daily activity across all platforms for the last 365 days
    heatmap = {}
    today = datetime.now(timezone.utc).date()

    for pd in platform_data_list:
        if pd.get("platform") == "leetcode":
            cal = pd.get("submission_calendar", {})
            for ts_str, count in cal.items():
                try:
                    ts = int(ts_str)
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc).date()
                    day_key = dt.strftime("%Y-%m-%d")
                    heatmap[day_key] = heatmap.get(day_key, 0) + count
                except:
                    pass
        elif pd.get("platform") == "github":
            wc = pd.get("weekly_commits", {})
            for day, count in wc.items():
                heatmap[day] = heatmap.get(day, 0) + count

    # Build heatmap data for last 365 days
    heatmap_data = []
    for i in range(364, -1, -1):
        d = today - timedelta(days=i)
        day_key = d.strftime("%Y-%m-%d")
        heatmap_data.append({
            "date": day_key,
            "count": heatmap.get(day_key, 0),
            "weekday": d.weekday(),
            "month": d.month
        })

    return {"heatmap": heatmap_data}

# ======================== DASHBOARD DATA ========================

@api_router.get("/dashboard")
async def get_dashboard(request: Request):
    user = await get_current_user(request)
    user_id = user["user_id"]

    connections = await db.platform_connections.find({"user_id": user_id}, {"_id": 0}).to_list(10)
    platform_data_list = await db.platform_data.find({"user_id": user_id}, {"_id": 0}).to_list(10)

    # Aggregate stats
    total_problems = 0
    total_commits = 0
    streak = 0
    weekly_data = {}

    for pd in platform_data_list:
        if pd.get("platform") == "leetcode":
            total_problems += pd.get("problems_solved", 0)
            streak = max(streak, pd.get("streak", 0))
            cal = pd.get("submission_calendar", {})
            for ts, count in cal.items():
                try:
                    dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                    day_key = dt.strftime("%Y-%m-%d")
                    weekly_data[day_key] = weekly_data.get(day_key, 0) + count
                except:
                    pass
        elif pd.get("platform") == "github":
            total_commits += pd.get("total_commits", 0)
            wc = pd.get("weekly_commits", {})
            for day, count in wc.items():
                weekly_data[day] = weekly_data.get(day, 0) + count
        elif pd.get("platform") == "codeforces":
            total_problems += pd.get("problems_solved", 0)
        elif pd.get("platform") == "codechef":
            total_problems += pd.get("problems_solved", 0)

    # Build weekly graph (last 7 days)
    today = datetime.now(timezone.utc).date()
    weekly_graph = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        day_key = d.strftime("%Y-%m-%d")
        weekly_graph.append({
            "date": day_key,
            "day": d.strftime("%a"),
            "activity": weekly_data.get(day_key, 0)
        })

    # Remove sensitive data from connections
    clean_connections = []
    for conn in connections:
        clean_connections.append({
            "platform": conn["platform"],
            "username": conn["username"],
            "connected_at": conn["connected_at"],
            "last_synced": conn.get("last_synced"),
            "status": conn.get("status", "connected")
        })

    return {
        "total_problems": total_problems,
        "total_commits": total_commits,
        "streak": streak,
        "weekly_graph": weekly_graph,
        "connections": clean_connections,
        "platform_data": platform_data_list
    }

# ======================== READINESS SCORE ========================

@api_router.get("/readiness")
async def get_readiness(request: Request):
    user = await get_current_user(request)
    user_id = user["user_id"]

    platform_data_list = await db.platform_data.find({"user_id": user_id}, {"_id": 0}).to_list(10)

    # DSA Score (45%) - based on problems solved
    dsa_problems = 0
    for pd in platform_data_list:
        if pd.get("platform") in ["leetcode", "codeforces", "codechef"]:
            dsa_problems += pd.get("problems_solved", 0)

    dsa_score = min(100, (dsa_problems / 300) * 100)

    # Projects Score (30%) - based on GitHub activity
    project_score = 0
    for pd in platform_data_list:
        if pd.get("platform") == "github":
            repos = pd.get("total_repos", 0)
            commits = pd.get("total_commits", 0)
            stars = pd.get("total_stars", 0)
            project_score = min(100, (repos * 3 + commits * 0.5 + stars * 5) / 100 * 100)

    # Consistency Score (25%) - based on streak and activity
    streak = 0
    for pd in platform_data_list:
        if pd.get("platform") == "leetcode":
            streak = max(streak, pd.get("streak", 0))

    connections_count = len(platform_data_list)
    consistency_score = min(100, streak * 10 + connections_count * 15)

    # Weighted total
    total_score = round(dsa_score * 0.45 + project_score * 0.30 + consistency_score * 0.25, 1)

    return {
        "total_score": total_score,
        "dsa": {"score": round(dsa_score, 1), "weight": 45, "problems_solved": dsa_problems},
        "projects": {"score": round(project_score, 1), "weight": 30},
        "consistency": {"score": round(consistency_score, 1), "weight": 25, "streak": streak}
    }

# ======================== AI INSIGHTS ========================

@api_router.get("/insights")
async def get_insights(request: Request):
    user = await get_current_user(request)
    user_id = user["user_id"]

    # Check cached insights (valid for 6 hours)
    cached = await db.insights.find_one({"user_id": user_id}, {"_id": 0})
    if cached:
        generated_at = cached.get("generated_at", "")
        if generated_at:
            try:
                gen_time = datetime.fromisoformat(generated_at)
                if gen_time.tzinfo is None:
                    gen_time = gen_time.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - gen_time < timedelta(hours=6):
                    return cached
            except:
                pass

    platform_data_list = await db.platform_data.find({"user_id": user_id}, {"_id": 0}).to_list(10)

    if not platform_data_list:
        return {
            "user_id": user_id,
            "insights": ["Connect your coding platforms to get personalized insights!"],
            "weaknesses": [],
            "suggestions": [],
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

    # Build context for AI
    context_parts = []
    for pd in platform_data_list:
        if pd.get("platform") == "leetcode":
            context_parts.append(f"LeetCode: {pd.get('problems_solved', 0)} problems solved (Easy: {pd.get('easy', 0)}, Medium: {pd.get('medium', 0)}, Hard: {pd.get('hard', 0)}), Streak: {pd.get('streak', 0)} days, Rating: {pd.get('contest_rating', 0)}")
        elif pd.get("platform") == "github":
            context_parts.append(f"GitHub: {pd.get('total_repos', 0)} repos, {pd.get('total_commits', 0)} recent commits, {pd.get('total_stars', 0)} stars, Languages: {pd.get('languages', {})}")
        elif pd.get("platform") == "codeforces":
            context_parts.append(f"Codeforces: Rating {pd.get('rating', 0)}, Max Rating: {pd.get('max_rating', 0)}, Rank: {pd.get('rank', 'unrated')}, {pd.get('problems_solved', 0)} problems solved")
        elif pd.get("platform") == "codechef":
            context_parts.append(f"CodeChef: Rating {pd.get('rating', 0)}, Max Rating: {pd.get('max_rating', 0)}, Stars: {pd.get('stars', '0')}, {pd.get('problems_solved', 0)} problems solved")

    context = "\n".join(context_parts)

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(
            api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
            session_id=f"insights_{user_id}_{datetime.now(timezone.utc).strftime('%Y%m%d')}",
            system_message="You are DevSync AI, a developer growth analyst. Analyze coding activity data and provide actionable insights. Be specific and encouraging. Return JSON with keys: insights (array of 3-4 insight strings), weaknesses (array of 2-3 weakness strings), suggestions (array of 3-4 actionable suggestion strings)."
        ).with_model("openai", "gpt-5.2")

        user_message = UserMessage(text=f"Analyze this developer's coding activity and provide insights:\n\n{context}\n\nReturn valid JSON only.")
        response_text = await chat.send_message(user_message)

        # Parse JSON from response
        try:
            # Try to extract JSON from the response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                insights_data = json.loads(response_text[json_start:json_end])
            else:
                insights_data = {"insights": [response_text], "weaknesses": [], "suggestions": []}
        except json.JSONDecodeError:
            insights_data = {"insights": [response_text], "weaknesses": [], "suggestions": []}

    except Exception as e:
        logger.error(f"AI Insights error: {e}")
        insights_data = {
            "insights": [
                "Based on your activity, you're making steady progress!",
                "Consider practicing more medium and hard problems to improve.",
                "Regular coding habits will significantly boost your skills."
            ],
            "weaknesses": ["Could not generate AI insights at this time."],
            "suggestions": ["Connect more platforms for comprehensive analysis.", "Try solving at least one problem daily."]
        }

    result = {
        "user_id": user_id,
        "insights": insights_data.get("insights", []),
        "weaknesses": insights_data.get("weaknesses", []),
        "suggestions": insights_data.get("suggestions", []),
        "generated_at": datetime.now(timezone.utc).isoformat()
    }

    await db.insights.delete_many({"user_id": user_id})
    await db.insights.insert_one(result)
    result.pop("_id", None)

    return result

@api_router.post("/insights/regenerate")
async def regenerate_insights(request: Request):
    user = await get_current_user(request)
    await db.insights.delete_many({"user_id": user["user_id"]})
    # Redirect to get_insights
    return await get_insights(request)

# ======================== GOALS ========================

@api_router.get("/goals")
async def get_goals(request: Request):
    user = await get_current_user(request)
    goals = await db.goals.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(100)
    return {"goals": goals}

@api_router.post("/goals")
async def create_goal(goal: GoalCreate, request: Request):
    user = await get_current_user(request)
    goal_doc = {
        "goal_id": f"goal_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "title": goal.title,
        "description": goal.description,
        "target_value": goal.target_value,
        "current_value": 0,
        "category": goal.category,
        "completed": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.goals.insert_one(goal_doc)
    goal_doc.pop("_id", None)
    return goal_doc

@api_router.put("/goals/{goal_id}")
async def update_goal(goal_id: str, update: GoalUpdate, request: Request):
    user = await get_current_user(request)
    update_dict = {}
    if update.current_value is not None:
        update_dict["current_value"] = update.current_value
    if update.completed is not None:
        update_dict["completed"] = update.completed

    if not update_dict:
        raise HTTPException(status_code=400, detail="Nothing to update")

    result = await db.goals.update_one(
        {"goal_id": goal_id, "user_id": user["user_id"]},
        {"$set": update_dict}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Goal not found")

    goal = await db.goals.find_one({"goal_id": goal_id, "user_id": user["user_id"]}, {"_id": 0})
    return goal

@api_router.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str, request: Request):
    user = await get_current_user(request)
    result = await db.goals.delete_one({"goal_id": goal_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"message": "Goal deleted"}

@api_router.post("/goals/auto-generate")
async def auto_generate_goals(request: Request):
    user = await get_current_user(request)
    user_id = user["user_id"]

    platform_data_list = await db.platform_data.find({"user_id": user_id}, {"_id": 0}).to_list(10)

    goals = []
    for pd in platform_data_list:
        if pd.get("platform") == "leetcode":
            problems = pd.get("problems_solved", 0)
            goals.append({
                "goal_id": f"goal_{uuid.uuid4().hex[:12]}",
                "user_id": user_id,
                "title": f"Solve {max(10, (problems // 50 + 1) * 50 - problems)} more LeetCode problems",
                "description": f"You've solved {problems} problems. Push to the next milestone!",
                "target_value": max(10, (problems // 50 + 1) * 50 - problems),
                "current_value": 0,
                "category": "dsa",
                "completed": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            if pd.get("hard", 0) < 10:
                goals.append({
                    "goal_id": f"goal_{uuid.uuid4().hex[:12]}",
                    "user_id": user_id,
                    "title": "Solve 5 Hard LeetCode Problems",
                    "description": "Challenge yourself with hard problems to sharpen advanced skills.",
                    "target_value": 5,
                    "current_value": 0,
                    "category": "dsa",
                    "completed": False,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
        elif pd.get("platform") == "github":
            repos = pd.get("total_repos", 0)
            goals.append({
                "goal_id": f"goal_{uuid.uuid4().hex[:12]}",
                "user_id": user_id,
                "title": "Contribute to 3 Open Source Projects",
                "description": f"With {repos} repos, start contributing to the community.",
                "target_value": 3,
                "current_value": 0,
                "category": "projects",
                "completed": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        elif pd.get("platform") == "codeforces":
            rating = pd.get("rating", 0)
            target = ((rating // 100) + 1) * 100 if rating > 0 else 1200
            goals.append({
                "goal_id": f"goal_{uuid.uuid4().hex[:12]}",
                "user_id": user_id,
                "title": f"Reach Codeforces Rating {target}",
                "description": f"Current rating: {rating}. Push to the next level!",
                "target_value": target,
                "current_value": rating,
                "category": "dsa",
                "completed": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        elif pd.get("platform") == "codechef":
            rating = pd.get("rating", 0)
            target = ((rating // 100) + 1) * 100 if rating > 0 else 1200
            goals.append({
                "goal_id": f"goal_{uuid.uuid4().hex[:12]}",
                "user_id": user_id,
                "title": f"Reach CodeChef Rating {target}",
                "description": f"Current rating: {rating}. Keep competing!",
                "target_value": target,
                "current_value": rating,
                "category": "dsa",
                "completed": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })

    if not goals:
        goals.append({
            "goal_id": f"goal_{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "title": "Connect Your First Platform",
            "description": "Link LeetCode, GitHub, or Codeforces to start tracking your progress.",
            "target_value": 1,
            "current_value": 0,
            "category": "general",
            "completed": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    for g in goals:
        await db.goals.insert_one(g)
        g.pop("_id", None)

    return {"goals": goals}

# ======================== AUTO-SYNC SCHEDULER ========================

AUTO_SYNC_INTERVAL_HOURS = 6

async def auto_sync_all_platforms():
    """Background task: sync all connected platforms for all users every N hours."""
    while True:
        try:
            await asyncio.sleep(AUTO_SYNC_INTERVAL_HOURS * 3600)
            logger.info("Auto-sync: starting scheduled platform sync for all users")
            connections = await db.platform_connections.find({}, {"_id": 0}).to_list(10000)
            synced = 0
            for conn in connections:
                try:
                    await sync_platform_data(
                        conn["user_id"], conn["platform"],
                        conn["username"], conn.get("pat_token")
                    )
                    await db.platform_connections.update_one(
                        {"user_id": conn["user_id"], "platform": conn["platform"]},
                        {"$set": {"last_synced": datetime.now(timezone.utc).isoformat()}}
                    )
                    synced += 1
                except Exception as e:
                    logger.error(f"Auto-sync error for {conn['user_id']}/{conn['platform']}: {e}")
                # Rate limit: small delay between syncs
                await asyncio.sleep(2)
            logger.info(f"Auto-sync: completed {synced}/{len(connections)} platforms")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Auto-sync scheduler error: {e}")

# ======================== STARTUP ========================

@app.on_event("startup")
async def startup():
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.platform_connections.create_index([("user_id", 1), ("platform", 1)])
    await db.platform_data.create_index([("user_id", 1), ("platform", 1)])
    await db.user_sessions.create_index("session_token")
    await db.user_sessions.create_index("user_id")
    await db.login_attempts.create_index("identifier")
    await db.goals.create_index("user_id")
    await db.goals.create_index("goal_id")
    await db.insights.create_index("user_id")
    await db.password_reset_tokens.create_index("token")
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)

    # Seed admin
    await seed_admin()

    # Start auto-sync background task
    asyncio.create_task(auto_sync_all_platforms())

    logger.info("DevSync backend started!")

async def seed_admin():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@devsync.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")

    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "Admin",
            "role": "admin",
            "auth_provider": "email",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"Admin user created: {admin_email}")
    elif not verify_password(admin_password, existing.get("password_hash", "")):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}}
        )
        logger.info("Admin password updated")

    # Write test credentials
    os.makedirs("./memory", exist_ok=True)
    with open("./memory/test_credentials.md", "w") as f:
        f.write("# DevSync Test Credentials\n\n")
        f.write(f"## Admin Account\n- Email: {admin_email}\n- Password: {admin_password}\n- Role: admin\n\n")
        f.write("## Auth Endpoints\n- POST /api/auth/register\n- POST /api/auth/login\n- POST /api/auth/logout\n- GET /api/auth/me\n- POST /api/auth/refresh\n- POST /api/auth/google/session\n")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# Include the router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
