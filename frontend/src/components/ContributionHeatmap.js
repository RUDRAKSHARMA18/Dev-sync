import React, { useState, useEffect, useMemo } from "react";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Calendar } from "lucide-react";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function getIntensityClass(count) {
  if (count === 0) return "bg-muted";
  if (count <= 2) return "bg-emerald-200 dark:bg-emerald-900";
  if (count <= 5) return "bg-emerald-400 dark:bg-emerald-700";
  if (count <= 10) return "bg-emerald-500 dark:bg-emerald-500";
  return "bg-emerald-600 dark:bg-emerald-400";
}

export default function ContributionHeatmap({ period = "365", customStart, customEnd }) {
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

  const filteredData = useMemo(() => {
    if (!heatmapData.length) return [];
    if (period === "custom" && customStart && customEnd) {
      return heatmapData.filter(d => d.date >= customStart && d.date <= customEnd);
    } else if (period !== "custom") {
      const days = parseInt(period, 10);
      return heatmapData.slice(-days);
    }
    return [];
  }, [heatmapData, period, customStart, customEnd]);

  const { totalActivity, activeDays, cells, monthLabels } = useMemo(() => {
    if (!filteredData.length) return { totalActivity: 0, activeDays: 0, cells: [], monthLabels: [] };

    let total = 0;
    let active = 0;
    const mLabels = [];
    let lastMonth = -1;
    let colIndex = 0;

    // Pad the start with empty cells if the first day isn't a Sunday
    const startWeekday = filteredData[0].weekday;
    const paddedCells = Array(startWeekday).fill(null);

    const dataCells = filteredData.map((day) => {
      total += day.count;
      if (day.count > 0) active++;

      // Track month labels (simplified, places label at approx column index)
      const currentWeek = Math.floor((paddedCells.length + filteredData.indexOf(day)) / 7);
      if (day.month !== lastMonth) {
        mLabels.push({ month: MONTHS[day.month - 1], weekIndex: currentWeek });
        lastMonth = day.month;
      }

      return day;
    });

    return { 
      totalActivity: total, 
      activeDays: active, 
      cells: [...paddedCells, ...dataCells],
      monthLabels: mLabels 
    };
  }, [filteredData]);

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
        <div className="flex mb-1 ml-8 relative h-4 overflow-hidden" data-testid="heatmap-month-labels">
          {monthLabels.map((ml, i) => (
            <div
              key={i}
              className="text-[10px] text-muted-foreground font-mono absolute"
              style={{ left: `${ml.weekIndex * 14}px` }}
            >
              {ml.month}
            </div>
          ))}
        </div>

        <div className="flex gap-2 overflow-x-auto pb-2" data-testid="heatmap-grid">
          {/* Day labels */}
          <div className="grid grid-rows-7 gap-[2px] pr-1 shrink-0">
            {["", "Mon", "", "Wed", "", "Fri", ""].map((label, i) => (
              <div key={i} className="h-[12px] text-[9px] text-muted-foreground font-mono flex items-center justify-end w-6">
                {label}
              </div>
            ))}
          </div>

          {/* Heatmap true CSS grid */}
          <TooltipProvider delayDuration={100}>
            <div className="grid grid-rows-7 grid-flow-col gap-[2px]">
              {cells.map((cell, i) => {
                if (!cell) {
                  return <div key={`empty-${i}`} className="w-[12px] h-[12px]" />;
                }

                return (
                  <Tooltip key={`day-${cell.date}`}>
                    <TooltipTrigger asChild>
                      <div
                        className={`w-[12px] h-[12px] rounded-[2px] transition-colors cursor-pointer hover:ring-1 hover:ring-foreground/30 ${getIntensityClass(cell.count)}`}
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
          </TooltipProvider>
        </div>

        {/* Legend */}
        <div className="flex items-center justify-end gap-1 mt-2">
          <span className="text-[10px] text-muted-foreground mr-1">Less</span>
          {[0, 2, 5, 10, 15].map((level) => (
            <div
              key={level}
              className={`w-[12px] h-[12px] rounded-[2px] ${getIntensityClass(level)}`}
            />
          ))}
          <span className="text-[10px] text-muted-foreground ml-1">More</span>
        </div>
      </CardContent>
    </Card>
  );
}
