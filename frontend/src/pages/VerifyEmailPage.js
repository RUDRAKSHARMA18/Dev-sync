import React, { useState, useEffect } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import api, { formatApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CheckCircle2, Mail } from "lucide-react";

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  
  const [email, setEmail] = useState(searchParams.get("email") || "");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [msg, setMsg] = useState("");

  const handleVerify = async (e) => {
    e.preventDefault();
    if (!email || !code) return;
    
    setLoading(true);
    setError("");
    try {
      await api.post("/auth/verify-email", { email, code });
      setSuccess(true);
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || "Invalid or expired verification code.");
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (!email) {
      setError("Please enter your email to resend the code.");
      return;
    }
    setResending(true);
    setError("");
    setMsg("");
    try {
      const { data } = await api.post("/auth/resend-verification", { email });
      setMsg(data.message || "Verification code resent! Please check your email.");
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || "Failed to resend code.");
    } finally {
      setResending(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-4 animate-fade-in" data-testid="verify-email-success">
        <Card className="w-full max-w-md border rounded-lg text-center shadow-lg">
          <CardHeader>
            <div className="mx-auto mb-4 w-16 h-16 rounded-full flex items-center justify-center bg-brand-success/10">
              <CheckCircle2 size={32} className="text-brand-success" />
            </div>
            <CardTitle className="font-heading font-bold text-2xl tracking-tight">Email Verified!</CardTitle>
            <CardDescription className="text-base mt-2">
              Your account has been successfully verified.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild className="w-full h-11 font-medium mt-2">
              <Link to="/auth">Continue to Sign In</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4" data-testid="verify-email-page">
      <Card className="w-full max-w-md border rounded-lg shadow-lg animate-fade-in">
        <CardHeader className="text-center pb-6">
          <div className="mx-auto mb-4 w-12 h-12 rounded-full flex items-center justify-center bg-primary/10">
            <Mail size={24} className="text-primary" />
          </div>
          <CardTitle className="font-heading font-bold text-2xl tracking-tight">Verify your email</CardTitle>
          <CardDescription className="text-base mt-2">
            We've sent a 6-digit code to your email. Enter it below to activate your account.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleVerify} className="space-y-4">
            {error && (
              <div className="p-3 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-sm text-center">
                {error}
              </div>
            )}
            {msg && (
              <div className="p-3 rounded-md bg-brand-success/10 border border-brand-success/20 text-brand-success text-sm text-center">
                {msg}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="email">Email Address</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email"
                required
                className="h-11"
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="code">6-Digit Code</Label>
              <Input
                id="code"
                type="text"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/[^0-9]/g, ''))}
                placeholder="000000"
                required
                className="h-12 text-center text-2xl tracking-widest font-mono"
              />
            </div>

            <Button type="submit" className="w-full h-11 font-medium mt-2" disabled={loading || code.length !== 6}>
              {loading ? <div className="w-5 h-5 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" /> : "Verify Account"}
            </Button>

            <div className="text-center mt-6 text-sm text-muted-foreground">
              Didn't receive the code?{" "}
              <button
                type="button"
                onClick={handleResend}
                disabled={resending}
                className="font-medium text-primary hover:underline disabled:opacity-50"
              >
                {resending ? "Sending..." : "Click to resend"}
              </button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
