import React, { useState, useEffect, useMemo } from "react";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExternalLink, Sparkles, Code2, AlertTriangle, RefreshCw } from "lucide-react";

export default function ProblemsPage() {
  const [recommendations, setRecommendations] = useState([]);
  const [level, setLevel] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState("All");

  const fetchRecommendations = async (forceRefresh = false) => {
    if (forceRefresh) setRefreshing(true);
    try {
      if (forceRefresh) {
         // Optionally you could add an endpoint to clear cache, but standard fetch just gets it.
         // Let's assume a query param ?refresh=true would bypass cache if we implemented it, 
         // but for now we just call it.
      }
      const { data } = await api.get("/problems/recommendations");
      setRecommendations(data.recommendations || []);
      setLevel(data.level || "");
    } catch (err) {
      console.error("Recommendations error:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchRecommendations();
  }, []);

  const getDifficultyColor = (difficulty) => {
    switch (difficulty?.toLowerCase()) {
      case "easy": return "bg-green-500/10 text-green-500 border-green-500/20";
      case "medium": return "bg-yellow-500/10 text-yellow-500 border-yellow-500/20";
      case "hard": return "bg-red-500/10 text-red-500 border-red-500/20";
      default: return "bg-primary/10 text-primary border-primary/20";
    }
  };

  const topics = useMemo(() => {
    const t = new Set(recommendations.map(r => r.topic).filter(Boolean));
    return Array.from(t);
  }, [recommendations]);

  const filteredRecs = useMemo(() => {
    let result = recommendations;
    if (filter === "Recommended") {
      result = recommendations.filter(r => !r.solved);
    } else if (filter === "Solved") {
      result = recommendations.filter(r => r.solved);
    } else if (filter !== "All") {
      if (["Easy", "Medium", "Hard"].includes(filter)) {
        result = recommendations.filter(r => r.difficulty?.toLowerCase() === filter.toLowerCase());
      } else {
        result = recommendations.filter(r => r.topic === filter);
      }
    }
    return result;
  }, [recommendations, filter]);

  const handleMarkSolved = async (slug) => {
    try {
      await api.post(`/problems/${slug}/solved`);
      fetchRecommendations(true);
    } catch (err) {
      console.error("Mark solved error:", err);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        <p className="text-muted-foreground text-sm animate-pulse">Generating personalized coding problems...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="problems-page">
      <div className="flex flex-col sm:flex-row items-start justify-between gap-4 animate-fade-in">
        <div>
          <h1 className="font-heading font-bold text-2xl sm:text-3xl tracking-tight">Recommended Problems</h1>
          <p className="text-muted-foreground text-sm mt-1">AI-curated challenges tailored to your current skill level</p>
        </div>
        <div className="flex flex-col sm:flex-row items-end sm:items-center gap-3">
          {level && (
            <Badge variant="secondary" className="px-3 py-1 font-semibold text-sm">
              Your Level: {level} 🎯
            </Badge>
          )}
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => fetchRecommendations(true)}
            disabled={refreshing}
            className="gap-2"
          >
            <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
            Refresh Recommendations
          </Button>
        </div>
      </div>

      {recommendations.length > 0 && (
        <div className="flex flex-wrap gap-2 animate-fade-in stagger-1">
          <Button 
            variant={filter === "All" ? "default" : "outline"} 
            size="sm" 
            className="h-8 text-xs rounded-full"
            onClick={() => setFilter("All")}
          >
            All
          </Button>
          <Button 
            variant={filter === "Easy" ? "default" : "outline"} 
            size="sm" 
            className="h-8 text-xs rounded-full border-green-500/30 hover:bg-green-500/10 hover:text-green-500"
            onClick={() => setFilter("Easy")}
          >
            Easy
          </Button>
          <Button 
            variant={filter === "Medium" ? "default" : "outline"} 
            size="sm" 
            className="h-8 text-xs rounded-full border-yellow-500/30 hover:bg-yellow-500/10 hover:text-yellow-500"
            onClick={() => setFilter("Medium")}
          >
            Medium
          </Button>
          <Button 
            variant={filter === "Hard" ? "default" : "outline"} 
            size="sm" 
            className="h-8 text-xs rounded-full border-red-500/30 hover:bg-red-500/10 hover:text-red-500"
            onClick={() => setFilter("Hard")}
          >
            Hard
          </Button>
          {topics.map(t => (
            <Button 
              key={t}
              variant={filter === t ? "default" : "outline"} 
              size="sm" 
              className="h-8 text-xs rounded-full"
              onClick={() => setFilter(t)}
            >
              {t}
            </Button>
          ))}
          <div className="w-px h-6 bg-border mx-1" />
          <Button 
            variant={filter === "Recommended" ? "default" : "outline"} 
            size="sm" 
            className="h-8 text-xs rounded-full"
            onClick={() => setFilter("Recommended")}
          >
            Recommended
          </Button>
          <Button 
            variant={filter === "Solved" ? "default" : "outline"} 
            size="sm" 
            className="h-8 text-xs rounded-full border-brand-success/30 hover:bg-brand-success/10 hover:text-brand-success"
            onClick={() => setFilter("Solved")}
          >
            Solved
          </Button>
        </div>
      )}

      {filteredRecs.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredRecs.map((prob, i) => (
            <Card key={i} className={`border rounded-lg animate-fade-in stagger-${i + 1} transition-transform ${!prob.solved ? 'hover:-translate-y-1' : 'opacity-60'}`}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <CardTitle className={`text-base font-heading line-clamp-1 ${prob.solved ? 'line-through text-muted-foreground' : ''}`} title={prob.title}>
                      {prob.title}
                    </CardTitle>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className={`text-xs ${getDifficultyColor(prob.difficulty)}`}>
                        {prob.difficulty}
                      </Badge>
                      {prob.topic && (
                         <div className="flex items-center gap-1 text-xs text-muted-foreground">
                           <Code2 size={12} />
                           <span>{prob.topic}</span>
                         </div>
                      )}
                      {prob.solved && (
                        <Badge variant="outline" className="text-xs bg-brand-success/10 text-brand-success border-brand-success/20">
                          Solved
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground h-10 line-clamp-2">{prob.reason}</p>
                <div className="flex gap-2">
                  <Button asChild variant="outline" className="w-full gap-2">
                    <a href={`https://leetcode.com/problemset/all/?search=${encodeURIComponent(prob.title)}`} target="_blank" rel="noopener noreferrer">
                      Solve on LeetCode <ExternalLink size={14} />
                    </a>
                  </Button>
                  {!prob.solved && (
                    <Button 
                      variant="default" 
                      onClick={() => handleMarkSolved(prob.slug)}
                      className="gap-2"
                    >
                      Mark as Solved
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card className="border rounded-lg">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <AlertTriangle size={48} className="text-muted-foreground/30 mb-4" />
            <p className="text-muted-foreground">No recommendations match your filter.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
