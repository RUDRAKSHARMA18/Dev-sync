import React, { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { formatApiError } from "@/lib/api";
import api from "@/lib/api";
import { Mail, Lock, User, Eye, EyeOff, Sun, Moon } from "lucide-react";
import { SiGoogle } from "react-icons/si";

const AUTH_BG_DARK = "https://static.prod-images.emergentagent.com/jobs/aebb7a6d-cec7-42be-8543-483f84a54cd7/images/30999452ba81483cb88f4fc95ba9a318515382c0c211f501c3b5da77556d97f5.png";
const AUTH_BG_LIGHT = "https://static.prod-images.emergentagent.com/jobs/aebb7a6d-cec7-42be-8543-483f84a54cd7/images/d8cd64160b90179d9664bbefb69d4e5ce9674004a6e73dee4efa4e5dab95dbbf.png";

export default function AuthPage() {
  const { user, login, register } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotStep, setForgotStep] = useState(1); // 1 = email, 2 = token+password
  const [successMsg, setSuccessMsg] = useState("");

  if (user) return <Navigate to="/dashboard" replace />;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (isLogin) {
        await login(email, password);
      } else {
        if (!name.trim()) {
          setError("Name is required");
          setLoading(false);
          return;
        }
        await register(email, password, name);
      }
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async (e) => {
    e.preventDefault();
    setError("");
    setSuccessMsg("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/forgot-password", { email: forgotEmail });
      if (data.reset_token) {
        // Fallback: token returned directly (email failed)
        setResetToken(data.reset_token);
      }
      setForgotStep(2);
      if (data.email_sent) {
        setSuccessMsg("A password reset email has been sent to your inbox. Check your email for the reset token.");
      } else if (data.reset_token) {
        setSuccessMsg("Email delivery failed. Your reset token has been pre-filled below.");
      } else {
        setSuccessMsg("If an account exists with that email, a reset token has been sent.");
      }
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    setError("");
    setSuccessMsg("");
    setLoading(true);
    try {
      await api.post("/auth/reset-password", { token: resetToken, new_password: newPassword });
      setSuccessMsg("Password reset successfully! You can now sign in.");
      setShowForgotPassword(false);
      setForgotStep(1);
      setResetToken("");
      setNewPassword("");
      setForgotEmail("");
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen flex" data-testid="auth-page">
      {/* Left panel - Background */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        <img
          src={theme === "dark" ? AUTH_BG_DARK : AUTH_BG_LIGHT}
          alt="DevSync"
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-black/30 dark:bg-black/50" />
        <div className="relative z-10 flex flex-col justify-end p-12 text-white">
          <h1 className="font-heading font-bold text-4xl sm:text-5xl tracking-tight mb-4">
            DevSync
          </h1>
          <p className="text-lg text-white/80 font-body max-w-md">
            Track your developer journey across LeetCode, GitHub & Codeforces. AI-powered insights to level up your skills.
          </p>
        </div>
      </div>

      {/* Right panel - Form */}
      <div className="flex-1 flex flex-col bg-background">
        {/* Theme toggle */}
        <div className="flex justify-end p-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            data-testid="auth-theme-toggle"
            className="rounded-md"
          >
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </Button>
        </div>

        <div className="flex-1 flex items-center justify-center px-6 sm:px-12">
          <div className="w-full max-w-md animate-fade-in">
            {/* Mobile logo */}
            <div className="lg:hidden flex items-center gap-2.5 mb-8">
              <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center">
                <span className="text-primary-foreground font-heading font-bold text-lg">DS</span>
              </div>
              <span className="font-heading font-bold text-2xl tracking-tight">DevSync</span>
            </div>

            <h2 className="font-heading font-bold text-2xl sm:text-3xl tracking-tight mb-2">
              {isLogin ? "Welcome back" : "Create account"}
            </h2>
            <p className="text-muted-foreground text-sm mb-8">
              {isLogin ? "Sign in to continue tracking your progress" : "Start your developer journey today"}
            </p>

            {error && (
              <div className="mb-4 p-3 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-sm" data-testid="auth-error">
                {error}
              </div>
            )}

            {successMsg && (
              <div className="mb-4 p-3 rounded-md bg-brand-success/10 border border-brand-success/20 text-brand-success text-sm" data-testid="auth-success">
                {successMsg}
              </div>
            )}

            {showForgotPassword ? (
              /* Forgot Password Flow */
              <div className="space-y-4" data-testid="forgot-password-form">
                {forgotStep === 1 ? (
                  <form onSubmit={handleForgotPassword} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="forgot-email" className="text-sm font-medium">Email Address</Label>
                      <div className="relative">
                        <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                        <Input
                          id="forgot-email"
                          type="email"
                          placeholder="Enter your email"
                          value={forgotEmail}
                          onChange={(e) => setForgotEmail(e.target.value)}
                          className="pl-10"
                          required
                          data-testid="forgot-email-input"
                        />
                      </div>
                    </div>
                    <Button type="submit" className="w-full h-11 font-medium" disabled={loading} data-testid="forgot-submit-button">
                      {loading ? <div className="w-5 h-5 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" /> : "Send Reset Token"}
                    </Button>
                  </form>
                ) : (
                  <form onSubmit={handleResetPassword} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="reset-token" className="text-sm font-medium">Reset Token</Label>
                      <Input
                        id="reset-token"
                        type="text"
                        placeholder="Paste your reset token"
                        value={resetToken}
                        onChange={(e) => setResetToken(e.target.value)}
                        required
                        data-testid="reset-token-input"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="new-password" className="text-sm font-medium">New Password</Label>
                      <div className="relative">
                        <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                        <Input
                          id="new-password"
                          type="password"
                          placeholder="Min 6 characters"
                          value={newPassword}
                          onChange={(e) => setNewPassword(e.target.value)}
                          className="pl-10"
                          required
                          minLength={6}
                          data-testid="new-password-input"
                        />
                      </div>
                    </div>
                    <Button type="submit" className="w-full h-11 font-medium" disabled={loading} data-testid="reset-submit-button">
                      {loading ? <div className="w-5 h-5 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" /> : "Reset Password"}
                    </Button>
                  </form>
                )}
                <button
                  type="button"
                  onClick={() => { setShowForgotPassword(false); setError(""); setSuccessMsg(""); setForgotStep(1); }}
                  className="text-primary text-sm font-medium hover:underline w-full text-center"
                  data-testid="back-to-login-button"
                >
                  Back to Sign In
                </button>
              </div>
            ) : (
            <>
            <form onSubmit={handleSubmit} className="space-y-4" data-testid="auth-form">
              {!isLogin && (
                <div className="space-y-2">
                  <Label htmlFor="name" className="text-sm font-medium">Name</Label>
                  <div className="relative">
                    <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      id="name"
                      type="text"
                      placeholder="Your name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="pl-10"
                      data-testid="register-name-input"
                    />
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="email" className="text-sm font-medium">Email</Label>
                <div className="relative">
                  <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="pl-10"
                    required
                    data-testid="auth-email-input"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-sm font-medium">Password</Label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Min 6 characters"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pl-10 pr-10"
                    required
                    minLength={6}
                    data-testid="auth-password-input"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    data-testid="toggle-password-visibility"
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <Button
                type="submit"
                className="w-full h-11 font-medium"
                disabled={loading}
                data-testid="auth-submit-button"
              >
                {loading ? (
                  <div className="w-5 h-5 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
                ) : (
                  isLogin ? "Sign In" : "Create Account"
                )}
              </Button>

              {isLogin && (
                <button
                  type="button"
                  onClick={() => { setShowForgotPassword(true); setError(""); setSuccessMsg(""); }}
                  className="text-primary text-sm font-medium hover:underline w-full text-center block"
                  data-testid="forgot-password-link"
                >
                  Forgot password?
                </button>
              )}
            </form>

            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-border" />
              </div>
              <div className="relative flex justify-center">
                <span className="bg-background px-3 text-xs text-muted-foreground uppercase tracking-wider">or continue with</span>
              </div>
            </div>

            <Button
              variant="outline"
              className="w-full h-11 gap-2 font-medium"
              onClick={handleGoogleLogin}
              data-testid="google-login-button"
            >
              <SiGoogle size={16} />
              Google
            </Button>

            <p className="text-center text-sm text-muted-foreground mt-6">
              {isLogin ? "Don't have an account? " : "Already have an account? "}
              <button
                type="button"
                onClick={() => { setIsLogin(!isLogin); setError(""); setSuccessMsg(""); }}
                className="text-primary font-medium hover:underline"
                data-testid="auth-toggle-mode"
              >
                {isLogin ? "Sign up" : "Sign in"}
              </button>
            </p>
            </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
