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
from jose import jwt, JWTError, ExpiredSignatureError
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from bson import ObjectId
import google.generativeai as genai

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Gmail SMTP setup
SMTP_EMAIL = os.environ.get("SMTP_EMAIL", "")
SMTP_APP_PASSWORD = os.environ.get("SMTP_APP_PASSWORD", "")

def send_email_smtp(to_email: str, subject: str, html_content: str):
    """Send an email via Gmail SMTP. Works with any recipient."""
    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        logger.error("SMTP_EMAIL or SMTP_APP_PASSWORD not configured in .env")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"DevSync <{SMTP_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False

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

class GitHubOAuthCallbackRequest(BaseModel):
    code: str

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
async def register(req: RegisterRequest):
    email = req.email.strip().lower()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Generate unique username
    base_username = "".join(c for c in req.name.strip().lower() if c.isalnum())
    if not base_username:
        base_username = "user"
    
    import random
    while True:
        suffix = f"{random.randint(1000, 9999)}"
        username = f"{base_username}{suffix}"
        if not await db.users.find_one({"username": username}):
            break

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    password_hash = hash_password(req.password)

    user_doc = {
        "user_id": user_id,
        "username": username,
        "email": email,
        "name": req.name.strip(),
        "password_hash": password_hash,
        "role": "user",
        "email_verified": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "auth_provider": "email"
    }
    await db.users.insert_one(user_doc)

    verify_token = f"{random.randint(100000, 999999)}"
    await db.email_verifications.insert_one({
        "user_id": user_id,
        "token": verify_token,
        "verified": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    html_content = f"""
    <div style="font-family: sans-serif; padding: 20px;">
        <h2>Verify your email</h2>
        <p>Hi {req.name.strip()},</p>
        <p>Your verification code is:</p>
        <div style="font-size: 24px; font-weight: bold; background: #f3f4f6; padding: 10px; display: inline-block; letter-spacing: 2px;">{verify_token}</div>
        <p>Please enter this code on the verification page to activate your account.</p>
    </div>
    """
    try:
        await asyncio.to_thread(send_email_smtp, email, "DevSync - Verify your email", html_content)
    except Exception as e:
        logger.error(f"Failed to send verification email to {email}: {e}")

    return {
        "message": "Account created. Please check your email to verify your account."
    }

class VerifyEmailRequest(BaseModel):
    email: str
    code: str

@api_router.post("/auth/verify-email")
async def verify_email(req: VerifyEmailRequest):
    email = req.email.strip().lower()
    user = await db.users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    verification = await db.email_verifications.find_one({
        "user_id": user["user_id"], 
        "token": req.code.strip(), 
        "verified": False
    })
    
    if not verification:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")
    
    await db.email_verifications.update_one({"_id": verification["_id"]}, {"$set": {"verified": True}})
    await db.users.update_one({"user_id": verification["user_id"]}, {"$set": {"email_verified": True}})
    return {"message": "Email verified successfully."}

class ResendVerificationRequest(BaseModel):
    email: str

@api_router.post("/auth/resend-verification")
async def resend_verification(req: ResendVerificationRequest):
    email = req.email.strip().lower()
    user = await db.users.find_one({"email": email, "auth_provider": "email"})
    if not user:
        return {"message": "If this email is registered, a verification link has been sent."}
    
    if user.get("email_verified"):
        return {"message": "Email is already verified."}

    import random
    verify_token = f"{random.randint(100000, 999999)}"
    await db.email_verifications.insert_one({
        "user_id": user["user_id"],
        "token": verify_token,
        "verified": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    html_content = f"""
    <div style="font-family: sans-serif; padding: 20px;">
        <h2>Verify your email</h2>
        <p>Hi {user.get('name', 'Developer')},</p>
        <p>Your new verification code is:</p>
        <div style="font-size: 24px; font-weight: bold; background: #f3f4f6; padding: 10px; display: inline-block; letter-spacing: 2px;">{verify_token}</div>
    </div>
    """
    try:
        await asyncio.to_thread(send_email_smtp, email, "DevSync - Verify your email", html_content)
    except Exception as e:
        logger.error(f"Failed to send verification email to {email}: {e}")

    return {"message": "If this email is registered, a verification link has been sent."}

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

    if user.get("auth_provider") == "email" and not user.get("email_verified", True):
        raise HTTPException(status_code=403, detail="Please verify your email before signing in. Check your inbox.")

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
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

# ======================== PASSWORD RESET ========================

async def send_reset_email(email: str, token: str, user_name: str):
    """Send password reset email via Gmail SMTP."""
    html_content = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 560px; margin: 0 auto; padding: 40px 20px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <div style="display: inline-block; background: #3B82F6; color: white; font-weight: bold; font-size: 18px; width: 44px; height: 44px; line-height: 44px; border-radius: 10px;">DS</div>
            <h1 style="font-size: 24px; color: #09090B; margin: 16px 0 0;">DevSync</h1>
        </div>
        <h2 style="font-size: 20px; color: #09090B; margin-bottom: 8px;">Reset your password</h2>
        <p style="color: #52525B; font-size: 15px; line-height: 1.6;">Hi {user_name},</p>
        <p style="color: #52525B; font-size: 15px; line-height: 1.6;">We received a request to reset your password. Use the 6-digit code below to set a new password:</p>
        <div style="background: #F4F4F5; border: 1px solid #E4E4E7; border-radius: 8px; padding: 16px; text-align: center; margin: 24px 0;">
            <code style="font-size: 24px; font-weight: 600; color: #09090B; letter-spacing: 2px; word-break: break-all;">{token}</code>
        </div>
        <p style="color: #52525B; font-size: 15px; line-height: 1.6;">Enter this code in the password reset form on DevSync.</p>
        <p style="color: #A1A1AA; font-size: 13px; margin-top: 32px;">This code expires in 1 hour. If you didn't request a password reset, you can safely ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #E4E4E7; margin: 24px 0;" />
        <p style="color: #A1A1AA; font-size: 12px; text-align: center;">DevSync - Track your developer journey</p>
    </div>
    """

    return await asyncio.to_thread(send_email_smtp, email, "DevSync - Password Reset", html_content)

@api_router.post("/auth/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    email = req.email.strip().lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    # Always return success to prevent email enumeration
    # Only skip users that have NO password_hash (pure Google-only accounts)
    if not user or not user.get("password_hash"):
        return {"message": "If an account exists with that email, a reset link has been sent."}

    import random
    token = f"{random.randint(100000, 999999)}"
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

    logger.debug(f"DEV ONLY reset token: {token}")

    response_data = {"message": "If an account exists with that email, a reset token has been sent."}
    if not email_sent:
        response_data["error"] = "Email delivery failed, please check your RESEND_API_KEY config"

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

# ======================== CHANGE PASSWORD ========================

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@api_router.post("/auth/change-password")
async def change_password(req: ChangePasswordRequest, request: Request):
    user = await get_current_user(request)
    
    full_user = await db.users.find_one({"user_id": user["user_id"]})
    if not full_user or not full_user.get("password_hash"):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
        
    if not verify_password(req.current_password, full_user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
        
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        
    new_hash = hash_password(req.new_password)
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"password_hash": new_hash}}
    )
    
    return {"message": "Password changed successfully"}

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

class CheckUsernameRequest(BaseModel):
    username: str

@api_router.post("/auth/check-username")
async def check_username(req: CheckUsernameRequest):
    import re
    username = req.username.strip().lower()
    if not re.match(r"^[a-z0-9_]{3,20}$", username):
        return {"available": False, "error": "Username must be 3-20 chars, lowercase letters, numbers, and underscores only."}
    
    existing = await db.users.find_one({"username": username})
    if existing:
        return {"available": False}
    return {"available": True}

class UpdateUsernameRequest(BaseModel):
    username: str

@api_router.patch("/user/username")
async def update_username(req: UpdateUsernameRequest, request: Request):
    user = await get_current_user(request)
    import re
    username = req.username.strip().lower()
    if not re.match(r"^[a-z0-9_]{3,20}$", username):
        raise HTTPException(status_code=400, detail="Username must be 3-20 chars, lowercase letters, numbers, and underscores only.")
        
    existing = await db.users.find_one({"username": username})
    if existing and existing["user_id"] != user["user_id"]:
        raise HTTPException(status_code=400, detail="Username is already taken")
        
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"username": username}}
    )
    return {"message": "Username updated successfully"}

# ======================== GOOGLE OAUTH (NATIVE) ========================

class GoogleSessionRequest(BaseModel):
    email: str
    name: Optional[str] = None
    picture: Optional[str] = ""
    access_token: str

@api_router.post("/auth/google/session")
async def google_session(req: GoogleSessionRequest, response: Response):
    # Verify the access_token by calling Google's userinfo endpoint
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        resp = await http_client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {req.access_token}"}
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Google access token")
        google_data = resp.json()

    # Verify the email from token matches what was sent
    verified_email = google_data.get("email", "").lower()
    if not verified_email or verified_email != req.email.strip().lower():
        raise HTTPException(status_code=401, detail="Email mismatch — token verification failed")

    email = verified_email
    name = google_data.get("name") or req.name or email.split("@")[0]
    picture = google_data.get("picture") or req.picture or ""
    session_token_value = secrets.token_urlsafe(32)

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

@api_router.post("/platforms/github/oauth/callback")
async def github_oauth_callback(req: GitHubOAuthCallbackRequest, request: Request):
    user = await get_current_user(request)
    user_id = user["user_id"]

    client_id = os.environ.get("GITHUB_CLIENT_ID")
    client_secret = os.environ.get("GITHUB_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="GitHub OAuth is not configured on the server")

    # Exchange code for access_token
    async with httpx.AsyncClient() as http_client:
        resp = await http_client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": req.code
            }
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get GitHub access token")
            
        token_data = resp.json()
        access_token = token_data.get("access_token")
        
        if not access_token:
            raise HTTPException(status_code=400, detail=f"GitHub OAuth error: {token_data.get('error_description', 'No access token')}")

        # Use access_token to fetch user info
        user_resp = await http_client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {access_token}", "Accept": "application/vnd.github.v3+json"}
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch GitHub profile")
            
        gh_user = user_resp.json()
        gh_username = gh_user.get("login")
        
        if not gh_username:
            raise HTTPException(status_code=400, detail="Failed to get GitHub username")

        # Delete existing connection
        await db.platform_connections.delete_many({"user_id": user_id, "platform": "github"})

        connection = {
            "connection_id": f"conn_{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "platform": "github",
            "username": gh_username,
            "pat_token": access_token,
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "last_synced": None,
            "status": "connected"
        }
        await db.platform_connections.insert_one(connection)

        # Initial sync
        sync_data = await sync_platform_data(user_id, "github", gh_username, access_token)

        return {"message": "GitHub connected successfully via OAuth", "connection": {k: v for k, v in connection.items() if k != "_id"}, "sync_data": sync_data}

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
        
        # Auto-update goals based on new stats
        asyncio.create_task(auto_update_goals_progress(user_id))
        
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

        total_commits = 0
        contribution_calendar = {}
        weekly_commits = {}

        graphql_query = """
        {
          user(login: "%s") {
            contributionsCollection {
              contributionCalendar {
                totalContributions
                weeks {
                  contributionDays {
                    date
                    contributionCount
                  }
                }
              }
            }
          }
        }
        """ % username

        graphql_headers = {"Authorization": f"bearer {pat_token}"} if pat_token else {"Authorization": ""}
        try:
            graphql_resp = await http_client.post(
                "https://api.github.com/graphql",
                json={"query": graphql_query},
                headers=graphql_headers,
                timeout=15.0
            )
            if graphql_resp.status_code == 200:
                cal_data = graphql_resp.json()["data"]["user"]["contributionsCollection"]["contributionCalendar"]
                total_commits = cal_data["totalContributions"]
                for week in cal_data["weeks"]:
                    for day in week["contributionDays"]:
                        date_str = day["date"]
                        count = day["contributionCount"]
                        contribution_calendar[date_str] = count
                        weekly_commits[date_str] = count
            else:
                # Fallback to events REST API if GraphQL fails
                events_resp = await http_client.get(f"https://api.github.com/users/{username}/events?per_page=100", headers=headers)
                events = events_resp.json() if events_resp.status_code == 200 else []
                for event in events:
                    if isinstance(event, dict) and event.get("type") == "PushEvent":
                        commits_count = len(event.get("payload", {}).get("commits", []))
                        total_commits += commits_count
                        created = event.get("created_at", "")[:10]
                        weekly_commits[created] = weekly_commits.get(created, 0) + commits_count
        except Exception as e:
            logger.warning(f"GraphQL failed, falling back: {e}")


        return {
            "total_repos": user_info.get("public_repos", 0),
            "total_stars": total_stars,
            "followers": user_info.get("followers", 0),
            "following": user_info.get("following", 0),
            "total_commits": total_commits,
            "languages": languages,
            "weekly_commits": weekly_commits,
            "contribution_calendar": contribution_calendar,
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
            "weekday": (d.weekday() + 1) % 7,
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

    days = request.query_params.get("days")
    from_date = request.query_params.get("from")
    to_date = request.query_params.get("to")

    today = datetime.now(timezone.utc).date()
    start_date = None
    end_date = today

    if from_date and to_date:
        try:
            start_date = datetime.strptime(from_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(to_date, "%Y-%m-%d").date()
        except:
            pass
    elif days and days.isdigit():
        start_date = today - timedelta(days=int(days))

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
                    dt_date = dt.date()
                    if start_date and (dt_date < start_date or dt_date > end_date):
                        continue
                    weekly_data[day_key] = weekly_data.get(day_key, 0) + count
                except:
                    pass
        elif pd.get("platform") == "github":
            wc = pd.get("weekly_commits", {})
            for day_key, count in wc.items():
                try:
                    dt_date = datetime.strptime(day_key, "%Y-%m-%d").date()
                    if start_date and (dt_date < start_date or dt_date > end_date):
                        continue
                    weekly_data[day_key] = weekly_data.get(day_key, 0) + count
                    total_commits += count
                except:
                    weekly_data[day_key] = weekly_data.get(day_key, 0) + count
                    total_commits += count
        elif pd.get("platform") == "codeforces":
            total_problems += pd.get("problems_solved", 0)
        elif pd.get("platform") == "codechef":
            total_problems += pd.get("problems_solved", 0)

    # Build weekly graph (based on selected period, max 7 days for the chart)
    graph_days = int(days) if days and days.isdigit() and int(days) <= 7 else 7
    if from_date and to_date and start_date:
        graph_days = min(7, (end_date - start_date).days + 1)
        
    weekly_graph = []
    for i in range(graph_days - 1, -1, -1):
        d = end_date - timedelta(days=i)
        day_key = d.strftime("%Y-%m-%d")
        weekly_graph.append({
            "date": day_key,
            "day": d.strftime("%a"),
            "activity": weekly_data.get(day_key, 0)
        })

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

# CLOUD AI — powered by Google Gemini

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

async def call_gemini(prompt: str, expect_json: bool = False) -> str:
    """Call Google Gemini LLM. Returns empty string if unavailable."""
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        logger.warning("GEMINI_API_KEY not configured, using static fallback.")
        return ""
        
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # If we expect JSON, Gemini 1.5 supports JSON mode
        generation_config = {"response_mime_type": "application/json"} if expect_json else None
        
        response = await model.generate_content_async(
            prompt,
            generation_config=generation_config
        )
        
        result = response.text.strip()
        if expect_json:
            # Strip markdown code fences if present just in case
            result = result.replace("```json", "").replace("```", "").strip()
        return result
    except Exception as e:
        logger.error(f"Gemini AI error: {e}")
    return ""

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

    # Generate AI recommendations for each score component
    dsa_rec = f"You've solved {dsa_problems} DSA problems. Keep pushing to reach 300 for a perfect score!"
    projects_rec = "Build more projects and push commits regularly to boost your project score."
    consistency_rec = f"Your current streak is {streak} days. Aim for a 30-day streak to maximize consistency!"

    prompt = f"""You are DevSync AI. Give a short 1-2 sentence personalized recommendation for each of these readiness score components. Return ONLY valid JSON with keys: dsa, projects, consistency.

Scores:
- DSA score: {round(dsa_score, 1)}/100 ({dsa_problems} problems solved)
- Projects score: {round(project_score, 1)}/100
- Consistency score: {round(consistency_score, 1)}/100 (streak: {streak} days)

Return ONLY the JSON object."""
    
    response_text = await call_gemini(prompt, expect_json=True)
    if response_text:
        try:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                recs = json.loads(response_text[json_start:json_end])
                dsa_rec = recs.get("dsa", dsa_rec)
                projects_rec = recs.get("projects", projects_rec)
                consistency_rec = recs.get("consistency", consistency_rec)
        except Exception as e:
            logger.error(f"Readiness AI parse error: {e}")

    return {
        "total_score": total_score,
        "dsa": {"score": round(dsa_score, 1), "weight": 45, "problems_solved": dsa_problems, "ai_recommendation": dsa_rec},
        "projects": {"score": round(project_score, 1), "weight": 30, "ai_recommendation": projects_rec},
        "consistency": {"score": round(consistency_score, 1), "weight": 25, "streak": streak, "ai_recommendation": consistency_rec}
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
    
    logger.info(f"Generating insights for user {user_id} with {len(platform_data_list)} platforms")

    # LOCAL AI — powered by Ollama (https://ollama.com)
    prompt = f"""You are DevSync AI, a developer growth analyst. Analyze this developer's data.

Developer Stats:
{context}

Return ONLY a valid JSON object with exactly these three keys:
- "insights": array of exactly 3 strings — specific strengths based on their actual numbers
- "weaknesses": array of exactly 2 strings — specific areas needing improvement  
- "suggestions": array of exactly 3 strings — concrete actionable steps for this week (mention specific numbers)

Rules:
- Reference actual numbers from their stats (e.g. "You've solved 45 medium problems")
- Suggestions must be specific (e.g. "Solve 3 medium graph problems" not "practice graphs")
- Be encouraging but honest
- Return ONLY the JSON object. No markdown. No explanation. No code fences."""

    response_text = await call_gemini(prompt, expect_json=True)
    insights_data = None
    
    if response_text:
        try:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                insights_data = json.loads(response_text[json_start:json_end])
        except Exception:
            pass

    if not insights_data or not insights_data.get("insights"):
        # Static fallback — always works
        insights_data = {
            "insights": [
                "You've been consistently active across your connected platforms.",
                "Your problem-solving history shows steady growth.",
                "Keep your current streak going — consistency is your biggest asset."
            ],
            "weaknesses": [
                "Connect more platforms for deeper AI analysis.",
                "Try solving harder difficulty problems to level up."
            ],
            "suggestions": [
                "Solve at least 1 medium difficulty problem today.",
                "Make at least 1 GitHub commit this week.",
                "Attempt one Codeforces contest this weekend."
            ]
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
    try:
        user = await get_current_user(request)
        
        # Auto-update progress based on latest platform data before fetching
        await auto_update_goals_progress(user["user_id"])
        
        goals = await db.goals.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(100)
        return {"goals": goals}
    except Exception as e:
        logger.error(f"Error fetching goals: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error fetching goals")

@api_router.post("/goals")
async def create_goal(goal: GoalCreate, request: Request):
    try:
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
    except Exception as e:
        logger.error(f"Error creating goal: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error creating goal")

@api_router.put("/goals/{goal_id}")
async def update_goal(goal_id: str, update: GoalUpdate, request: Request):
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating goal {goal_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error updating goal")

@api_router.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str, request: Request):
    try:
        user = await get_current_user(request)
        result = await db.goals.delete_one({"goal_id": goal_id, "user_id": user["user_id"]})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Goal not found")
        return {"message": "Goal deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting goal {goal_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error deleting goal")

async def generate_new_goals_for_user(user_id: str) -> dict:
    platform_data_list = await db.platform_data.find({"user_id": user_id}, {"_id": 0}).to_list(10)
    
    easy = 0
    medium = 0
    hard = 0
    cf_rating = 0

    for pd in platform_data_list:
        if pd.get("platform") == "leetcode":
            easy = pd.get("easy", 0)
            medium = pd.get("medium", 0)
            hard = pd.get("hard", 0)
        elif pd.get("platform") == "codeforces":
            cf_rating = max(cf_rating, pd.get("rating", 0))

    total_lc = easy + medium + hard
    if total_lc > 200 or cf_rating > 1600:
        level = "Advanced"
    elif (total_lc >= 50 and total_lc <= 200) or (cf_rating >= 1000 and cf_rating <= 1600):
        level = "Intermediate"
    else:
        level = "Beginner"

    beginner_goals = [
        {"title": "Solve 50 Easy Problems", "category": "dsa", "target_value": 50, "description": "Build your foundation with easy problems"},
        {"title": "Set Up GitHub Profile", "category": "projects", "target_value": 1, "description": "Create a professional GitHub presence"},
        {"title": "7-Day Coding Streak", "category": "consistency", "target_value": 7, "description": "Code every day for a week"},
        {"title": "Solve First Medium Problem", "category": "dsa", "target_value": 1, "description": "Level up beyond easy problems"},
        {"title": "Create Your First Repository", "category": "projects", "target_value": 1, "description": "Start building your portfolio"},
        {"title": "Register on Codeforces", "category": "dsa", "target_value": 1, "description": "Join competitive programming"},
        {"title": "Solve 10 Array Problems", "category": "dsa", "target_value": 10, "description": "Master the most common interview topic"},
        {"title": "30-Day Coding Streak", "category": "consistency", "target_value": 30, "description": "Build an unstoppable habit"}
    ]

    intermediate_goals = [
        {"title": "Solve 100 Medium Problems", "category": "dsa", "target_value": 100, "description": "Tackle interview-level challenges"},
        {"title": "Reach Codeforces Rating 1200", "category": "dsa", "target_value": 1200, "description": "Hit Specialist rank on Codeforces"},
        {"title": "Build 3 Portfolio Projects", "category": "projects", "target_value": 3, "description": "Show employers what you can build"},
        {"title": "Solve 20 Hard Problems", "category": "dsa", "target_value": 20, "description": "Push your limits with hard problems"},
        {"title": "100 GitHub Commits This Month", "category": "projects", "target_value": 100, "description": "Show consistent coding activity"},
        {"title": "Participate in 5 CF Contests", "category": "dsa", "target_value": 5, "description": "Compete and improve under pressure"},
        {"title": "Master Dynamic Programming", "category": "dsa", "target_value": 15, "description": "Solve 15 DP problems"},
        {"title": "60-Day Coding Streak", "category": "consistency", "target_value": 60, "description": "Two months of daily coding"}
    ]

    advanced_goals = [
        {"title": "Reach Codeforces Expert (1600+)", "category": "dsa", "target_value": 1600, "description": "Hit Expert rank on Codeforces"},
        {"title": "Solve 50 Hard LeetCode Problems", "category": "dsa", "target_value": 50, "description": "Master the hardest interview questions"},
        {"title": "Open Source Contribution", "category": "projects", "target_value": 5, "description": "Contribute to 5 open source projects"},
        {"title": "LeetCode Contest Rating 1800+", "category": "dsa", "target_value": 1800, "description": "Compete at a high level on LeetCode"},
        {"title": "Build a Full-Stack Project", "category": "projects", "target_value": 1, "description": "Ship a complete product"},
        {"title": "Solve 500 Total Problems", "category": "dsa", "target_value": 500, "description": "Reach 500 total problems solved"},
        {"title": "100-Day Coding Streak", "category": "consistency", "target_value": 100, "description": "Elite-level consistency"},
        {"title": "Mentor a Junior Developer", "category": "projects", "target_value": 1, "description": "Give back to the community"}
    ]

    presets = beginner_goals
    if level == "Intermediate":
        presets = intermediate_goals
    elif level == "Advanced":
        presets = advanced_goals

    existing_goals = await db.goals.find({"user_id": user_id}).to_list(100)
    existing_titles = [g["title"] for g in existing_goals]

    new_goals = []
    for p in presets:
        if p["title"] not in existing_titles:
            goal_id = f"goal_{uuid.uuid4().hex[:12]}"
            
            # Request Ollama for personalized description
            prompt = f"User has solved {easy} easy, {medium} medium, {hard} hard LeetCode problems. CF rating: {cf_rating}.\nThey have a new goal: \"{p['title']}\". Write ONE motivational sentence (max 15 words) for why this goal matters for them specifically.\nReturn only the sentence."
            ai_desc = await call_gemini(prompt, expect_json=False)
            desc = ai_desc.strip() if ai_desc else p["description"]
            
            goal_doc = {
                "goal_id": goal_id,
                "user_id": user_id,
                "title": p["title"],
                "description": desc,
                "target_value": p["target_value"],
                "current_value": 0,
                "category": p["category"],
                "completed": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            new_goals.append(goal_doc)

    for g in new_goals:
        await db.goals.update_one(
            {"user_id": user_id, "title": g["title"]},
            {"$setOnInsert": g},
            upsert=True
        )
        g.pop("_id", None)

    return {"goals": new_goals}

async def auto_update_goals_progress(user_id: str):
    """Automatically updates goal progress based on latest platform data."""
    try:
        platform_data_list = await db.platform_data.find({"user_id": user_id}, {"_id": 0}).to_list(10)
        connections = await db.platform_connections.find({"user_id": user_id}, {"_id": 0}).to_list(10)
        active_goals = await db.goals.find({"user_id": user_id, "completed": False}).to_list(100)

        if not active_goals:
            return

        # Calculate streak from aggregated calendar
        heatmap = {}
        for pd in platform_data_list:
            if pd.get("platform") == "leetcode":
                cal = pd.get("submission_calendar", {})
                for ts_str, count in cal.items():
                    try:
                        dt = datetime.fromtimestamp(int(ts_str), tz=timezone.utc).date()
                        day_key = dt.strftime("%Y-%m-%d")
                        heatmap[day_key] = heatmap.get(day_key, 0) + count
                    except:
                        pass
            elif pd.get("platform") == "github":
                wc = pd.get("weekly_commits", {})
                for day, count in wc.items():
                    heatmap[day] = heatmap.get(day, 0) + count

        today = datetime.now(timezone.utc).date()
        current_streak = 0
        current_date = today
        while True:
            day_key = current_date.strftime("%Y-%m-%d")
            if heatmap.get(day_key, 0) > 0:
                current_streak += 1
                current_date -= timedelta(days=1)
            elif current_date == today:
                # If no activity today, check yesterday before breaking
                current_date -= timedelta(days=1)
            else:
                break

        # Calculate metrics
        metrics = {
            "easy": 0, "medium": 0, "hard": 0, "total_lc": 0,
            "cf_rating": 0, "cf_contests": 0,
            "gh_repos": 0, "gh_commits_30d": 0, "gh_commits_total": 0,
            "streak": current_streak,
            "gh_connected": any(c.get("platform") == "github" for c in connections),
            "cf_connected": any(c.get("platform") == "codeforces" for c in connections)
        }

        for pd in platform_data_list:
            if pd.get("platform") == "leetcode":
                metrics["easy"] = pd.get("easy", 0)
                metrics["medium"] = pd.get("medium", 0)
                metrics["hard"] = pd.get("hard", 0)
                metrics["total_lc"] = metrics["easy"] + metrics["medium"] + metrics["hard"]
            elif pd.get("platform") == "codeforces":
                metrics["cf_rating"] = max(metrics["cf_rating"], pd.get("rating", 0))
                metrics["cf_contests"] = pd.get("contests_participated", 0)
            elif pd.get("platform") == "github":
                metrics["gh_repos"] = pd.get("total_repos", 0)
                metrics["gh_commits_total"] = pd.get("total_commits", 0)
                # Calculate commits in last 30 days
                wc = pd.get("weekly_commits", {})
                thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).date()
                recent_commits = sum(count for date_str, count in wc.items() if datetime.strptime(date_str, "%Y-%m-%d").date() >= thirty_days_ago)
                metrics["gh_commits_30d"] = recent_commits

        # Map metrics to specific goal titles (or patterns)
        def get_metric_for_goal(title: str) -> int:
            title_lower = title.lower()
            if "easy problem" in title_lower:
                return metrics["easy"]
            if "medium problem" in title_lower:
                return metrics["medium"]
            if "hard problem" in title_lower:
                return metrics["hard"]
            if "total problem" in title_lower:
                return metrics["total_lc"]
            if "codeforces rating" in title_lower or "codeforces expert" in title_lower:
                return metrics["cf_rating"]
            if "cf contest" in title_lower:
                return metrics["cf_contests"]
            if "github commits" in title_lower and "month" in title_lower:
                return metrics["gh_commits_30d"]
            if "portfolio project" in title_lower or "open source" in title_lower or "first repository" in title_lower or "full-stack project" in title_lower:
                return metrics["gh_repos"]
            if "streak" in title_lower:
                return metrics["streak"]
            if "set up github" in title_lower:
                return 1 if metrics["gh_connected"] else 0
            if "register on codeforces" in title_lower:
                return 1 if metrics["cf_connected"] else 0
            # For legacy dynamic goals like "Solve 27 more LeetCode problems" we can't accurately auto-update 
            # without knowing the starting baseline, so we skip them.
            return -1

        any_completed = False
        for goal in active_goals:
            new_val = get_metric_for_goal(goal["title"])
            if new_val >= 0 and new_val != goal.get("current_value"):
                is_completed = new_val >= goal["target_value"]
                if is_completed:
                    any_completed = True
                
                await db.goals.update_one(
                    {"_id": goal["_id"]},
                    {"$set": {
                        "current_value": new_val,
                        "completed": is_completed
                    }}
                )

        if any_completed:
            # Generate new goals automatically to replace the completed ones
            await generate_new_goals_for_user(user_id)
            
    except Exception as e:
        logger.error(f"Error in auto_update_goals_progress: {e}", exc_info=True)

@api_router.post("/goals/auto-generate")
async def auto_generate_goals(request: Request):
    user = await get_current_user(request)
    return await generate_new_goals_for_user(user["user_id"])

@api_router.get("/goals/progress-analysis")
async def get_goal_progress_analysis(request: Request):
    user = await get_current_user(request)
    goals = await db.goals.find({"user_id": user["user_id"], "completed": False}).to_list(10)
    
    if not goals:
        return {"tips": {}}

    goals_list_str = "\n".join([f"- {g['title']}: {g['current_value']}/{g['target_value']}" for g in goals])
    
    prompt = f"""You are DevSync AI, a motivational developer coach. Give a short, encouraging 1-sentence tip on how to make progress for each of the following active goals. Return ONLY a valid JSON object where keys are the exact goal titles and values are the string tips.

Goals:
{goals_list_str}

Return ONLY the JSON object, no markdown."""

    response_text = await call_gemini(prompt, expect_json=True)
    tips = {}
    if response_text:
        try:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                tips = json.loads(response_text[json_start:json_end])
        except Exception:
            pass

    return {"tips": tips}

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

# ======================== PROBLEMS ========================

@api_router.get("/problems/recommendations")
async def get_problem_recommendations(request: Request):
    user = await get_current_user(request)
    platform_data_list = await db.platform_data.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(10)
    
    solved_docs = await db.solved_problems.find({"user_id": user["user_id"]}).to_list(1000)
    solved_slugs = {doc["slug"] for doc in solved_docs}

    # Check cached problems (valid for 24 hours)
    cached = await db.problem_recommendations.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if cached:
        generated_at = cached.get("generated_at", "")
        if generated_at:
            try:
                gen_time = datetime.fromisoformat(generated_at)
                if gen_time.tzinfo is None:
                    gen_time = gen_time.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - gen_time < timedelta(hours=24):
                    recs = cached.get("recommendations", [])
                    # Append solved status
                    for r in recs:
                        r["solved"] = r.get("slug") in solved_slugs
                    return {"recommendations": recs, "level": cached.get("level", "Beginner")}
            except:
                pass

    easy = 0
    medium = 0
    hard = 0
    cf_rating = 0

    for pd in platform_data_list:
        if pd.get("platform") == "leetcode":
            easy = pd.get("easy", 0)
            medium = pd.get("medium", 0)
            hard = pd.get("hard", 0)
        elif pd.get("platform") == "codeforces":
            cf_rating = pd.get("rating", 0)

    # Determine user level
    if hard > 30 or cf_rating > 1600:
        level = "Advanced"
    elif medium > 100 and (hard >= 10 and hard <= 30):
        level = "Hard-Intermediate"
    elif (medium >= 30 and medium <= 100) and hard < 10:
        level = "Intermediate"
    elif (easy >= 50 and easy <= 150) and medium < 30:
        level = "Easy-Intermediate"
    else:
        level = "Beginner"

    prompt = f"""A developer has solved {easy} easy, {medium} medium, {hard} hard LeetCode problems.
Codeforces rating: {cf_rating}. Their level is: {level}.

Recommend exactly 10 LeetCode problems appropriate for their level.
Vary the topics: include Arrays, Strings, Trees, Graphs, DP, Binary Search, Stack/Queue, Greedy, Backtracking, Math.

Return ONLY a JSON array of exactly 10 objects. Each object must have:
- "title": exact LeetCode problem title
- "difficulty": "Easy", "Medium", or "Hard"  
- "topic": main topic category
- "reason": one specific sentence (max 12 words) why this fits their level
- "slug": the leetcode URL slug (e.g. "two-sum", "longest-substring-without-repeating-characters")

No markdown. No explanation. Only the JSON array."""

    response_text = await call_gemini(prompt, expect_json=True)
    recs = []
    
    if response_text:
        try:
            json_start = response_text.find("[")
            json_end = response_text.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                recs = json.loads(response_text[json_start:json_end])
        except Exception as e:
            logger.error(f"Problem recommendations parse error: {e}")

    if not recs or len(recs) == 0:
        # Static fallback
        if level in ("Beginner", "Easy-Intermediate"):
            recs = [
                {"title": "Two Sum", "difficulty": "Easy", "topic": "Arrays", "slug": "two-sum", "reason": "Fundamental hash map pattern."},
                {"title": "Valid Anagram", "difficulty": "Easy", "topic": "Strings", "slug": "valid-anagram", "reason": "Great for learning character counting."},
                {"title": "Binary Search", "difficulty": "Easy", "topic": "Binary Search", "slug": "binary-search", "reason": "Core algorithm every developer needs."},
                {"title": "Reverse Linked List", "difficulty": "Easy", "topic": "Linked List", "slug": "reverse-linked-list", "reason": "Essential pointer manipulation practice."},
                {"title": "Best Time to Buy and Sell Stock", "difficulty": "Easy", "topic": "Arrays", "slug": "best-time-to-buy-and-sell-stock", "reason": "Introduction to sliding window approach."},
                {"title": "Merge Two Sorted Lists", "difficulty": "Easy", "topic": "Linked List", "slug": "merge-two-sorted-lists", "reason": "Good practice for list merging."},
                {"title": "Valid Parentheses", "difficulty": "Easy", "topic": "Stack", "slug": "valid-parentheses", "reason": "Classic stack problem."},
                {"title": "Climbing Stairs", "difficulty": "Easy", "topic": "Dynamic Programming", "slug": "climbing-stairs", "reason": "Learn basic DP transitions."},
                {"title": "Maximum Subarray", "difficulty": "Medium", "topic": "Dynamic Programming", "slug": "maximum-subarray", "reason": "Kadane's algorithm is a must-know."},
                {"title": "Contains Duplicate", "difficulty": "Easy", "topic": "Arrays", "slug": "contains-duplicate", "reason": "Learn to use hash sets."}
            ]
        elif level in ("Intermediate", "Hard-Intermediate"):
            recs = [
                {"title": "Number of Islands", "difficulty": "Medium", "topic": "Graphs", "slug": "number-of-islands", "reason": "Classic BFS/DFS traversal problem."},
                {"title": "Coin Change", "difficulty": "Medium", "topic": "Dynamic Programming", "slug": "coin-change", "reason": "Introduction to 1D DP."},
                {"title": "Trie (Prefix Tree)", "difficulty": "Medium", "topic": "Trie", "slug": "implement-trie-prefix-tree", "reason": "Important data structure for string search."},
                {"title": "Course Schedule", "difficulty": "Medium", "topic": "Graphs", "slug": "course-schedule", "reason": "Learn topological sort."},
                {"title": "Longest Substring Without Repeating Characters", "difficulty": "Medium", "topic": "Strings", "slug": "longest-substring-without-repeating-characters", "reason": "Essential sliding window problem."},
                {"title": "3Sum", "difficulty": "Medium", "topic": "Arrays", "slug": "3sum", "reason": "Two pointers approach on sorted arrays."},
                {"title": "Binary Tree Level Order Traversal", "difficulty": "Medium", "topic": "Trees", "slug": "binary-tree-level-order-traversal", "reason": "Learn BFS on trees."},
                {"title": "Word Break", "difficulty": "Medium", "topic": "Dynamic Programming", "slug": "word-break", "reason": "Classic DP on strings."},
                {"title": "Pacific Atlantic Water Flow", "difficulty": "Medium", "topic": "Graphs", "slug": "pacific-atlantic-water-flow", "reason": "Multi-source BFS practice."},
                {"title": "Merge Intervals", "difficulty": "Medium", "topic": "Arrays", "slug": "merge-intervals", "reason": "Sorting and interval merging."}
            ]
        else:
            recs = [
                {"title": "Alien Dictionary", "difficulty": "Hard", "topic": "Graphs", "slug": "alien-dictionary", "reason": "Complex topological sort application."},
                {"title": "Edit Distance", "difficulty": "Hard", "topic": "Dynamic Programming", "slug": "edit-distance", "reason": "Classic 2D DP problem."},
                {"title": "Merge K Sorted Lists", "difficulty": "Hard", "topic": "Heaps", "slug": "merge-k-sorted-lists", "reason": "Great priority queue problem."},
                {"title": "Word Search II", "difficulty": "Hard", "topic": "Trie", "slug": "word-search-ii", "reason": "Combines backtracking with tries."},
                {"title": "Trapping Rain Water", "difficulty": "Hard", "topic": "Arrays", "slug": "trapping-rain-water", "reason": "Two pointers on arrays."},
                {"title": "Serialize and Deserialize Binary Tree", "difficulty": "Hard", "topic": "Trees", "slug": "serialize-and-deserialize-binary-tree", "reason": "Tree traversal and string parsing."},
                {"title": "Longest Increasing Path in a Matrix", "difficulty": "Hard", "topic": "Graphs", "slug": "longest-increasing-path-in-a-matrix", "reason": "DFS with memoization."},
                {"title": "Burst Balloons", "difficulty": "Hard", "topic": "Dynamic Programming", "slug": "burst-balloons", "reason": "Complex divide and conquer DP."},
                {"title": "Find Median from Data Stream", "difficulty": "Hard", "topic": "Heaps", "slug": "find-median-from-data-stream", "reason": "Two heaps pattern."},
                {"title": "Regular Expression Matching", "difficulty": "Hard", "topic": "Dynamic Programming", "slug": "regular-expression-matching", "reason": "Advanced 2D DP problem."}
            ]

    # Ensure Leetcode URLs
    for r in recs:
        if "slug" in r and "leetcode_url" not in r:
            r["leetcode_url"] = f"https://leetcode.com/problems/{r['slug']}/"
        r["solved"] = r.get("slug") in solved_slugs

    await db.problem_recommendations.delete_many({"user_id": user["user_id"]})
    await db.problem_recommendations.insert_one({
        "user_id": user["user_id"],
        "recommendations": recs,
        "level": level,
        "generated_at": datetime.now(timezone.utc).isoformat()
    })

    return {"recommendations": recs, "level": level}

@api_router.post("/problems/{slug}/solved")
async def mark_problem_solved(slug: str, request: Request):
    user = await get_current_user(request)
    
    # Add to solved_problems
    await db.solved_problems.update_one(
        {"user_id": user["user_id"], "slug": slug},
        {"$set": {"solved_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    
    # Delete recommendations cache to force refresh with new problem
    await db.problem_recommendations.delete_many({"user_id": user["user_id"]})
    
    # We could theoretically generate 1 new problem with Ollama here, but 
    # to be simple and robust we just delete the cache so the next GET refreshes it.
    return {"message": "Problem marked as solved", "slug": slug}

@api_router.get("/problems/solved")
async def get_solved_problems(request: Request):
    user = await get_current_user(request)
    solved = await db.solved_problems.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(1000)
    return {"solved_problems": solved}

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
    await db.goals.create_index([("user_id", 1), ("title", 1)], unique=True)
    await db.insights.create_index("user_id")
    await db.problem_recommendations.create_index("user_id")
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
cors_origins_str = os.environ.get("CORS_ORIGINS", "")
origins = [o.strip() for o in cors_origins_str.split(",") if o.strip()]
if not origins:
    origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.ts\.net",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve React Frontend (Single Server Mode)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_build_dir = os.path.join(ROOT_DIR.parent, "frontend", "build")

# Only mount if the build directory exists
if os.path.exists(frontend_build_dir):
    # Serve static assets (/static/js, /static/css, etc)
    static_dir = os.path.join(frontend_build_dir, "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Fallback route for SPA (React Router)
    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        # If the user is trying to hit an API endpoint that doesn't exist, return 404 JSON instead of HTML
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
            
        requested_file = os.path.join(frontend_build_dir, full_path)
        # Serve exact file if it exists (e.g., manifest.json, favicon.ico)
        if os.path.isfile(requested_file):
            return FileResponse(requested_file)
        
        # Otherwise serve index.html for client-side routing
        return FileResponse(os.path.join(frontend_build_dir, "index.html"))
else:
    logger.warning(f"Frontend build directory not found at {frontend_build_dir}. Ensure you run 'npm run build' in the frontend directory.")
