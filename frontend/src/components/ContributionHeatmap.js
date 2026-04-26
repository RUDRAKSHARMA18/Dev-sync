import React, { useState, useEffect, useMemo } from "react";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Calendar } from "lucide-react";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function getColor(count, isDark) {
  if (count === 0) return isDark ? "#18181B" : "#F4F4F5";
  if (count <= 2) return isDark ? "#1E3A5F" : "#DBEAFE";
  if (count <= 5) return isDark ? "#1D4ED8" : "#93C5FD";
  if (count <= 10) return isDark ? "#2563EB" : "#60A5FA";
  return isDark ? "#3B82F6" : "#3B82F6";
}

export default function ContributionHeatmap() {
  const [heatmapData, setHeatmapData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchHeatmap = async () => {
      try {
        const { data } = await api.get("/heatmap");
        setHeatmapData(data.heatmap || []);
      } catch (err) {
        console.error("Heatmap error:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchHeatmap();
  }, []);

  const isDark = document.documentElement.classList.contains("dark");

  // Group data by weeks (columns) with weekday as row
  const { weeks, monthLabels, totalActivity, activeDays } = useMemo(() => {
    if (!heatmapData.length) return { weeks: [], monthLabels: [], totalActivity: 0, activeDays: 0 };

    const w = [];
    let currentWeek = [];
    let total = 0;
    let active = 0;
    const mLabels = [];
    let lastMonth = -1;

    heatmapData.forEach((day, i) => {
      total += day.count;
      if (day.count > 0) active++;

      if (day.weekday === 0 && currentWeek.length > 0) {
        w.push(currentWeek);
        currentWeek = [];
      }
      currentWeek.push(day);

      // Track month labels
      if (day.month !== lastMonth) {
        mLabels.push({ month: MONTHS[day.month - 1], weekIndex: w.length });
        lastMonth = day.month;
      }
    });
    if (currentWeek.length > 0) w.push(currentWeek);

    return { weeks: w, monthLabels: mLabels, totalActivity: total, activeDays: active };
  }, [heatmapData]);

  if (loading) {
    return (
      <Card className="border rounded-lg" data-testid="heatmap-loading">
        <CardContent className="flex items-center justify-center h-40">
          <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border rounded-lg animate-fade-in" data-testid="contribution-heatmap-card">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Calendar size={16} className="text-primary" />
            <CardTitle className="text-lg font-heading font-semibold">Contribution Activity</CardTitle>
          </div>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span><strong className="text-foreground font-mono">{totalActivity}</strong> contributions</span>
            <span><strong className="text-foreground font-mono">{activeDays}</strong> active days</span>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Month labels */}
        <div className="flex mb-1 ml-8" data-testid="heatmap-month-labels">
          {monthLabels.map((ml, i) => (
            <div
              key={i}
              className="text-[10px] text-muted-foreground font-mono"
              style={{ position: "relative", left: `${ml.weekIndex * 14}px` }}
            >
              {ml.month}
            </div>
          ))}
        </div>

        {/* Heatmap grid */}
        <div className="flex gap-[2px] overflow-x-auto pb-2" data-testid="heatmap-grid">
          {/* Day labels */}
          <div className="flex flex-col gap-[2px] mr-1 shrink-0">
            {["", "Mon", "", "Wed", "", "Fri", ""].map((label, i) => (
              <div key={i} className="h-[12px] text-[9px] text-muted-foreground font-mono flex items-center justify-end pr-1 w-6">
                {label}
              </div>
            ))}
          </div>

          <TooltipProvider delayDuration={100}>
            {weeks.map((week, wi) => (
              <div key={wi} className="flex flex-col gap-[2px]">
                {Array.from({ length: 7 }, (_, dayIndex) => {
                  const cell = week.find((d) => d.weekday === dayIndex);
                  if (!cell) return <div key={dayIndex} className="w-[12px] h-[12px]" />;

                  return (
                    <Tooltip key={dayIndex}>
                      <TooltipTrigger asChild>
                        <div
                          className="w-[12px] h-[12px] rounded-[2px] transition-colors cursor-pointer hover:ring-1 hover:ring-foreground/30"
                          style={{ backgroundColor: getColor(cell.count, isDark) }}
                          data-testid={`heatmap-cell-${cell.date}`}
                        />
                      </TooltipTrigger>
                      <TooltipContent side="top" className="text-xs">
                        <p className="font-mono font-semibold">{cell.count} contribution{cell.count !== 1 ? "s" : ""}</p>
                        <p className="text-muted-foreground">{cell.date}</p>
                      </TooltipContent>
                    </Tooltip>
                  );
                })}
              </div>
            ))}
          </TooltipProvider>
        </div>

        {/* Legend */}
        <div className="flex items-center justify-end gap-1 mt-2">
          <span className="text-[10px] text-muted-foreground mr-1">Less</span>
          {[0, 2, 5, 10, 15].map((level) => (
            <div
              key={level}
              className="w-[12px] h-[12px] rounded-[2px]"
              style={{ backgroundColor: getColor(level, isDark) }}
            />
          ))}
          <span className="text-[10px] text-muted-foreground ml-1">More</span>
        </div>
      </CardContent>
    </Card>
  );
}
