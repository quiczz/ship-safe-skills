// Example: app/dashboard/loading.tsx  (Next.js App Router)
// Next shows this instantly while app/dashboard/page.tsx streams in.
// Match the sizes and spacing of page.tsx. Adjust the import path to where you put Skeleton.tsx.
import { Skeleton, SkeletonText, SkeletonAvatar, SkeletonRegion } from "@/components/Skeleton";

export default function Loading() {
  return (
    <SkeletonRegion label="Loading dashboard" className="dashboard">
      {/* page title + action button (same sizes as the real header) */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <Skeleton width={220} height={32} />
        <Skeleton width={120} height={40} radius={8} />
      </div>

      {/* stat cards: same grid and card height as the real ones */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16, marginBottom: 24 }}>
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} style={{ padding: 16, border: "1px solid transparent", height: 112 }}>
            <Skeleton width="40%" height={14} />
            <Skeleton width="60%" height={32} style={{ marginTop: 12 }} />
          </div>
        ))}
      </div>

      {/* list rows: avatar + two lines */}
      {Array.from({ length: 5 }, (_, i) => (
        <div key={i} style={{ display: "flex", gap: 12, alignItems: "center", height: 64 }}>
          <SkeletonAvatar size={40} />
          <div style={{ flex: 1 }}>
            <SkeletonText lines={2} lineHeight={22} textSize={14} />
          </div>
        </div>
      ))}
    </SkeletonRegion>
  );
}
