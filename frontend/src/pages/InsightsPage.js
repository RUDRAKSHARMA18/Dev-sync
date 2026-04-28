import React, { useState, useEffect } from "react";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Lightbulb, AlertTriangle, Sparkles, RefreshCw, Brain, Trophy, Target, Activity } from "lucide-react";

export default function InsightsPage() {
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [hasData, setHasData] = useState(false);

  useEffect(() => {
    const fetchCachedInsights = async () => {
      try {
        const { data } = await api.get("/insights");
        if (data && data.insights && data.insights.length > 0) {
          setInsights(data);
          setHasData(true);
        }
      } catch (err) {
        console.error("Insights error:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchCachedInsights();
  }, []);

  const handleGenerate = async () => {
    setRegenerating(true);
    try {
      const { data } = await api.post("/insights/regenerate");
      setInsights(data);
      setHasData(true);
    } catch (err) {
      console.error("Generate error:", err);
    } finally {
      setRegenerating(false);
    }
  };

  const getTimeAgo = (dateStr) => {
    if (!dateStr) return "";
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins} minute${mins !== 1 ? "s" : ""} ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours} hour${hours !== 1 ? "s" : ""} ago`;
    const days = Math.floor(hours / 24);
    return `${days} day${days !== 1 ? "s" : ""} ago`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-12 h-12 border-4 border-primary/30 border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  // Header Banner Component
  const HeaderBanner = () => (
    <div className="relative overflow-hidden rounded-2xl bg-card border shadow-sm mb-8 animate-fade-in group">
      {/* Background Glows */}
      <div className="absolute -top-24 -right-24 w-64 h-64 bg-primary/20 rounded-full blur-3xl opacity-50 transition-opacity duration-700 group-hover:opacity-70 pointer-events-none" />
      <div className="absolute -bottom-24 -left-24 w-80 h-80 bg-blue-500/10 rounded-full blur-3xl opacity-50 transition-opacity duration-700 group-hover:opacity-70 pointer-events-none" />
      
      <div className="relative z-10 p-6 sm:p-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Brain size={24} className="text-primary" />
            </div>
            <h1 className="font-heading font-bold text-3xl sm:text-4xl tracking-tight bg-clip-text text-transparent bg-gradient-to-br from-foreground to-foreground/70">
              AI Insights
            </h1>
          </div>
          <p className="text-muted-foreground mt-2 max-w-xl text-sm sm:text-base leading-relaxed">
            Powered by DevSync's local AI model. We analyze your cross-platform coding activity to provide personalized strengths, areas to improve, and actionable suggestions.
          </p>
        </div>
        
        {hasData && (
          <Button
            size="lg"
            onClick={handleGenerate}
            disabled={regenerating}
            data-testid="regenerate-insights-button"
            className="gap-2 shrink-0 relative overflow-hidden transition-all duration-300 hover:shadow-[0_0_20px_rgba(var(--primary),0.3)] hover:-translate-y-0.5"
          >
            <RefreshCw size={18} className={regenerating ? "animate-spin" : ""} />
            {regenerating ? "Analyzing..." : "Regenerate Analysis"}
            
            {/* Button Shine Effect */}
            <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent hover:animate-[shimmer_1.5s_infinite]" />
          </Button>
        )}
      </div>
    </div>
  );

  // No data yet — show Generate button
  if (!hasData && !regenerating) {
    return (
      <div className="space-y-6" data-testid="insights-page">
        <HeaderBanner />
        <Card className="border rounded-2xl overflow-hidden relative group animate-fade-in stagger-1">
          <div className="absolute inset-0 bg-gradient-to-b from-primary/5 to-transparent opacity-50" />
          <CardContent className="relative z-10 flex flex-col items-center justify-center py-24 gap-6">
            <div className="relative">
              <div className="absolute -inset-4 bg-primary/20 rounded-full blur-xl animate-pulse" />
              <div className="w-20 h-20 rounded-full bg-card border shadow-lg flex items-center justify-center relative z-10">
                <Sparkles size={40} className="text-primary" />
              </div>
            </div>
            <div className="text-center space-y-2 max-w-md">
              <h2 className="font-heading font-bold text-2xl">Ready for Analysis</h2>
              <p className="text-muted-foreground">
                We'll scan your GitHub commits, LeetCode submissions, and Codeforces history to generate a personalized growth profile. This usually takes 15-30 seconds.
              </p>
            </div>
            <Button size="lg" onClick={handleGenerate} className="gap-2 mt-4 transition-all duration-300 hover:shadow-lg hover:-translate-y-1" data-testid="generate-insights-button">
              <Sparkles size={18} />
              Generate My Insights
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Loading / regenerating state
  if (regenerating) {
    return (
      <div className="space-y-6" data-testid="insights-page">
        <HeaderBanner />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {[
            { color: "brand-success", label: "Strengths" },
            { color: "amber-500", label: "Areas to Improve" },
            { color: "blue-500", label: "Suggestions" }
          ].map((item, i) => (
            <Card key={i} className="border rounded-2xl overflow-hidden relative">
              <div className={`absolute top-0 left-0 w-full h-1 bg-${item.color}/40`} />
              <CardHeader className="pb-4">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl bg-${item.color}/10 flex items-center justify-center animate-pulse`} />
                  <div className="h-6 w-32 bg-muted rounded-md animate-pulse" />
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {[1, 2, 3].map((j) => (
                  <div key={j} className="h-20 w-full bg-muted/30 rounded-xl relative overflow-hidden">
                    <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-muted/40 to-transparent animate-[shimmer_1.5s_infinite]" />
                  </div>
                ))}
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="insights-page">
      <HeaderBanner />

      {/* AI Coach Banner */}
      {insights?.coach_message && (
        <div className="bg-gradient-to-br from-primary/10 to-transparent border border-primary/20 rounded-2xl p-6 flex flex-col sm:flex-row items-center sm:items-start gap-4 animate-fade-in stagger-1">
          <div className="w-12 h-12 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
            <Brain size={24} className="text-primary" />
          </div>
          <div className="text-center sm:text-left space-y-1">
            <p className="font-heading font-bold text-lg text-foreground tracking-tight">Your AI Coach Says:</p>
            <p className="text-muted-foreground leading-relaxed">{insights.coach_message}</p>
          </div>
        </div>
      )}

      {/* Pro Stats Grid */}
      {insights?.pro_stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 animate-fade-in stagger-2">
          <Card className="bg-card/50 border shadow-sm">
            <CardContent className="p-4 flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-yellow-500/10 flex items-center justify-center shrink-0">
                <Trophy size={20} className="text-yellow-500" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Est. Percentile</p>
                <p className="text-xl font-bold font-mono tracking-tighter">{insights.pro_stats.estimated_percentile}</p>
              </div>
            </CardContent>
          </Card>
          
          <Card className="bg-card/50 border shadow-sm">
            <CardContent className="p-4 flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center shrink-0">
                <Target size={20} className="text-blue-500" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Strongest Domain</p>
                <p className="text-xl font-bold font-heading truncate max-w-[150px] sm:max-w-xs">{insights.pro_stats.strongest_domain}</p>
              </div>
            </CardContent>
          </Card>
          
          <Card className="bg-card/50 border shadow-sm">
            <CardContent className="p-4 flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center shrink-0">
                <Activity size={20} className="text-green-500" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Consistency</p>
                <p className="text-xl font-bold font-mono tracking-tighter">{insights.pro_stats.consistency_rating}</p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 pt-2">
        {/* Strengths */}
        <Card className="border-brand-success/20 rounded-2xl overflow-hidden relative group animate-fade-in stagger-1 hover:shadow-lg transition-shadow duration-500" data-testid="insights-card">
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-brand-success to-emerald-400 opacity-70" />
          <div className="absolute top-0 left-0 w-full h-32 bg-gradient-to-b from-brand-success/5 to-transparent pointer-events-none" />
          
          <CardHeader className="pb-4 relative z-10">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-brand-success/10 flex items-center justify-center shadow-inner">
                <Brain size={20} className="text-brand-success" />
              </div>
              <CardTitle className="text-lg font-heading tracking-tight">Strengths</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 relative z-10">
            {insights?.insights?.map((insight, i) => (
              <div key={i} className="flex gap-4 p-4 rounded-xl bg-card border shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-md hover:border-brand-success/30 group/item" data-testid={`insight-item-${i}`}>
                <div className="w-8 h-8 rounded-full bg-brand-success/10 flex items-center justify-center shrink-0 group-hover/item:bg-brand-success group-hover/item:text-white transition-colors">
                  <Lightbulb size={16} className="text-brand-success group-hover/item:text-white" />
                </div>
                <p className="text-sm leading-relaxed text-foreground/90">{insight}</p>
              </div>
            ))}
            {(!insights?.insights || insights.insights.length === 0) && (
              <div className="p-6 text-center border border-dashed rounded-xl bg-muted/30">
                <p className="text-sm text-muted-foreground">Connect more platforms to get strengths insights.</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Areas to Improve */}
        <Card className="border-amber-500/20 rounded-2xl overflow-hidden relative group animate-fade-in stagger-2 hover:shadow-lg transition-shadow duration-500" data-testid="weaknesses-card">
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-amber-500 to-orange-400 opacity-70" />
          <div className="absolute top-0 left-0 w-full h-32 bg-gradient-to-b from-amber-500/5 to-transparent pointer-events-none" />
          
          <CardHeader className="pb-4 relative z-10">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center shadow-inner">
                <AlertTriangle size={20} className="text-amber-500" />
              </div>
              <CardTitle className="text-lg font-heading tracking-tight">Areas to Improve</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 relative z-10">
            {insights?.weaknesses?.map((weakness, i) => (
              <div key={i} className="flex gap-4 p-4 rounded-xl bg-card border shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-md hover:border-amber-500/30 group/item" data-testid={`weakness-item-${i}`}>
                <div className="w-8 h-8 rounded-full bg-amber-500/10 flex items-center justify-center shrink-0 group-hover/item:bg-amber-500 group-hover/item:text-white transition-colors">
                  <AlertTriangle size={16} className="text-amber-500 group-hover/item:text-white" />
                </div>
                <p className="text-sm leading-relaxed text-foreground/90">{weakness}</p>
              </div>
            ))}
            {(!insights?.weaknesses || insights.weaknesses.length === 0) && (
              <div className="p-6 text-center border border-dashed rounded-xl bg-muted/30">
                <p className="text-sm text-muted-foreground">No weaknesses identified yet. Keep it up!</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Suggestions */}
        <Card className="border-blue-500/20 rounded-2xl overflow-hidden relative group animate-fade-in stagger-3 hover:shadow-lg transition-shadow duration-500" data-testid="suggestions-card">
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 to-indigo-400 opacity-70" />
          <div className="absolute top-0 left-0 w-full h-32 bg-gradient-to-b from-blue-500/5 to-transparent pointer-events-none" />
          
          <CardHeader className="pb-4 relative z-10">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center shadow-inner">
                <Sparkles size={20} className="text-blue-500" />
              </div>
              <CardTitle className="text-lg font-heading tracking-tight">Suggestions</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 relative z-10">
            {insights?.suggestions?.map((suggestion, i) => (
              <div key={i} className="flex gap-4 p-4 rounded-xl bg-card border shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-md hover:border-blue-500/30 group/item" data-testid={`suggestion-item-${i}`}>
                <div className="w-8 h-8 rounded-full bg-blue-500/10 flex items-center justify-center shrink-0 group-hover/item:bg-blue-500 group-hover/item:text-white transition-colors">
                  <Sparkles size={16} className="text-blue-500 group-hover/item:text-white" />
                </div>
                <p className="text-sm leading-relaxed text-foreground/90">{suggestion}</p>
              </div>
            ))}
            {(!insights?.suggestions || insights.suggestions.length === 0) && (
              <div className="p-6 text-center border border-dashed rounded-xl bg-muted/30">
                <p className="text-sm text-muted-foreground">No suggestions available at the moment.</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {insights?.generated_at && (
        <div className="flex justify-center mt-8 animate-fade-in stagger-4">
          <div className="px-4 py-2 rounded-full bg-muted/30 border text-xs text-muted-foreground">
            Analysis completed {getTimeAgo(insights.generated_at)}
          </div>
        </div>
      )}
    </div>
  );
}
