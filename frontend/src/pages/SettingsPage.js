import React, { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Settings, Link2, Unlink, User, Shield, Key, Pencil, Check, X, Lock, ExternalLink } from "lucide-react";
import { SiLeetcode, SiGithub, SiCodeforces, SiCodechef } from "react-icons/si";

const platformConfig = [
  {
    key: "leetcode",
    name: "LeetCode",
    icon: SiLeetcode,
    color: "text-amber-500",
    url: "https://leetcode.com/profile/",
    instruction: "Your username is in the URL: leetcode.com/u/YOUR_USERNAME",
    fields: [{ key: "username", label: "LeetCode Username", placeholder: "e.g., lee215" }],
  },
  {
    key: "github",
    name: "GitHub",
    icon: SiGithub,
    color: "text-foreground",
    url: "https://github.com/settings/profile",
    instruction: "Your username is shown at the top of your profile page",
    fields: [
      { key: "username", label: "GitHub Username", placeholder: "e.g., torvalds" },
      { key: "pat_token", label: "Personal Access Token (Optional)", placeholder: "ghp_xxxx...", optional: true },
    ],
  },
  {
    key: "codeforces",
    name: "Codeforces",
    icon: SiCodeforces,
    color: "text-blue-500",
    url: "https://codeforces.com/settings/general",
    instruction: "Your handle is shown in the top-right corner after login",
    fields: [{ key: "username", label: "Codeforces Handle", placeholder: "e.g., tourist" }],
  },
  {
    key: "codechef",
    name: "CodeChef",
    icon: SiCodechef,
    color: "text-orange-600",
    url: "https://www.codechef.com/settings/profile",
    instruction: "Your username is in the URL: codechef.com/users/YOUR_USERNAME",
    fields: [{ key: "username", label: "CodeChef Username", placeholder: "e.g., admin" }],
  },
];

export default function SettingsPage() {
  const { user, checkAuth } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [connections, setConnections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [connectDialog, setConnectDialog] = useState(null);
  const [formData, setFormData] = useState({});
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState("");
  const [oauthError, setOauthError] = useState("");
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileMsg, setProfileMsg] = useState("");

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordMsg, setPasswordMsg] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);

  const [editingUsername, setEditingUsername] = useState(false);
  const [usernameValue, setUsernameValue] = useState("");
  const [usernameAvailable, setUsernameAvailable] = useState(null);
  const [usernameChecking, setUsernameChecking] = useState(false);
  const [usernameMsg, setUsernameMsg] = useState("");

  // Debounced username check
  useEffect(() => {
    if (!editingUsername || !usernameValue || usernameValue === user?.username) {
      setUsernameAvailable(null);
      return;
    }
    const timer = setTimeout(async () => {
      setUsernameChecking(true);
      try {
        const { data } = await api.post("/auth/check-username", { username: usernameValue });
        if (data.available) setUsernameAvailable(true);
        else {
          setUsernameAvailable(false);
          if (data.error) setUsernameMsg(data.error);
          else setUsernameMsg("");
        }
      } catch (err) {
        setUsernameAvailable(false);
      } finally {
        setUsernameChecking(false);
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [usernameValue, editingUsername, user?.username]);

  const handleChangePassword = async (e) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setPasswordMsg("New passwords do not match.");
      return;
    }
    setChangingPassword(true);
    setPasswordMsg("");
    try {
      await api.post("/auth/change-password", { current_password: currentPassword, new_password: newPassword });
      setPasswordMsg("Password changed successfully!");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setPasswordMsg(formatApiError(err.response?.data?.detail) || "Failed to change password.");
    } finally {
      setChangingPassword(false);
    }
  };

  const handleSaveUsername = async () => {
    if (!usernameValue.trim() || usernameValue === user?.username || !usernameAvailable) {
      setEditingUsername(false);
      return;
    }
    setSavingProfile(true);
    setUsernameMsg("");
    try {
      await api.patch("/user/username", { username: usernameValue.trim() });
      await checkAuth(); // refresh user data
      setEditingUsername(false);
      setProfileMsg("Username updated!");
      setTimeout(() => setProfileMsg(""), 3000);
    } catch (err) {
      setUsernameMsg(formatApiError(err.response?.data?.detail) || "Update failed");
    } finally {
      setSavingProfile(false);
    }
  };

  const fetchConnections = async () => {
    try {
      const { data } = await api.get("/platforms");
      setConnections(data.platforms || []);
    } catch (err) {
      console.error("Fetch connections error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConnections();
  }, []);

  useEffect(() => {
    const query = new URLSearchParams(location.search);
    const code = query.get("code");
    if (code) {
      handleGitHubOAuthCallback(code);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search]);

  const handleGitHubOAuthCallback = async (code) => {
    setConnecting(true);
    setOauthError("");
    // Clear code from URL
    navigate("/settings", { replace: true });
    
    try {
      await api.post("/platforms/github/oauth/callback", { code });
      fetchConnections();
      setProfileMsg("GitHub connected successfully!");
      setTimeout(() => setProfileMsg(""), 3000);
    } catch (err) {
      console.error("OAuth callback error:", err);
      setOauthError(formatApiError(err.response?.data?.detail) || "GitHub OAuth failed");
      // Scroll to the error so user sees it
      window.scrollTo(0, 0);
    } finally {
      setConnecting(false);
    }
  };

  const handleSaveProfile = async () => {
    if (!nameValue.trim()) return;
    setSavingProfile(true);
    setProfileMsg("");
    try {
      await api.put("/profile", { name: nameValue.trim() });
      await checkAuth(); // refresh user data in context
      setEditingName(false);
      setProfileMsg("Profile updated!");
      setTimeout(() => setProfileMsg(""), 3000);
    } catch (err) {
      setProfileMsg(formatApiError(err.response?.data?.detail) || "Update failed");
    } finally {
      setSavingProfile(false);
    }
  };

  const handleConnect = async (e) => {
    e.preventDefault();
    setConnecting(true);
    setError("");
    try {
      await api.post("/platforms/connect", {
        platform: connectDialog,
        username: formData.username,
        pat_token: formData.pat_token || null,
      });
      setConnectDialog(null);
      setFormData({});
      fetchConnections();
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || "Connection failed");
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async (platform) => {
    try {
      await api.delete(`/platforms/${platform}`);
      fetchConnections();
    } catch (err) {
      console.error("Disconnect error:", err);
    }
  };

  const isConnected = (platform) => connections.some((c) => c.platform === platform);
  const getConnection = (platform) => connections.find((c) => c.platform === platform);

  return (
    <div className="space-y-6 max-w-3xl" data-testid="settings-page">
      <div className="animate-fade-in">
        <h1 className="font-heading font-bold text-2xl sm:text-3xl tracking-tight">Settings</h1>
        <p className="text-muted-foreground text-sm mt-1">Manage your account and platform connections</p>
      </div>

      {/* Profile */}
      <Card className="border rounded-lg animate-fade-in stagger-1" data-testid="profile-card">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <User size={18} className="text-primary" />
            <CardTitle className="text-base font-heading">Profile</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-lg bg-primary flex items-center justify-center text-primary-foreground font-heading font-bold text-xl">
              {user?.name?.[0]?.toUpperCase() || "U"}
            </div>
            <div className="flex-1">
              {editingName ? (
                <div className="flex items-center gap-2">
                  <Input
                    value={nameValue}
                    onChange={(e) => setNameValue(e.target.value)}
                    className="h-8 text-sm max-w-[200px]"
                    autoFocus
                    data-testid="edit-name-input"
                    onKeyDown={(e) => { if (e.key === "Enter") handleSaveProfile(); if (e.key === "Escape") setEditingName(false); }}
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-brand-success"
                    onClick={handleSaveProfile}
                    disabled={savingProfile}
                    data-testid="save-name-button"
                  >
                    {savingProfile ? <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" /> : <Check size={14} />}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground"
                    onClick={() => setEditingName(false)}
                    data-testid="cancel-edit-name-button"
                  >
                    <X size={14} />
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <p className="font-heading font-semibold" data-testid="settings-user-name">{user?.name || "User"}</p>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 text-muted-foreground hover:text-foreground"
                    onClick={() => { setEditingName(true); setNameValue(user?.name || ""); setProfileMsg(""); }}
                    data-testid="edit-name-button"
                  >
                    <Pencil size={12} />
                  </Button>
                </div>
              )}
              <div className="mt-1">
                <p className="text-sm text-muted-foreground" data-testid="settings-user-email">{user?.email}</p>
              </div>
              {editingUsername ? (
                <div className="flex items-center gap-2 mt-2">
                  <span className="text-muted-foreground">@</span>
                  <Input
                    value={usernameValue}
                    onChange={(e) => setUsernameValue(e.target.value.toLowerCase())}
                    className="h-8 text-sm max-w-[180px]"
                    placeholder="username"
                  />
                  {usernameChecking && <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />}
                  {!usernameChecking && usernameAvailable === true && <Check size={14} className="text-brand-success" />}
                  {!usernameChecking && usernameAvailable === false && <X size={14} className="text-destructive" />}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-brand-success"
                    onClick={handleSaveUsername}
                    disabled={savingProfile || usernameAvailable === false}
                  >
                    {savingProfile ? <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" /> : <Check size={14} />}
                  </Button>
                  <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground" onClick={() => setEditingUsername(false)}>
                    <X size={14} />
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-2 mt-1">
                  <p className="text-sm font-mono text-muted-foreground">@{user?.username || "username"}</p>
                  <Button variant="ghost" size="icon" className="h-5 w-5 text-muted-foreground hover:text-foreground" onClick={() => { setEditingUsername(true); setUsernameValue(user?.username || ""); setUsernameMsg(""); setUsernameAvailable(null); }}>
                    <Pencil size={10} />
                  </Button>
                </div>
              )}
              {usernameMsg && <p className={`text-xs mt-1 ${usernameAvailable === false ? "text-destructive" : "text-brand-success"}`}>{usernameMsg}</p>}
              <Badge variant="outline" className="mt-2 text-xs capitalize">
                {user?.auth_provider || "email"} &middot; {user?.role || "user"}
              </Badge>
              {profileMsg && (
                <p className={`text-xs mt-1 ${profileMsg.includes("updated") ? "text-brand-success" : "text-destructive"}`} data-testid="profile-message">
                  {profileMsg}
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Platform Connections */}
      {oauthError && (
        <div className="p-3 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-sm animate-in fade-in slide-in-from-top-2">
          {oauthError}
        </div>
      )}
      <Card className="border rounded-lg animate-fade-in stagger-2" data-testid="connections-card">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Link2 size={18} className="text-primary" />
            <CardTitle className="text-base font-heading">Platform Connections</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {platformConfig.map((platform) => {
            const connected = isConnected(platform.key);
            const conn = getConnection(platform.key);
            const Icon = platform.icon;

            return (
              <div
                key={platform.key}
                className="flex items-center justify-between p-4 rounded-md border border-border bg-accent/30 transition-all hover:bg-accent/50"
                data-testid={`settings-platform-${platform.key}`}
              >
                <div className="flex items-center gap-3">
                  <Icon size={24} className={platform.color} />
                  <div>
                    <p className="font-medium text-sm">{platform.name}</p>
                    {connected && conn ? (
                      <p className="text-xs text-muted-foreground font-mono">{conn.username}</p>
                    ) : (
                      <p className="text-xs text-muted-foreground">Not connected</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {connected ? (
                    <>
                      <Badge variant="outline" className="text-xs text-brand-success border-brand-success/30">
                        Connected
                      </Badge>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDisconnect(platform.key)}
                        className="text-xs text-destructive hover:text-destructive"
                        data-testid={`disconnect-${platform.key}`}
                      >
                        <Unlink size={14} className="mr-1" />
                        Disconnect
                      </Button>
                    </>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        if (platform.key === "github") {
                          const clientId = process.env.REACT_APP_GITHUB_CLIENT_ID;
                          if (!clientId) {
                            setOauthError("GitHub Client ID is not configured in environment variables.");
                            return;
                          }
                          window.location.href = `https://github.com/login/oauth/authorize?client_id=${clientId}&scope=read:user`;
                        } else {
                          setConnectDialog(platform.key);
                          setFormData({});
                          setError("");
                        }
                      }}
                      data-testid={`connect-${platform.key}`}
                      className="text-xs"
                    >
                      <Link2 size={14} className="mr-1" />
                      Connect
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      {/* Connect Dialog */}
      <Dialog open={!!connectDialog} onOpenChange={() => setConnectDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-heading capitalize">
              Connect {platformConfig.find((p) => p.key === connectDialog)?.name}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleConnect} className="space-y-4" data-testid="connect-platform-form">
            <div className="flex flex-col gap-2 mb-4 bg-accent/30 p-3 rounded-md">
               <Button type="button" variant="outline" asChild className="w-full">
                  <a href={platformConfig.find((p) => p.key === connectDialog)?.url} target="_blank" rel="noopener noreferrer">
                    Visit & Get Username <ExternalLink size={14} className="ml-2" />
                  </a>
               </Button>
               <p className="text-xs text-center text-muted-foreground mt-1">
                 Find your username on the page that opens, then enter it below.
               </p>
            </div>
            {error && (
              <div className="p-3 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-sm" data-testid="connect-error">
                {error}
              </div>
            )}
            {platformConfig
              .find((p) => p.key === connectDialog)
              ?.fields.map((field) => (
                <div key={field.key} className="space-y-2">
                  <Label className="text-sm">
                    {field.label}
                    {field.optional && <span className="text-muted-foreground ml-1">(optional)</span>}
                  </Label>
                  <Input
                    value={formData[field.key] || ""}
                    onChange={(e) => setFormData({ ...formData, [field.key]: e.target.value })}
                    placeholder={field.placeholder}
                    required={!field.optional}
                    data-testid={`connect-input-${field.key}`}
                  />
                  {field.key === "username" && (
                    <p className="text-xs text-muted-foreground mt-1">
                      {platformConfig.find((p) => p.key === connectDialog)?.instruction}
                    </p>
                  )}
                  {field.key === "pat_token" && (
                    <p className="text-xs text-muted-foreground">
                      Without a PAT, GitHub API is limited to 60 requests/hour. Get one from GitHub Settings &rarr; Developer Settings &rarr; Personal Access Tokens.
                    </p>
                  )}
                </div>
              ))}
            <Button type="submit" className="w-full" disabled={connecting} data-testid="submit-connect-button">
              {connecting ? (
                <div className="w-5 h-5 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
              ) : (
                "Connect"
              )}
            </Button>
          </form>
        </DialogContent>
      </Dialog>

      {/* Security Info */}
      <Card className="border rounded-lg animate-fade-in stagger-3" data-testid="security-card">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Shield size={18} className="text-primary" />
            <CardTitle className="text-base font-heading">Security</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex items-center justify-between p-3 rounded-md bg-accent/30">
            <div className="flex items-center gap-2">
              <Key size={14} className="text-muted-foreground" />
              <span className="text-sm">Session Management</span>
            </div>
            <Badge variant="outline" className="text-xs text-brand-success border-brand-success/30">Active</Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            Your session is secured with httpOnly cookies. All data is strictly isolated to your account.
          </p>

          {user?.auth_provider === "email" && (
            <div className="pt-4 border-t border-border mt-4">
              <div className="flex items-center gap-2 mb-3">
                <Lock size={14} className="text-muted-foreground" />
                <h3 className="text-sm font-semibold">Change Password</h3>
              </div>
              <form onSubmit={handleChangePassword} className="space-y-3 max-w-sm">
                <div className="space-y-1">
                  <Label className="text-xs">Current Password</Label>
                  <Input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} required className="h-8 text-sm" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">New Password</Label>
                  <Input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required className="h-8 text-sm" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Confirm New Password</Label>
                  <Input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required className="h-8 text-sm" />
                </div>
                {passwordMsg && (
                  <p className={`text-xs ${passwordMsg.includes("success") ? "text-brand-success" : "text-destructive"}`}>
                    {passwordMsg}
                  </p>
                )}
                <Button type="submit" disabled={changingPassword} size="sm">
                  {changingPassword ? "Updating..." : "Update Password"}
                </Button>
              </form>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
