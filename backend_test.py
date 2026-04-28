#!/usr/bin/env python3
"""
DevSync Backend API Testing Suite
Tests all authentication, platform, dashboard, goals, insights, and readiness endpoints
"""

import requests
import sys
import json
import time
from datetime import datetime

class DevSyncAPITester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.session = requests.Session()
        self.tests_run = 0
        self.tests_passed = 0
        self.admin_cookies = None
        self.user_cookies = None
        
    def log(self, message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def run_test(self, name, method, endpoint, expected_status, data=None, cookies=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        if headers:
            test_headers.update(headers)
            
        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = self.session.get(url, headers=test_headers, cookies=cookies)
            elif method == 'POST':
                response = self.session.post(url, json=data, headers=test_headers, cookies=cookies)
            elif method == 'PUT':
                response = self.session.put(url, json=data, headers=test_headers, cookies=cookies)
            elif method == 'DELETE':
                response = self.session.delete(url, headers=test_headers, cookies=cookies)
            else:
                self.log(f"❌ Unsupported method: {method}")
                return False, {}

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ Passed - Status: {response.status_code}")
            else:
                self.log(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                if response.text:
                    self.log(f"   Response: {response.text[:200]}")

            try:
                response_data = response.json() if response.text else {}
            except:
                response_data = {"raw_response": response.text}
                
            return success, response_data, response.cookies

        except Exception as e:
            self.log(f"❌ Failed - Error: {str(e)}")
            return False, {}, None

    def test_auth_register(self):
        """Test user registration"""
        test_email = f"test_{int(time.time())}@example.com"
        success, response, cookies = self.run_test(
            "User Registration",
            "POST",
            "auth/register",
            200,
            data={"email": test_email, "password": "test12345", "name": "Test User"}
        )
        if success and cookies:
            self.user_cookies = cookies
        return success, test_email

    def test_auth_login_admin(self):
        """Test admin login"""
        success, response, cookies = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@devsync.com", "password": "admin123"}
        )
        if success and cookies:
            self.admin_cookies = cookies
        return success

    def test_auth_login_user(self):
        """Test user login with existing test user"""
        success, response, cookies = self.run_test(
            "Test User Login",
            "POST",
            "auth/login",
            200,
            data={"email": "testuser@example.com", "password": "test12345"}
        )
        if success and cookies:
            self.user_cookies = cookies
        return success

    def test_auth_me(self, cookies, user_type="user"):
        """Test /auth/me endpoint"""
        success, response, _ = self.run_test(
            f"Auth Me ({user_type})",
            "GET",
            "auth/me",
            200,
            cookies=cookies
        )
        return success, response

    def test_auth_logout(self, cookies):
        """Test logout"""
        success, response, _ = self.run_test(
            "Logout",
            "POST",
            "auth/logout",
            200,
            cookies=cookies
        )
        return success

    def test_auth_refresh(self, cookies):
        """Test token refresh"""
        success, response, new_cookies = self.run_test(
            "Token Refresh",
            "POST",
            "auth/refresh",
            200,
            cookies=cookies
        )
        return success, new_cookies

    def test_brute_force_protection(self):
        """Test brute force protection - 5 failed attempts should lock account"""
        self.log("🔒 Testing brute force protection...")
        test_email = "brute@test.com"
        
        # Try 6 failed login attempts
        for i in range(6):
            success, response, _ = self.run_test(
                f"Brute Force Attempt {i+1}",
                "POST",
                "auth/login",
                401 if i < 5 else 429,  # Expect 429 (Too Many Requests) on 6th attempt
                data={"email": test_email, "password": "wrongpassword"}
            )
            if i == 5 and response.get("detail") and "Too many login attempts" in response["detail"]:
                self.log("✅ Brute force protection working correctly")
                return True
                
        self.log("❌ Brute force protection not working as expected")
        return False

    def test_platform_connect(self, cookies, platform="leetcode", username="testuser"):
        """Test platform connection"""
        success, response, _ = self.run_test(
            f"Connect {platform}",
            "POST",
            "platforms/connect",
            200,
            data={"platform": platform, "username": username},
            cookies=cookies
        )
        return success, response

    def test_platform_list(self, cookies):
        """Test platform list"""
        success, response, _ = self.run_test(
            "List Platforms",
            "GET",
            "platforms",
            200,
            cookies=cookies
        )
        return success, response

    def test_platform_disconnect(self, cookies, platform="leetcode"):
        """Test platform disconnect"""
        success, response, _ = self.run_test(
            f"Disconnect {platform}",
            "DELETE",
            f"platforms/{platform}",
            200,
            cookies=cookies
        )
        return success

    def test_dashboard(self, cookies):
        """Test dashboard data"""
        success, response, _ = self.run_test(
            "Dashboard Data",
            "GET",
            "dashboard",
            200,
            cookies=cookies
        )
        return success, response

    def test_readiness(self, cookies):
        """Test readiness score"""
        success, response, _ = self.run_test(
            "Readiness Score",
            "GET",
            "readiness",
            200,
            cookies=cookies
        )
        return success, response

    def test_insights(self, cookies):
        """Test AI insights"""
        success, response, _ = self.run_test(
            "AI Insights",
            "GET",
            "insights",
            200,
            cookies=cookies
        )
        return success, response

    def test_goals_crud(self, cookies):
        """Test Goals CRUD operations"""
        # Create goal
        success, goal_response, _ = self.run_test(
            "Create Goal",
            "POST",
            "goals",
            200,
            data={"title": "Test Goal", "description": "Test Description", "target_value": 10, "category": "dsa"},
            cookies=cookies
        )
        if not success:
            return False
            
        goal_id = goal_response.get("goal_id")
        if not goal_id:
            self.log("❌ No goal_id returned from create goal")
            return False

        # Get goals
        success, goals_response, _ = self.run_test(
            "Get Goals",
            "GET",
            "goals",
            200,
            cookies=cookies
        )
        if not success:
            return False

        # Update goal
        success, update_response, _ = self.run_test(
            "Update Goal",
            "PUT",
            f"goals/{goal_id}",
            200,
            data={"current_value": 5, "completed": False},
            cookies=cookies
        )
        if not success:
            return False

        # Delete goal
        success, delete_response, _ = self.run_test(
            "Delete Goal",
            "DELETE",
            f"goals/{goal_id}",
            200,
            cookies=cookies
        )
        return success

    def test_auto_generate_goals(self, cookies):
        """Test auto-generate goals"""
        success, response, _ = self.run_test(
            "Auto-Generate Goals",
            "POST",
            "goals/auto-generate",
            200,
            cookies=cookies
        )
        return success, response

    def test_password_reset_flow(self):
        """Test password reset flow - forgot password + reset password"""
        self.log("🔑 Testing password reset flow...")
        
        # Step 1: Request password reset
        success, response, _ = self.run_test(
            "Forgot Password",
            "POST",
            "auth/forgot-password",
            200,
            data={"email": "testuser@example.com"}
        )
        if not success:
            return False
            
        # Check for email_sent field (NEW FEATURE)
        email_sent = response.get("email_sent", False)
        if email_sent:
            self.log("✅ Email sent via Resend integration")
        else:
            self.log("ℹ️ Email delivery failed, fallback token provided")
            
        # Extract reset token from response (in dev mode, token is returned)
        reset_token = response.get("reset_token")
        if not reset_token:
            self.log("❌ No reset token returned from forgot-password")
            return False
            
        self.log(f"✅ Reset token received: {reset_token[:10]}...")
        
        # Step 2: Reset password with token
        new_password = "newpassword123"
        success, response, _ = self.run_test(
            "Reset Password",
            "POST",
            "auth/reset-password",
            200,
            data={"token": reset_token, "new_password": new_password}
        )
        if not success:
            return False
            
        # Step 3: Test login with new password
        success, response, cookies = self.run_test(
            "Login with New Password",
            "POST",
            "auth/login",
            200,
            data={"email": "testuser@example.com", "password": new_password}
        )
        if success:
            self.log("✅ Password reset flow working correctly")
            # Store cookies for profile tests
            self.user_cookies = cookies
        return success
        
    def test_password_reset_invalid_token(self):
        """Test password reset with invalid token"""
        success, response, _ = self.run_test(
            "Reset Password Invalid Token",
            "POST",
            "auth/reset-password",
            400,  # Should return 400 for invalid token
            data={"token": "invalid_token_123", "new_password": "newpass123"}
        )
        return success
        
    def test_codechef_platform_connect(self, cookies):
        """Test CodeChef platform connection"""
        success, response, _ = self.run_test(
            "Connect CodeChef",
            "POST",
            "platforms/connect",
            200,
            data={"platform": "codechef", "username": "testuser"},
            cookies=cookies
        )
        return success, response
        
    def test_profile_update(self, cookies):
        """Test profile update functionality (NEW FEATURE)"""
        self.log("👤 Testing profile update...")
        
        # Get current user info
        success, user_data, _ = self.run_test(
            "Get Current User Info",
            "GET",
            "auth/me",
            200,
            cookies=cookies
        )
        if not success:
            return False
            
        original_name = user_data.get("name", "")
        self.log(f"Original name: {original_name}")
        
        # Test valid name update
        new_name = "Updated Test User"
        success, response, _ = self.run_test(
            "Update Profile Name",
            "PUT",
            "profile",
            200,
            data={"name": new_name},
            cookies=cookies
        )
        if not success:
            return False
            
        # Verify name was updated in response
        if response.get("name") != new_name:
            self.log(f"❌ Name not updated in response: expected '{new_name}', got '{response.get('name')}'")
            return False
            
        # Verify /auth/me reflects the updated name
        success, updated_user, _ = self.run_test(
            "Verify Updated Name in Auth/Me",
            "GET",
            "auth/me",
            200,
            cookies=cookies
        )
        if not success:
            return False
            
        if updated_user.get("name") != new_name:
            self.log(f"❌ Updated name not reflected in /auth/me: expected '{new_name}', got '{updated_user.get('name')}'")
            return False
            
        self.log("✅ Profile name update working correctly")
        return True
        
    def test_profile_update_validation(self, cookies):
        """Test profile update validation (NEW FEATURE)"""
        self.log("🚫 Testing profile update validation...")
        
        # Test empty name rejection
        success, response, _ = self.run_test(
            "Update Profile Empty Name",
            "PUT",
            "profile",
            400,  # Should return 400 for empty name
            data={"name": ""},
            cookies=cookies
        )
        if success and "empty" in response.get("detail", "").lower():
            self.log("✅ Empty name correctly rejected")
            return True
        else:
            self.log("❌ Empty name validation failed")
            return False

    def test_create_test_user(self):
        """Create test user if it doesn't exist"""
        self.log("👤 Creating test user...")
        success, response, cookies = self.run_test(
            "Create Test User",
            "POST",
            "auth/register",
            200,
            data={"email": "testuser@example.com", "password": "test12345", "name": "Test User"}
        )
        # If user already exists, try to login
        if not success:
            success, response, cookies = self.run_test(
                "Login Existing Test User",
                "POST",
                "auth/login",
                200,
                data={"email": "testuser@example.com", "password": "test12345"}
            )
        
        if success and cookies:
            self.user_cookies = cookies
        return success

    def test_user_isolation(self):
        """CRITICAL: Test user isolation - no cross-user data leakage"""
        self.log("🔐 CRITICAL: Testing user isolation...")
        
        # Login as admin and connect a platform
        if not self.test_auth_login_admin():
            self.log("❌ Admin login failed for isolation test")
            return False
            
        # Connect platform as admin
        success, _ = self.test_platform_connect(self.admin_cookies, "github", "admin_github")
        if not success:
            self.log("❌ Admin platform connect failed")
            return False
            
        # Get admin platforms
        success, admin_platforms = self.test_platform_list(self.admin_cookies)
        if not success:
            self.log("❌ Admin platform list failed")
            return False
            
        admin_platform_count = len(admin_platforms.get("platforms", []))
        self.log(f"Admin has {admin_platform_count} connected platforms")
        
        # Logout admin
        self.test_auth_logout(self.admin_cookies)
        
        # Login as test user
        if not self.test_auth_login_user():
            self.log("❌ Test user login failed for isolation test")
            return False
            
        # Check test user platforms - should be ZERO
        success, user_platforms = self.test_platform_list(self.user_cookies)
        if not success:
            self.log("❌ User platform list failed")
            return False
            
        user_platform_count = len(user_platforms.get("platforms", []))
        self.log(f"Test user has {user_platform_count} connected platforms")
        
        if user_platform_count == 0:
            self.log("✅ CRITICAL: User isolation working correctly - no cross-user data leakage")
            return True
        else:
            self.log("❌ CRITICAL: User isolation FAILED - cross-user data leakage detected!")
            return False

def main():
    tester = DevSyncAPITester()
    
    print("=" * 60)
    print("🚀 DevSync Backend API Testing Suite - NEW FEATURES")
    print("=" * 60)
    
    # Test basic auth flows
    tester.log("📝 Testing Authentication...")
    
    # Test registration
    reg_success, test_email = tester.test_auth_register()
    
    # Test admin login
    admin_login_success = tester.test_auth_login_admin()
    
    # Create/login test user
    user_login_success = tester.test_create_test_user()
    
    # Test /auth/me for both users
    if admin_login_success:
        tester.test_auth_me(tester.admin_cookies, "admin")
    if user_login_success:
        tester.test_auth_me(tester.user_cookies, "user")
    
    # Test token refresh
    if user_login_success:
        tester.test_auth_refresh(tester.user_cookies)
    
    # NEW: Test password reset flow
    tester.log("🔑 Testing NEW Password Reset Features...")
    reset_success = tester.test_password_reset_flow()
    tester.test_password_reset_invalid_token()
    
    # NEW: Test profile update features
    if reset_success or user_login_success:
        tester.log("👤 Testing NEW Profile Update Features...")
        tester.test_profile_update(tester.user_cookies)
        tester.test_profile_update_validation(tester.user_cookies)
    
    # Test brute force protection
    tester.test_brute_force_protection()
    
    # Test platform operations (using user account)
    if user_login_success:
        tester.log("🔗 Testing Platform Operations...")
        tester.test_platform_connect(tester.user_cookies, "leetcode", "testuser")
        
        # NEW: Test CodeChef platform
        tester.log("🍳 Testing NEW CodeChef Platform...")
        tester.test_codechef_platform_connect(tester.user_cookies)
        
        tester.test_platform_list(tester.user_cookies)
        
        # Test dashboard and other endpoints
        tester.log("📊 Testing Dashboard & Analytics...")
        tester.test_dashboard(tester.user_cookies)
        tester.test_readiness(tester.user_cookies)
        tester.test_insights(tester.user_cookies)
        
        # NEW: Test heatmap endpoint
        tester.log("🔥 Testing NEW Contribution Heatmap...")
        tester.test_heatmap_endpoint(tester.user_cookies)
        
        # Test goals
        tester.log("🎯 Testing Goals...")
        tester.test_goals_crud(tester.user_cookies)
        tester.test_auto_generate_goals(tester.user_cookies)
        
        # Clean up - disconnect platforms
        tester.test_platform_disconnect(tester.user_cookies, "leetcode")
        tester.test_platform_disconnect(tester.user_cookies, "codechef")
    
    # CRITICAL: Test user isolation
    tester.test_user_isolation()
    
    # Test logout
    if user_login_success:
        tester.test_auth_logout(tester.user_cookies)
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    print("=" * 60)
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"❌ {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())