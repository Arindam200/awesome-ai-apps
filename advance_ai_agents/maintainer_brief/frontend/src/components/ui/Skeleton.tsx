import { Card } from "./Card";

/** Pulsing placeholder bar. Width via className (e.g. w-1/2). */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-[4px] bg-line ${className}`} />;
}

/** Loading state for the brief article (page + preview). */
export function BriefSkeleton() {
  return (
    <Card className="mt-8 px-8 py-8 sm:px-10">
      <Skeleton className="h-6 w-3/4" />
      <Skeleton className="mt-3 h-6 w-1/2" />
      <div className="mt-10 space-y-6">
        {[0, 1, 2].map((i) => (
          <div key={i}>
            <Skeleton className="h-3 w-40" />
            <Skeleton className="mt-4 h-5 w-2/3" />
            <Skeleton className="mt-2 h-4 w-5/6" />
            <div className="mt-3 flex gap-2">
              <Skeleton className="h-5 w-16" />
              <Skeleton className="h-5 w-16" />
              <Skeleton className="h-5 w-16" />
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

/** Loading state for list pages (signals / documents). */
export function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="mt-6 space-y-3">
      {Array.from({ length: rows }, (_, i) => (
        <Card key={i} className="p-4">
          <Skeleton className="h-3 w-32" />
          <Skeleton className="mt-2.5 h-5 w-2/3" />
          <Skeleton className="mt-2 h-4 w-1/2" />
        </Card>
      ))}
    </div>
  );
}
