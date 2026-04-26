import React, { useState, useEffect } from "react";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Lightbulb, AlertTriangle, Sparkles, RefreshCw, Brain } from "lucide-react";

export default function InsightsPage() {
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);

  const fetchInsights = async () => {
    try {
      const { data } = await api.get("/insights");
      setInsights(data);
    } catch (err) {
      console.error("Insights error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInsights();
  }, []);

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const { data } = await api.post("/insights/regenerate");
      setInsights(data);
    } catch (err) {
      console.error("Regenerate error:", err);
    } finally {
      setRegenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="insights-page">
      <div className="flex items-start justify-between">
        <div className="animate-fade-in">
          <h1 className="font-heading font-bold text-2xl sm:text-3xl tracking-tight">AI Insights</h1>
          <p className="text-muted-foreground text-sm mt-1">Powered by GPT-5.2 analysis of your coding activity</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRegenerate}
          disabled={regenerating}
          data-testid="regenerate-insights-button"
          className="gap-2"
        >
          <RefreshCw size={14} className={regenerating ? "animate-spin" : ""} />
          Regenerate
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        {/* Insights */}
        <Card className="border rounded-lg animate-fade-in stagger-1" data-testid="insights-card">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center">
                <Brain size={16} className="text-primary" />
              </div>
              <CardTitle className="text-base font-heading">Key Insights</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {insights?.insights?.map((insight, i) => (
              <div key={i} className="flex gap-3 p-3 rounded-md bg-accent/50" data-testid={`insight-item-${i}`}>
                <Lightbulb size={16} className="text-brand-warning mt-0.5 shrink-0" />
                <p className="text-sm leading-relaxed">{insight}</p>
              </div>
            ))}
            {(!insights?.insights || insights.insights.length === 0) && (
              <p className="text-sm text-muted-foreground text-center py-4">Connect platforms to get insights</p>
            )}
          </CardContent>
        </Card>

        {/* Weaknesses */}
        <Card className="border rounded-lg animate-fade-in stagger-2" data-testid="weaknesses-card">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-md bg-destructive/10 flex items-center justify-center">
                <AlertTriangle size={16} className="text-destructive" />
              </div>
              <CardTitle className="text-base font-heading">Areas to Improve</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {insights?.weaknesses?.map((weakness, i) => (
              <div key={i} className="flex gap-3 p-3 rounded-md bg-accent/50" data-testid={`weakness-item-${i}`}>
                <AlertTriangle size={16} className="text-destructive mt-0.5 shrink-0" />
                <p className="text-sm leading-relaxed">{weakness}</p>
              </div>
            ))}
            {(!insights?.weaknesses || insights.weaknesses.length === 0) && (
              <p className="text-sm text-muted-foreground text-center py-4">No weaknesses identified yet</p>
            )}
          </CardContent>
        </Card>

        {/* Suggestions */}
        <Card className="border rounded-lg animate-fade-in stagger-3" data-testid="suggestions-card">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-md bg-brand-success/10 flex items-center justify-center">
                <Sparkles size={16} className="text-brand-success" />
              </div>
              <CardTitle className="text-base font-heading">Suggestions</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {insights?.suggestions?.map((suggestion, i) => (
              <div key={i} className="flex gap-3 p-3 rounded-md bg-accent/50" data-testid={`suggestion-item-${i}`}>
                <Sparkles size={16} className="text-brand-success mt-0.5 shrink-0" />
                <p className="text-sm leading-relaxed">{suggestion}</p>
              </div>
            ))}
            {(!insights?.suggestions || insights.suggestions.length === 0) && (
              <p className="text-sm text-muted-foreground text-center py-4">No suggestions yet</p>
            )}
          </CardContent>
        </Card>
      </div>

      {insights?.generated_at && (
        <p className="text-xs text-muted-foreground text-center">
          Last generated: {new Date(insights.generated_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}
