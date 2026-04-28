import React, { useState, useEffect, useMemo } from "react";
import api from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Code2, GitCommit, Flame, Activity, RefreshCw, ExternalLink } from "lucide-react";
import { SiLeetcode, SiGithub, SiCodeforces, SiCodechef } from "react-icons/si";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import ContributionHeatmap from "@/components/ContributionHeatmap";

const platformIcons = {
  leetcode: SiLeetcode,
  github: SiGithub,
  codeforces: SiCodeforces,
  codechef: SiCodechef,
};

const platformColors = {
  leetcode: "text-amber-500",
  github: "text-foreground",
  codeforces: "text-blue-500",
  codechef: "text-orange-600",
};

export default function DashboardPage() {
  const { user } = useAuth();
  const [dashboard, setDashboard] = useState(null);
  const [heatmapRaw, setHeatmapRaw] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(null);
  const [period, setPeriod] = useState(() => localStorage.getItem("dashboard_period") || "365");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState(() => new Date().toISOString().split("T")[0]);

  useEffect(() => {
    localStorage.setItem("dashboard_period", period);
  }, [period]);

  const fetchDashboard = async () => {
    try {
      let url = `/dashboard?days=${period}`;
      if (period === "custom") {
        if (!customStart || !customEnd) return; // Wait until both are set
        url = `/dashboard?from=${customStart}&to=${customEnd}`;
      }
      
      const [dashRes, heatRes] = await Promise.all([
        api.get(url),
        api.get("/heatmap"),
      ]);
      setDashboard(dashRes.data);
      setHeatmapRaw(heatRes.data.heatmap || []);
    } catch (err) {
      console.error("Dashboard fetch error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period, customStart, customEnd]);

  const handleSync = async (platform) => {
    setSyncing(platform);
    try {
      await api.post(`/platforms/${platform}/sync`);
      await fetchDashboard();
    } catch (err) {
      console.error("Sync error:", err);
    } finally {
      setSyncing(null);
    }
  };

  // Compute period-filtered stats from heatmap data
  const periodStats = useMemo(() => {
    if (!heatmapRaw.length) return { contributions: 0, activeDays: 0 };
    let filtered = heatmapRaw;
    if (period === "custom" && customStart && customEnd) {
      filtered = heatmapRaw.filter(d => d.date >= customStart && d.date <= customEnd);
    } else if (period !== "custom") {
      const days = parseInt(period, 10);
      filtered = heatmapRaw.slice(-days);
    } else {
      filtered = [];
    }
    const contributions = filtered.reduce((sum, d) => sum + d.count, 0);
    const activeDays = filtered.filter((d) => d.count > 0).length;
    return { contributions, activeDays };
  }, [heatmapRaw, period, customStart, customEnd]);

  // Build period-filtered weekly graph
  const periodWeeklyGraph = useMemo(() => {
    if (!heatmapRaw.length) return dashboard?.weekly_graph || [];
    let filtered = heatmapRaw;
    if (period === "custom" && customStart && customEnd) {
      filtered = heatmapRaw.filter(d => d.date >= customStart && d.date <= customEnd);
    } else if (period !== "custom") {
      const days = parseInt(period, 10);
      filtered = heatmapRaw.slice(-days);
    } else {
      filtered = [];
    }
    const last7 = filtered.slice(-7);
    return last7.map((d) => ({
      date: d.date,
      day: new Date(d.date + "T00:00:00Z").toLocaleDateString("en-US", { weekday: "short" }),
      activity: d.count,
    }));
  }, [heatmapRaw, period, customStart, customEnd, dashboard]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const periodLabel = period === "7" ? "7 days" : period === "30" ? "30 days" : period === "90" ? "90 days" : period === "custom" ? "custom range" : "year";

  const stats = [
    {
      label: "PROBLEMS SOLVED",
      value: dashboard?.total_problems || 0,
      icon: Code2,
      color: "text-brand-dsa",
      bgColor: "bg-brand-dsa/10",
    },
    {
      label: "CONTRIBUTIONS",
      value: periodStats.contributions,
      subLabel: `in ${periodLabel}`,
      icon: GitCommit,
      color: "text-brand-success",
      bgColor: "bg-brand-success/10",
    },
    {
      label: "DAY STREAK",
      value: dashboard?.streak || 0,
      icon: Flame,
      color: "text-brand-warning",
      bgColor: "bg-brand-warning/10",
    },
    {
      label: "PLATFORMS",
      value: dashboard?.connections?.length || 0,
      icon: Activity,
      color: "text-brand-projects",
      bgColor: "bg-brand-projects/10",
    },
  ];

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* Welcome */}
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-end gap-4 animate-fade-in">
        <div>
          <h1 className="font-heading font-bold text-2xl sm:text-3xl tracking-tight">
            Welcome back, {user?.name?.split(" ")[0] || "Developer"}
          </h1>
          <p className="text-muted-foreground text-sm mt-1">Here's your coding activity overview</p>
        </div>
        <div className="flex items-center gap-2">
          {period === "custom" && (
            <div className="flex items-center gap-2 animate-fade-in">
              <Input
                type="date"
                className="h-9 w-[130px] text-xs"
                value={customStart}
                onChange={(e) => setCustomStart(e.target.value)}
              />
              <span className="text-muted-foreground text-xs">to</span>
              <Input
                type="date"
                className="h-9 w-[130px] text-xs"
                value={customEnd}
                onChange={(e) => setCustomEnd(e.target.value)}
              />
            </div>
          )}
          <Select value={period} onValueChange={setPeriod}>
            <SelectTrigger className="w-[140px] h-9 text-xs font-medium">
              <SelectValue placeholder="Select Period" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">Last 7 Days</SelectItem>
              <SelectItem value="30">Last 30 Days</SelectItem>
              <SelectItem value="90">Last 90 Days</SelectItem>
              <SelectItem value="365">Last 365 Days</SelectItem>
              <SelectItem value="custom">Custom</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" data-testid="stats-grid">
        {stats.map((stat, i) => (
          <Card
            key={stat.label}
            className={`border rounded-lg transition-all duration-200 hover:-translate-y-1 hover:shadow-md animate-fade-in stagger-${i + 1}`}
            data-testid={`stat-card-${stat.label.toLowerCase().replace(/\s/g, "-")}`}
          >
            <CardContent className="p-4 sm:p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-mono tracking-[0.15em] uppercase text-muted-foreground">{stat.label}</span>
                <div className={`w-8 h-8 rounded-md ${stat.bgColor} flex items-center justify-center`}>
                  <stat.icon size={16} className={stat.color} />
                </div>
              </div>
              <p className="text-3xl sm:text-4xl font-mono font-bold tracking-tighter" data-testid={`stat-value-${stat.label.toLowerCase().replace(/\s/g, "-")}`}>
                {stat.value}
              </p>
              {stat.subLabel && (
                <p className="text-xs text-muted-foreground mt-1">{stat.subLabel}</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 sm:gap-6">
        {/* Weekly Activity Chart */}
        <Card className="xl:col-span-2 border rounded-lg animate-fade-in" data-testid="weekly-chart-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg font-heading font-semibold">Recent Activity</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="h-[240px] sm:h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={periodWeeklyGraph} barSize={32}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis
                    dataKey="day"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                  />
                  <Bar dataKey="activity" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Connected Platforms */}
        <Card className="border rounded-lg animate-fade-in" data-testid="platforms-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg font-heading font-semibold">Connected Platforms</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {dashboard?.connections?.length > 0 ? (
              dashboard.connections.map((conn) => {
                const Icon = platformIcons[conn.platform] || Activity;
                return (
                  <div
                    key={conn.platform}
                    className="flex items-center justify-between p-3 rounded-md bg-accent/50 transition-colors hover:bg-accent"
                    data-testid={`platform-${conn.platform}`}
                  >
                    <div className="flex items-center gap-3">
                      <Icon size={20} className={platformColors[conn.platform]} />
                      <div>
                        <p className="text-sm font-medium capitalize">{conn.platform}</p>
                        <p className="text-xs text-muted-foreground font-mono">{conn.username}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-xs">
                        {conn.status}
                      </Badge>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => handleSync(conn.platform)}
                        disabled={syncing === conn.platform}
                        data-testid={`sync-${conn.platform}`}
                      >
                        <RefreshCw size={14} className={syncing === conn.platform ? "animate-spin" : ""} />
                      </Button>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="text-center py-8">
                <Activity size={32} className="mx-auto text-muted-foreground/40 mb-3" />
                <p className="text-sm text-muted-foreground">No platforms connected</p>
                <Button variant="outline" size="sm" className="mt-3" asChild>
                  <a href="/settings" data-testid="connect-platforms-link">
                    Connect Now
                    <ExternalLink size={14} className="ml-1" />
                  </a>
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Contribution Heatmap */}
      <ContributionHeatmap period={period} customStart={customStart} customEnd={customEnd} />

      {/* Platform Details */}
      {dashboard?.platform_data?.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4" data-testid="platform-details">
          {dashboard.platform_data.map((pd) => (
            <PlatformDetailCard key={pd.platform} data={pd} />
          ))}
        </div>
      )}
    </div>
  );
}

function PlatformDetailCard({ data }) {
  const Icon = platformIcons[data.platform] || Activity;

  return (
    <Card className="border rounded-lg transition-all duration-200 hover:-translate-y-1 hover:shadow-md" data-testid={`detail-${data.platform}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Icon size={18} className={platformColors[data.platform]} />
          <CardTitle className="text-base font-heading font-semibold capitalize">{data.platform}</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        {data.platform === "leetcode" && (
          <div className="grid grid-cols-3 gap-3">
            <StatBlock label="Easy" value={data.easy || 0} className="text-green-500" />
            <StatBlock label="Medium" value={data.medium || 0} className="text-amber-500" />
            <StatBlock label="Hard" value={data.hard || 0} className="text-red-500" />
            <StatBlock label="Total" value={data.problems_solved || 0} />
            <StatBlock label="Rating" value={Math.round(data.contest_rating || 0)} />
            <StatBlock label="Streak" value={data.streak || 0} />
          </div>
        )}
        {data.platform === "github" && (
          <div className="grid grid-cols-3 gap-3">
            <StatBlock label="Repos" value={data.total_repos || 0} />
            <StatBlock label="Commits" value={data.total_commits || 0} />
            <StatBlock label="Stars" value={data.total_stars || 0} />
            <StatBlock label="Followers" value={data.followers || 0} />
            <StatBlock label="Languages" value={Object.keys(data.languages || {}).length} />
          </div>
        )}
        {data.platform === "codeforces" && (
          <div className="grid grid-cols-3 gap-3">
            <StatBlock label="Rating" value={data.rating || 0} />
            <StatBlock label="Max" value={data.max_rating || 0} />
            <StatBlock label="Rank" value={data.rank || "-"} />
            <StatBlock label="Solved" value={data.problems_solved || 0} />
            <StatBlock label="Contests" value={data.contests_participated || 0} />
          </div>
        )}
        {data.platform === "codechef" && (
          <div className="grid grid-cols-3 gap-3">
            <StatBlock label="Rating" value={data.rating || 0} />
            <StatBlock label="Max" value={data.max_rating || 0} />
            <StatBlock label="Stars" value={data.stars || "0"} />
            <StatBlock label="Solved" value={data.problems_solved || 0} />
            <StatBlock label="Global #" value={data.global_rank || "-"} />
          </div>
        )}
        {data.error && (
          <p className="text-xs text-destructive mt-2">{data.error}</p>
        )}
      </CardContent>
    </Card>
  );
}

function StatBlock({ label, value, className = "" }) {
  return (
    <div className="text-center">
      <p className={`text-lg font-mono font-bold ${className}`}>{value}</p>
      <p className="text-xs text-muted-foreground uppercase tracking-wider">{label}</p>
    </div>
  );
}
