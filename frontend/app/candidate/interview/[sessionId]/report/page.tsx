"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ThumbsUp, ThumbsDown, Download, ArrowLeft, Star, Loader2,
  CheckCircle2, AlertCircle, Lightbulb, BookOpen, Smile,
} from "lucide-react";
import { useApiQuery } from "@/hooks/use-api";
import { interviewService } from "@/lib/api/services";
import { Card, CardContent, ScoreRing, Skeleton, Button } from "@/components/ui";
import { useToast } from "@/store/use-ui-store";
import type { FeedbackReport } from "@/types";

export default function InterviewReportPage() {
  const params = useParams<{ sessionId: string }>();
  const router = useRouter();
  const { toast } = useToast();
  const [rating, setRating] = useState<number | null>(null);
  const [submittingRating, setSubmittingRating] = useState(false);

  const { data: report, isLoading, isError } = useApiQuery<FeedbackReport>({
    url: `/interviews/sessions/${params.sessionId}/report/`,
    retry: 3,
    retryDelay: 2500,
  });

  const submitRating = async (score: number) => {
    setRating(score);
    setSubmittingRating(true);
    try {
      await interviewService.submitRating(params.sessionId, score);
      toast.success("Thanks for the feedback!");
    } catch {
      toast.error("Couldn't submit your rating");
    } finally {
      setSubmittingRating(false);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto space-y-6 py-8">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError || !report) {
    return (
      <div className="max-w-md mx-auto py-24 text-center space-y-4">
        <Loader2 className="w-6 h-6 text-primary animate-spin mx-auto" />
        <h2 className="font-display font-semibold text-foreground">Still generating your report</h2>
        <p className="text-sm text-muted-foreground">
          The Feedback Agent is putting together your scored breakdown — this usually takes under a minute.
        </p>
        <Button variant="outline" onClick={() => router.refresh()}>
          Check again
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto py-8 px-6 space-y-6 animate-fade-in">
      <button
        type="button"
        onClick={() => router.push("/candidate/history")}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> Back to history
      </button>

      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-foreground">Your interview report</h1>
          <p className="text-sm text-muted-foreground mt-1">{report.summary}</p>
        </div>
        {report.pdfUrl && (
          <a
            href={report.pdfUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-lg border border-border hover:bg-white/5 transition-colors flex-shrink-0"
          >
            <Download className="w-4 h-4" /> Download PDF
          </a>
        )}
      </div>

      {/* Scores */}
      <Card className="p-6">
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          {[
            { label: "Overall", value: report.scores.overall },
            { label: "Communication", value: report.scores.communication },
            { label: "Technical", value: report.scores.technical },
            { label: "Behavioral", value: report.scores.behavioral },
            { label: "Confidence", value: report.scores.confidence },
          ].map((item) => (
            <div key={item.label} className="flex flex-col items-center gap-2">
              <ScoreRing score={item.value} size={72} strokeWidth={6} />
              <span className="text-xs text-muted-foreground text-center">{item.label}</span>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid sm:grid-cols-2 gap-5">
        <ReportSection icon={CheckCircle2} iconClass="text-success" title="Strengths" items={report.strengths} />
        <ReportSection icon={AlertCircle} iconClass="text-warning" title="Areas to improve" items={report.weaknesses} />
      </div>

      <ReportSection icon={Lightbulb} iconClass="text-accent" title="Suggestions" items={report.suggestions} />

      {report.sentimentDistribution && Object.keys(report.sentimentDistribution).length > 0 && (
        <Card>
          <CardContent className="p-6">
            <h2 className="font-display font-semibold text-foreground flex items-center gap-2 mb-3">
              <Smile className="w-4 h-4 text-primary" /> Emotional tone
            </h2>
            <div className="flex flex-wrap gap-2">
              {Object.entries(report.sentimentDistribution)
                .sort((a, b) => b[1] - a[1])
                .map(([label, count]) => {
                  const total = Object.values(report.sentimentDistribution ?? {}).reduce((sum, n) => sum + n, 0);
                  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                  return (
                    <span
                      key={label}
                      className="text-xs font-medium px-3 py-1.5 rounded-full border border-border text-muted-foreground capitalize"
                    >
                      {label} · {pct}%
                    </span>
                  );
                })}
            </div>
          </CardContent>
        </Card>
      )}

      {report.exampleBetterAnswers.length > 0 && (
        <Card>
          <CardContent className="p-6 space-y-5">
            <h2 className="font-display font-semibold text-foreground flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-primary" /> Stronger versions of your answers
            </h2>
            {report.exampleBetterAnswers.map((ex, i) => (
              <div key={i} className="space-y-2 pb-4 border-b border-border last:border-0 last:pb-0">
                <p className="text-sm font-medium text-foreground">{ex.question}</p>
                <p className="text-sm text-muted-foreground">
                  <span className="text-muted-foreground/70">You said: </span>
                  {ex.your_answer}
                </p>
                <p className="text-sm text-primary">
                  <span className="text-primary/70">Stronger: </span>
                  {ex.better_answer}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <ReportSection icon={Star} iconClass="text-primary" title="Recommended next practice" items={report.recommendedPractice} />

      {/* Rating */}
      <Card className="p-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <p className="text-sm font-medium text-foreground">Was this feedback helpful?</p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => submitRating(5)}
              disabled={submittingRating}
              className={`p-2 rounded-lg border transition-colors ${
                rating === 5 ? "border-success bg-success/10 text-success" : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              <ThumbsUp className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => submitRating(2)}
              disabled={submittingRating}
              className={`p-2 rounded-lg border transition-colors ${
                rating === 2 ? "border-error bg-error/10 text-error" : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              <ThumbsDown className="w-4 h-4" />
            </button>
          </div>
        </div>
      </Card>

      <div className="flex justify-center pt-2">
        <Button onClick={() => router.push("/candidate/practice")}>Practice again</Button>
      </div>
    </div>
  );
}

function ReportSection({
  icon: Icon,
  iconClass,
  title,
  items,
}: {
  icon: typeof CheckCircle2;
  iconClass: string;
  title: string;
  items: string[];
}) {
  return (
    <Card>
      <CardContent className="p-6">
        <h2 className="font-display font-semibold text-foreground flex items-center gap-2 mb-3">
          <Icon className={`w-4 h-4 ${iconClass}`} /> {title}
        </h2>
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing recorded for this section.</p>
        ) : (
          <ul className="space-y-2">
            {items.map((item, i) => (
              <li key={i} className="text-sm text-muted-foreground flex gap-2">
                <span className="text-muted-foreground/50">—</span>
                {item}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
