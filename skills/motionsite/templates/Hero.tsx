// Motionsite - React hero with a video that respects reduced motion, data saver and visibility.
// Styles: reuse the .hero, .hero-media, .hero-video, .word, .lead, .cta-row, .btn CSS from templates/site.html
// (copy it into your global CSS or Tailwind layer). Works in client components ("use client" in Next.js).
"use client";
import * as React from "react";

type HeroProps = {
  title: string;
  lead: string;
  primary: { label: string; href: string };
  secondary?: { label: string; href: string };
  videoMp4?: string;
  videoWebm?: string;
  poster?: string;
};

export function Hero({ title, lead, primary, secondary, videoMp4, videoWebm, poster }: HeroProps) {
  const videoRef = React.useRef<HTMLVideoElement>(null);
  const [ready, setReady] = React.useState(false);
  const [paused, setPaused] = React.useState(false);
  const userPaused = React.useRef(false);

  React.useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const saveData = (navigator as any).connection?.saveData;
    if (reduce || saveData) return; // poster only
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) {
        if (!userPaused.current) v.play().then(() => setReady(true)).catch(() => {});
      } else {
        v.pause();
      }
    }, { threshold: 0.1 });
    io.observe(v);
    return () => io.disconnect();
  }, []);

  const toggle = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) { userPaused.current = false; v.play().catch(() => {}); setPaused(false); }
    else { userPaused.current = true; v.pause(); setPaused(true); }
  };

  const words = title.split(/\s+/);
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero-media" aria-hidden="true">
        {(videoMp4 || videoWebm) && (
          <video
            ref={videoRef}
            className={`hero-video ${ready ? "is-ready" : ""}`}
            muted loop playsInline preload="metadata" poster={poster} width={1920} height={1080} tabIndex={-1}
          >
            {videoWebm && <source src={videoWebm} type="video/webm" />}
            {videoMp4 && <source src={videoMp4} type="video/mp4" />}
          </video>
        )}
      </div>
      <div className="wrap hero-inner">
        <h1 id="hero-title" aria-label={title}>
          {words.map((w, i) => (
            <span key={i} className="word" aria-hidden="true" style={{ ["--i" as any]: i }}>{w} </span>
          ))}
        </h1>
        <p className="lead">{lead}</p>
        <div className="cta-row">
          <a className="btn btn-primary" href={primary.href}>{primary.label}</a>
          {secondary && <a className="btn btn-ghost glass" href={secondary.href}>{secondary.label}</a>}
        </div>
      </div>
      {(videoMp4 || videoWebm) && (
        <button className="pause glass is-visible" type="button" onClick={toggle} aria-label={paused ? "Play background video" : "Pause background video"}>
          {paused ? "Play video" : "Pause video"}
        </button>
      )}
    </section>
  );
}
