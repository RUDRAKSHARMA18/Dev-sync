import React, { useState, useEffect } from "react";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Target, Plus, Trash2, Sparkles, CheckCircle2 } from "lucide-react";

const categoryColors = {
  dsa: "bg-brand-dsa/10 text-brand-dsa border-brand-dsa/20",
  projects: "bg-brand-projects/10 text-brand-projects border-brand-projects/20",
  consistency: "bg-brand-warning/10 text-brand-warning border-brand-warning/20",
  general: "bg-primary/10 text-primary border-primary/20",
};

export default function GoalsPage() {
  const [goals, setGoals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [newGoal, setNewGoal] = useState({ title: "", description: "", target_value: 1, category: "general" });

  const fetchGoals = async () => {
    try {
      const { data } = await api.get("/goals");
      setGoals(data.goals || []);
    } catch (err) {
      console.error("Goals error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGoals();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await api.post("/goals", newGoal);
      setNewGoal({ title: "", description: "", target_value: 1, category: "general" });
      setShowCreate(false);
      fetchGoals();
    } catch (err) {
      console.error("Create goal error:", err);
    }
  };

  const handleAutoGenerate = async () => {
    setGenerating(true);
    try {
      await api.post("/goals/auto-generate");
      fetchGoals();
    } catch (err) {
      console.error("Auto-generate error:", err);
    } finally {
      setGenerating(false);
    }
  };

  const handleUpdateProgress = async (goalId, currentValue) => {
    try {
      await api.put(`/goals/${goalId}`, { current_value: currentValue });
      fetchGoals();
    } catch (err) {
      console.error("Update goal error:", err);
    }
  };

  const handleToggleComplete = async (goalId, completed) => {
    try {
      await api.put(`/goals/${goalId}`, { completed: !completed });
      fetchGoals();
    } catch (err) {
      console.error("Toggle complete error:", err);
    }
  };

  const handleDelete = async (goalId) => {
    try {
      await api.delete(`/goals/${goalId}`);
      fetchGoals();
    } catch (err) {
      console.error("Delete goal error:", err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const activeGoals = goals.filter((g) => !g.completed);
  const completedGoals = goals.filter((g) => g.completed);

  return (
    <div className="space-y-6" data-testid="goals-page">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div className="animate-fade-in">
          <h1 className="font-heading font-bold text-2xl sm:text-3xl tracking-tight">Goals</h1>
          <p className="text-muted-foreground text-sm mt-1">Track your progress and stay motivated</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleAutoGenerate}
            disabled={generating}
            data-testid="auto-generate-goals-button"
            className="gap-2"
          >
            <Sparkles size={14} className={generating ? "animate-spin" : ""} />
            Auto-Generate
          </Button>

          <Dialog open={showCreate} onOpenChange={setShowCreate}>
            <DialogTrigger asChild>
              <Button size="sm" data-testid="create-goal-button" className="gap-2">
                <Plus size={14} />
                New Goal
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle className="font-heading">Create Goal</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleCreate} className="space-y-4" data-testid="create-goal-form">
                <div className="space-y-2">
                  <Label>Title</Label>
                  <Input
                    value={newGoal.title}
                    onChange={(e) => setNewGoal({ ...newGoal, title: e.target.value })}
                    placeholder="e.g., Solve 50 LeetCode problems"
                    required
                    data-testid="goal-title-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Description</Label>
                  <Input
                    value={newGoal.description}
                    onChange={(e) => setNewGoal({ ...newGoal, description: e.target.value })}
                    placeholder="Describe your goal..."
                    data-testid="goal-description-input"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Target Value</Label>
                    <Input
                      type="number"
                      min={1}
                      value={newGoal.target_value}
                      onChange={(e) => setNewGoal({ ...newGoal, target_value: parseInt(e.target.value) || 1 })}
                      data-testid="goal-target-input"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Category</Label>
                    <Select value={newGoal.category} onValueChange={(v) => setNewGoal({ ...newGoal, category: v })}>
                      <SelectTrigger data-testid="goal-category-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="dsa">DSA</SelectItem>
                        <SelectItem value="projects">Projects</SelectItem>
                        <SelectItem value="consistency">Consistency</SelectItem>
                        <SelectItem value="general">General</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <Button type="submit" className="w-full" data-testid="submit-goal-button">Create Goal</Button>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Active Goals */}
      {activeGoals.length > 0 && (
        <div className="space-y-3">
          <h2 className="font-heading font-semibold text-lg">Active ({activeGoals.length})</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {activeGoals.map((goal, i) => (
              <GoalCard
                key={goal.goal_id}
                goal={goal}
                index={i}
                onUpdateProgress={handleUpdateProgress}
                onToggleComplete={handleToggleComplete}
                onDelete={handleDelete}
              />
            ))}
          </div>
        </div>
      )}

      {/* Completed Goals */}
      {completedGoals.length > 0 && (
        <div className="space-y-3">
          <h2 className="font-heading font-semibold text-lg text-muted-foreground">
            Completed ({completedGoals.length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {completedGoals.map((goal, i) => (
              <GoalCard
                key={goal.goal_id}
                goal={goal}
                index={i}
                onUpdateProgress={handleUpdateProgress}
                onToggleComplete={handleToggleComplete}
                onDelete={handleDelete}
              />
            ))}
          </div>
        </div>
      )}

      {goals.length === 0 && (
        <Card className="border rounded-lg" data-testid="no-goals-message">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <Target size={48} className="text-muted-foreground/30 mb-4" />
            <p className="text-muted-foreground mb-4">No goals yet. Create one or auto-generate based on your activity!</p>
            <Button onClick={handleAutoGenerate} disabled={generating} data-testid="empty-auto-generate">
              <Sparkles size={14} className="mr-2" />
              Auto-Generate Goals
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function GoalCard({ goal, index, onUpdateProgress, onToggleComplete, onDelete }) {
  const progress = goal.target_value > 0 ? Math.min(100, (goal.current_value / goal.target_value) * 100) : 0;
  const colorClass = categoryColors[goal.category] || categoryColors.general;

  return (
    <Card
      className={`border rounded-lg transition-all duration-200 hover:-translate-y-1 hover:shadow-md animate-fade-in ${goal.completed ? "opacity-60" : ""}`}
      style={{ animationDelay: `${index * 0.1}s` }}
      data-testid={`goal-card-${goal.goal_id}`}
    >
      <CardContent className="p-4 sm:p-5">
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="outline" className={`text-xs ${colorClass}`}>
                {goal.category}
              </Badge>
              {goal.completed && <CheckCircle2 size={16} className="text-brand-success" />}
            </div>
            <h3 className="font-heading font-semibold text-sm">{goal.title}</h3>
            {goal.description && (
              <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{goal.description}</p>
            )}
          </div>
          <div className="flex gap-1 ml-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => onToggleComplete(goal.goal_id, goal.completed)}
              data-testid={`toggle-goal-${goal.goal_id}`}
            >
              <CheckCircle2 size={14} className={goal.completed ? "text-brand-success" : "text-muted-foreground"} />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground hover:text-destructive"
              onClick={() => onDelete(goal.goal_id)}
              data-testid={`delete-goal-${goal.goal_id}`}
            >
              <Trash2 size={14} />
            </Button>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Progress</span>
            <span className="font-mono font-medium">{goal.current_value}/{goal.target_value}</span>
          </div>
          <Progress value={progress} className="h-2" />
        </div>

        {!goal.completed && (
          <div className="flex items-center gap-2 mt-3">
            <Input
              type="number"
              min={0}
              max={goal.target_value}
              defaultValue={goal.current_value}
              className="h-8 text-sm w-20"
              onBlur={(e) => {
                const val = parseInt(e.target.value);
                if (!isNaN(val) && val !== goal.current_value) {
                  onUpdateProgress(goal.goal_id, val);
                }
              }}
              data-testid={`goal-progress-input-${goal.goal_id}`}
            />
            <span className="text-xs text-muted-foreground">/ {goal.target_value}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
