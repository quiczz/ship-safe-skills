// Skeletonizer - React primitives. Needs templates/skeleton.css loaded once.
// Works in Next.js server components (no hooks, no "use client" needed).
import * as React from "react";

type Dim = number | string;
const px = (v?: Dim) => (typeof v === "number" ? `${v}px` : v);

type BlockProps = Omit<React.HTMLAttributes<HTMLSpanElement>, "children"> & {
  width?: Dim;
  height?: Dim;
  radius?: Dim;
  circle?: boolean;
};

/** One grey block. Give it the same size as the element it replaces. */
export function Skeleton({ width, height, radius, circle, className = "", style, ...rest }: BlockProps) {
  return (
    <span
      aria-hidden="true"
      className={["sk", circle ? "sk-circle" : "", className].filter(Boolean).join(" ")}
      style={{ width: px(width), height: px(height), borderRadius: circle ? undefined : px(radius), ...style }}
      {...rest}
    />
  );
}

/** N lines of text. Set lineHeight to the real line-height so the height matches. */
export function SkeletonText({
  lines = 3,
  lineHeight = 20,
  textSize = 14,
  gap,
  lastLineWidth = "60%",
}: {
  lines?: number;
  lineHeight?: number;
  textSize?: number;
  gap?: number;
  lastLineWidth?: Dim;
}) {
  // Each line takes `lineHeight` px in total, like real text, with a bar of `textSize` px inside it.
  const pad = gap ?? Math.max(0, (lineHeight - textSize) / 2);
  return (
    <div aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} style={{ height: lineHeight, paddingBlock: pad }}>
          <Skeleton height={textSize} width={i === lines - 1 && lines > 1 ? lastLineWidth : "100%"} style={{ height: "100%" }} />
        </div>
      ))}
    </div>
  );
}

export function SkeletonAvatar({ size = 40 }: { size?: number }) {
  return <Skeleton circle width={size} height={size} style={{ flexShrink: 0 }} />;
}

/**
 * Wrap a whole skeleton. Adds the accessibility pieces once:
 * role="status", aria-busy, and one hidden "Loading" message.
 * delayed=true keeps it invisible for the first 200 ms so fast loads do not flash.
 */
export function SkeletonRegion({
  label = "Loading",
  delayed = true,
  as: Tag = "div",
  className = "",
  children,
}: {
  label?: string;
  delayed?: boolean;
  as?: React.ElementType;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Tag role="status" aria-busy="true" className={[delayed ? "sk-delayed" : "", className].filter(Boolean).join(" ")}>
      <span className="sk-sr-only">{label}</span>
      {children}
    </Tag>
  );
}
