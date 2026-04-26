import React, { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import api from "@/lib/api";

export default function AuthCallback() {
  const hasProcessed = useRef(false);
  const navigate = useNavigate();
  const { setAuthUser } = useAuth();

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processSession = async () => {
      const hash = window.location.hash;
      const match = hash.match(/session_id=([^&]+)/);
      if (!match) {
        navigate("/auth", { replace: true });
        return;
      }

      const sessionId = match[1];

      try {
        const { data } = await api.post("/auth/google/session", { session_id: sessionId });
        setAuthUser(data);
        // Clear hash and navigate
        window.history.replaceState(null, "", window.location.pathname);
        navigate("/dashboard", { replace: true, state: { user: data } });
      } catch (err) {
        console.error("OAuth callback error:", err);
        navigate("/auth", { replace: true });
      }
    };

    processSession();
  }, [navigate, setAuthUser]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-4">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        <p className="text-muted-foreground font-body text-sm">Completing sign in...</p>
      </div>
    </div>
  );
}
