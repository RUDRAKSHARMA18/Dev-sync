import React, { useState, useEffect } from "react";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { Gauge, TrendingUp, Code2, GitBranch, Calendar } from "lucide-react";

const COLORS = {
  dsa: "#8B5CF6",
  projects: "#EC4899",
  consistency: "#F59E0B",
};

export default function ReadinessPage() {
  const [readiness, setReadiness] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchReadiness = async () => {
      try {
        const { data } = await api.get("/readiness");
        setReadiness(data);
      } catch (err) {
        console.error("Readiness error:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchReadiness();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const pieData = [
    { name: "DSA", value: (readiness?.dsa?.score || 0) * 0.45, weight: 45, rawScore: readiness?.dsa?.score || 0 },
    { name: "Projects", value: (readiness?.projects?.score || 0) * 0.30, weight: 30, rawScore: readiness?.projects?.score || 0 },
    { name: "Consistency", value: (readiness?.consistency?.score || 0) * 0.25, weight: 25, rawScore: readiness?.consistency?.score || 0 },
  ];

  const totalScore = readiness?.total_score || 0;

  const getScoreLabel = (score) => {
    if (score >= 80) return { text: "Excellent", color: "text-brand-success" };
    if (score >= 60) return { text: "Good", color: "text-primary" };
    if (score >= 40) return { text: "Improving", color: "text-brand-warning" };
    return { text: "Getting Started", color: "text-muted-foreground" };
  };

  const scoreLabel = getScoreLabel(totalScore);

  return (
    <div className="space-y-6" data-testid="readiness-page">
      <div className="animate-fade-in">
        <h1 className="font-heading font-bold text-2xl sm:text-3xl tracking-tight">Readiness Score</h1>
        <p className="text-muted-foreground text-sm mt-1">Your developer interview readiness breakdown</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        {/* Score Donut */}
        <Card className="lg:col-span-1 border rounded-lg animate-fade-in stagger-1" data-testid="score-donut-card">
          <CardContent className="flex flex-col items-center justify-center py-8">
            <div className="relative w-52 h-52">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={65}
                    outerRadius={90}
                    paddingAngle={3}
                    dataKey="value"
                    strokeWidth={0}
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={index} fill={Object.values(COLORS)[index]} />
                    ))}
                  </Pie>
                  <Tooltip
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const d = payload[0].payload;
                        return (
                          <div className="bg-card border border-border rounded-lg p-3 shadow-md">
                            <p className="font-heading font-semibold text-sm">{d.name}</p>
                            <p className="text-xs text-muted-foreground">Score: {d.rawScore.toFixed(1)}%</p>
                            <p className="text-xs text-muted-foreground">Weight: {d.weight}%</p>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              {/* Center score */}
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-4xl font-mono font-bold tracking-tighter" data-testid="total-score">
                  {totalScore.toFixed(0)}
                </span>
                <span className={`text-xs font-medium ${scoreLabel.color}`}>{scoreLabel.text}</span>
              </div>
            </div>

            {/* Legend */}
            <div className="flex gap-4 mt-6">
              {pieData.map((d, i) => (
                <div key={d.name} className="flex items-center gap-1.5">
                  <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: Object.values(COLORS)[i] }} />
                  <span className="text-xs text-muted-foreground">{d.name} ({d.weight}%)</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Score Breakdown */}
        <div className="lg:col-span-2 space-y-4">
          {/* DSA */}
          <Card className="border rounded-lg animate-fade-in stagger-2" data-testid="dsa-score-card">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-brand-dsa/10 flex items-center justify-center">
                    <Code2 size={20} className="text-brand-dsa" />
                  </div>
                  <div>
                    <h3 className="font-heading font-semibold">DSA & Problem Solving</h3>
                    <p className="text-xs text-muted-foreground">Weight: 45%</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-mono font-bold" data-testid="dsa-score-value">{readiness?.dsa?.score?.toFixed(1) || 0}%</p>
                </div>
              </div>
              <div className="w-full bg-muted rounded-full h-3">
                <div
                  className="h-3 rounded-full transition-all duration-700"
                  style={{ width: `${readiness?.dsa?.score || 0}%`, backgroundColor: COLORS.dsa }}
                />
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                {readiness?.dsa?.problems_solved || 0} problems solved across platforms
              </p>
            </CardContent>
          </Card>

          {/* Projects */}
          <Card className="border rounded-lg animate-fade-in stagger-3" data-testid="projects-score-card">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-brand-projects/10 flex items-center justify-center">
                    <GitBranch size={20} className="text-brand-projects" />
                  </div>
                  <div>
                    <h3 className="font-heading font-semibold">Projects & GitHub</h3>
                    <p className="text-xs text-muted-foreground">Weight: 30%</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-mono font-bold" data-testid="projects-score-value">{readiness?.projects?.score?.toFixed(1) || 0}%</p>
                </div>
              </div>
              <div className="w-full bg-muted rounded-full h-3">
                <div
                  className="h-3 rounded-full transition-all duration-700"
                  style={{ width: `${readiness?.projects?.score || 0}%`, backgroundColor: COLORS.projects }}
                />
              </div>
            </CardContent>
          </Card>

          {/* Consistency */}
          <Card className="border rounded-lg animate-fade-in stagger-4" data-testid="consistency-score-card">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-brand-warning/10 flex items-center justify-center">
                    <Calendar size={20} className="text-brand-warning" />
                  </div>
                  <div>
                    <h3 className="font-heading font-semibold">Consistency</h3>
                    <p className="text-xs text-muted-foreground">Weight: 25%</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-mono font-bold" data-testid="consistency-score-value">{readiness?.consistency?.score?.toFixed(1) || 0}%</p>
                </div>
              </div>
              <div className="w-full bg-muted rounded-full h-3">
                <div
                  className="h-3 rounded-full transition-all duration-700"
                  style={{ width: `${readiness?.consistency?.score || 0}%`, backgroundColor: COLORS.consistency }}
                />
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                {readiness?.consistency?.streak || 0} day streak
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
