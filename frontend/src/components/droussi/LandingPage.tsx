import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  Download,
  MapPin,
  Settings2,
  Sparkles,
  Upload,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { useSearchParams } from "react-router-dom";
import { LoginModal } from "./LoginModal";
import uploadIllo from "../../assets/illustrations/upload.svg";
import shapeIllo from "../../assets/illustrations/shape_exam.svg";
import aiIllo from "../../assets/illustrations/AI.svg";
import exportIllo from "../../assets/illustrations/exportshare.svg";

interface LandingPageProps {
  onGoogleSignIn: () => void;
}

type IconType = LucideIcon;

/* ── The audiences the hero cycles through ───────────────────────────── */
const ROTATING = [
  { word: "Students", color: "#0069e0" },
  { word: "Professors", color: "#9552e0" },
  { word: "You", color: "#e05a00" },
];

/* ── Floating blurred blobs behind the hero (colour, size, position) ──── */
const BLOBS = [
  { c: "#f5a623", size: 200, top: "8%", left: "6%", cls: "dr-blob-1", op: 0.4 },
  { c: "#ffd23f", size: 360, top: "34%", left: "10%", cls: "dr-blob-2", op: 0.42 },
  { c: "#4fbeff", size: 300, top: "6%", left: "70%", cls: "dr-blob-3", op: 0.4 },
  { c: "#52d69a", size: 220, top: "48%", left: "56%", cls: "dr-blob-4", op: 0.38 },
  { c: "#c9a6f5", size: 320, top: "46%", left: "78%", cls: "dr-blob-5", op: 0.45 },
];

/* ── The road: process steps (alternating sides) + a conclusion ──────── */
interface Step {
  side: "left" | "right" | "center";
  Icon: IconType;
  tint: string;
  color: string;
  title: string;
  body: string;
  illo?: string;
  conclusion?: boolean;
}
const STEPS: Step[] = [
  { side: "left", Icon: Upload, tint: "#cce7ff", color: "#0069e0", title: "Drop in your material", body: "Add lecture PDFs. Droussi reads them so you never type a question by hand.", illo: uploadIllo },
  { side: "right", Icon: Settings2, tint: "#f1e6ff", color: "#9552e0", title: "Shape the exam", body: "Pick how many MCQs, short answers and essays you want, then set the difficulty and duration.", illo: shapeIllo },
  { side: "left", Icon: Sparkles, tint: "#ffe6d1", color: "#e05a00", title: "Let the AI write it", body: "Droussi drafts a complete, coherent exam from your material in seconds — questions, options and all.", illo: aiIllo },
  { side: "right", Icon: Download, tint: "#d3f6e3", color: "#1aa06d", title: "Export & share", body: "Download a clean PDF or an editable DOCX, ready to print, hand out, or upload to your LMS.", illo: exportIllo },
  { side: "center", Icon: CheckCircle2, tint: "#cce7ff", color: "#0069e0", title: "And that's it — exam ready", body: "Every file and every exam you make is saved to your repository. Reuse or regenerate any time.", conclusion: true },
];

/* Road geometry (in the SVG's 1000-wide viewBox coordinate space). */
const VB_W = 1000;
const FIRST_Y = 160;
const GAP_Y = 340;
const TAIL_Y = 150;
const ROAD_H = FIRST_Y + (STEPS.length - 1) * GAP_Y + TAIL_Y;
// gentle serpentine so the title/body have room on both sides of the road
const xForSide = (s: Step["side"]) => (s === "left" ? 435 : s === "right" ? 565 : 500);
// waypoints: top-center → each step → bottom-center (into the destination)
const WAYPOINTS = [
  { x: 500, y: 0 },
  ...STEPS.map((s, i) => ({ x: xForSide(s.side), y: FIRST_Y + i * GAP_Y })),
  { x: 500, y: ROAD_H },
];
const ROAD_D = WAYPOINTS.reduce((d, p, i) => {
  if (i === 0) return `M ${p.x} ${p.y}`;
  const prev = WAYPOINTS[i - 1];
  const dy = (p.y - prev.y) * 0.5;
  return `${d} C ${prev.x} ${prev.y + dy} ${p.x} ${p.y - dy} ${p.x} ${p.y}`;
}, "");

/* ── Cycle the rotating hero word ────────────────────────────────────── */
function useRotatingWord(count: number, ms: number) {
  const [i, setI] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setI((v) => (v + 1) % count), ms);
    return () => window.clearInterval(id);
  }, [count, ms]);
  return i;
}

/* ── Type a string out once it scrolls into view ─────────────────────── */
function useTypewriter(text: string, speed = 42) {
  const ref = useRef<HTMLHeadingElement>(null);
  const [out, setOut] = useState("");
  const [started, setStarted] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setStarted(true);
      setOut(text);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setStarted(true);
          io.disconnect();
        }
      },
      { threshold: 0.6 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [text]);
  useEffect(() => {
    if (!started) return;
    let i = 0;
    const id = window.setInterval(() => {
      i += 1;
      setOut(text.slice(0, i));
      if (i >= text.length) window.clearInterval(id);
    }, speed);
    return () => window.clearInterval(id);
  }, [started, text, speed]);
  return { ref, out, done: out.length >= text.length, started };
}

/* ── Add `is-visible` to `.dr-reveal` elements as they enter the view ─── */
function useScrollReveal() {
  useEffect(() => {
    const els = Array.from(document.querySelectorAll<HTMLElement>(".dr-reveal"));
    if (!("IntersectionObserver" in window)) {
      els.forEach((el) => el.classList.add("is-visible"));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("is-visible");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -8% 0px" },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
}

/* ── Simple mode: stack the road on small screens / reduced motion ───── */
function useSimpleMode() {
  const [simple, setSimple] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 860px), (prefers-reduced-motion: reduce)");
    const on = () => setSimple(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return simple;
}

export function LandingPage({ onGoogleSignIn }: LandingPageProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [loginOpen, setLoginOpen] = useState(false);
  const wordIndex = useRotatingWord(ROTATING.length, 2200);
  const simple = useSimpleMode();
  useScrollReveal();

  // Scroll-driven road: track progress + the arrow's position along the path.
  const roadRef = useRef<HTMLDivElement>(null);
  const pathRef = useRef<SVGPathElement>(null);
  const [len, setLen] = useState(0);
  const [prog, setProg] = useState(0);
  const [arrow, setArrow] = useState({ xPct: 50, yPct: 0, angle: 90, vy: 0 });

  const tw = useTypewriter("From a pile of notes to a finished exam");

  useEffect(() => {
    if (pathRef.current) setLen(pathRef.current.getTotalLength());
  }, [simple]);

  useEffect(() => {
    if (simple) return;
    let raf = 0;
    const update = () => {
      const el = roadRef.current;
      const path = pathRef.current;
      if (!el || !path) return;
      const rect = el.getBoundingClientRect();
      const vh = window.innerHeight;
      const p = Math.min(1, Math.max(0, (vh * 0.55 - rect.top) / rect.height));
      const L = path.getTotalLength();
      const pt = path.getPointAtLength(p * L);
      const pt2 = path.getPointAtLength(Math.min(L, p * L + 2));
      const angle = (Math.atan2(pt2.y - pt.y, pt2.x - pt.x) * 180) / Math.PI;
      setProg(p);
      setArrow({ xPct: (pt.x / VB_W) * 100, yPct: (pt.y / ROAD_H) * 100, angle, vy: pt.y });
    };
    const onScroll = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      cancelAnimationFrame(raf);
    };
  }, [simple]);

  // Open the modal automatically when redirected here with ?login.
  useEffect(() => {
    if (searchParams.has("login")) {
      setLoginOpen(true);
      searchParams.delete("login");
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const openLogin = () => setLoginOpen(true);
  const active = ROTATING[wordIndex];

  return (
    <div style={{ backgroundColor: "#ebf5ff", fontFamily: "'Geist','Inter',sans-serif", overflowX: "hidden" }}>

      {/* ── Nav (sticky) ── */}
      <nav
        style={{
          position: "sticky",
          top: 0,
          zIndex: 100,
          backgroundColor: "rgba(235,245,255,0.8)",
          backdropFilter: "blur(10px)",
          WebkitBackdropFilter: "blur(10px)",
          borderBottom: "1px solid rgba(83,88,98,0.08)",
        }}
      >
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "16px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {/* <div style={{ backgroundColor: "#0069e0", borderRadius: 10, width: 34, height: 34, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <BookOpen size={16} color="#fff" strokeWidth={2.5} />
            </div> */}
            <span style={{ fontFamily: "'Inter',sans-serif", fontWeight: 700, fontSize: 20, color: "#0a0d12", letterSpacing: "-0.03em" }}>Droussi</span>
          </div>
          <button
            onClick={openLogin}
            style={{ backgroundColor: "#181d27", color: "#fff", borderRadius: 9999, padding: "9px 22px", fontSize: 14, fontWeight: 500, border: "none", cursor: "pointer", letterSpacing: "-0.01em" }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#2d3444")}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "#181d27")}
          >
            Sign in
          </button>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section style={{ position: "relative", textAlign: "center", padding: "clamp(80px, 15vh, 150px) 24px 96px", overflow: "hidden" }}>
        {/* moving blurred blobs */}
        <div style={{ position: "absolute", inset: 0, zIndex: 0 }}>
          {BLOBS.map((b, i) => (
            <div
              key={i}
              className={`dr-blob ${b.cls}`}
              style={{ backgroundColor: b.c, width: b.size, height: b.size, top: b.top, left: b.left, opacity: b.op }}
            />
          ))}
        </div>

        <div style={{ position: "relative", zIndex: 1, maxWidth: 760, margin: "0 auto" }} className="mffb-stagger">
          <h1 style={{ fontFamily: "'Inter',sans-serif", fontSize: "clamp(46px, 7.5vw, 84px)", fontWeight: 700, color: "#0a0d12", letterSpacing: "-0.045em", lineHeight: 1.04, marginBottom: 26 }}>
            The platform for
            <br />
            <span key={wordIndex} className="dr-word" style={{ color: active.color }}>
              {active.word}
            </span>
          </h1>

          <p style={{ fontSize: 18, color: "#535862", fontWeight: 500, letterSpacing: "-0.01em", lineHeight: 1.6, maxWidth: 500, margin: "0 auto 40px", textWrap: "pretty" }}>
            Stop writing exams from a blank page. Upload your lessons, and let Droussi
            draft a complete, ready-to-use exam — start scribbling now.
          </p>

          <button
            onClick={openLogin}
            style={{ display: "inline-flex", alignItems: "center", gap: 8, backgroundColor: "#181d27", color: "#fff", borderRadius: 9999, padding: "15px 34px", fontSize: 15, fontWeight: 600, border: "none", cursor: "pointer", letterSpacing: "-0.01em", transition: "background-color 0.15s" }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#2d3444")}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "#181d27")}
          >
            Sign in to start <ArrowRight size={16} />
          </button>

          <div style={{ marginTop: 72, display: "flex", flexDirection: "column", alignItems: "center", gap: 6, color: "#93979f" }}>
            <span style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase" }}>See how it works</span>
            <ChevronDown size={22} className="dr-bob" />
          </div>
        </div>
      </section>

      {/* ── The journey (typewriter heading + scroll road) ── */}
      <section style={{ padding: "56px 24px 40px" }}>
        <div style={{ maxWidth: 980, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 8 }}>
            <p style={{ fontSize: 12, fontWeight: 700, color: "#0069e0", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 14 }}>The journey</p>
            <h2
              ref={tw.ref}
              style={{ fontFamily: "'Inter',sans-serif", fontSize: "clamp(28px, 4vw, 44px)", fontWeight: 700, color: "#0a0d12", letterSpacing: "-0.04em", lineHeight: 1.12, minHeight: "2.3em", maxWidth: 640, margin: "0 auto", textWrap: "balance" }}
            >
              {tw.out}
              {!tw.done && <span className="dr-caret" style={{ backgroundColor: "#0069e0", height: "0.82em", verticalAlign: "-0.06em" }} />}
            </h2>
          </div>

          {simple ? (
            /* Stacked fallback for small screens / reduced motion */
            <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 560, margin: "32px auto 0" }}>
              {STEPS.map((s, i) => (
                <div key={s.title} className="dr-reveal" style={{ display: "flex", gap: 16, alignItems: "center", backgroundColor: "#fafdff", border: "1px solid rgba(83,88,98,0.12)", borderRadius: 20, padding: "20px 22px" }}>
                  <div style={{ flexShrink: 0, width: 64, height: 64, borderRadius: 14, backgroundColor: s.tint, display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
                    {s.illo ? (
                      <img src={s.illo} alt={s.title} style={{ width: "78%", height: "78%", objectFit: "contain", outline: "none" }} />
                    ) : (
                      <s.Icon size={24} color={s.color} />
                    )}
                  </div>
                  <div>
                    <span style={{ fontFamily: "'Inter',sans-serif", fontSize: 12, fontWeight: 700, color: s.color, letterSpacing: "0.05em" }}>{s.conclusion ? "DESTINATION" : `STEP ${String(i + 1).padStart(2, "0")}`}</span>
                    <h3 style={{ fontFamily: "'Inter',sans-serif", fontSize: 17, fontWeight: 700, color: "#0a0d12", letterSpacing: "-0.03em", margin: "2px 0 6px" }}>{s.title}</h3>
                    <p style={{ fontSize: 14, color: "#535862", lineHeight: 1.6 }}>{s.body}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div ref={roadRef} style={{ position: "relative", marginTop: 24 }}>
              {/* the winding road */}
              <svg viewBox={`0 0 ${VB_W} ${ROAD_H}`} style={{ display: "block", width: "100%", height: "auto", overflow: "visible" }}>
                <path ref={pathRef} d={ROAD_D} fill="none" stroke="#cfe3f8" strokeWidth={5} strokeLinecap="round" />
                <path
                  d={ROAD_D}
                  fill="none"
                  stroke="#0069e0"
                  strokeWidth={5}
                  strokeLinecap="round"
                  strokeDasharray={len}
                  strokeDashoffset={len * (1 - prog)}
                />
              </svg>

              {/* travelling arrow — fades out as it reaches the destination */}
              <div style={{ position: "absolute", left: `${arrow.xPct}%`, top: `${arrow.yPct}%`, transform: "translate(-50%, -50%)", width: 36, height: 36, borderRadius: "50%", backgroundColor: "#0069e0", boxShadow: "0 4px 14px rgba(0,105,224,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 5, opacity: Math.max(0, Math.min(1, (0.96 - prog) / 0.05)), transition: "opacity 0.2s ease", pointerEvents: "none" }}>
                <div style={{ transform: `rotate(${arrow.angle}deg)`, display: "flex" }}>
                  <ArrowRight size={18} color="#fff" strokeWidth={2.75} />
                </div>
              </div>

              {/* steps: title on the road's side, body on the opposite side —
                  no icon, no card box. Illustrations live in the bottom stage. */}
              {STEPS.map((s, i) => {
                const node = WAYPOINTS[i + 1];
                const topPct = (node.y / ROAD_H) * 100;
                const revealed = arrow.vy >= node.y - 20 || prog >= 0.999;

                if (s.conclusion) {
                  return (
                    <div key={s.title} style={{ position: "absolute", top: `${topPct}%`, left: "20%", width: "60%", transform: "translateY(-50%)", zIndex: 3 }}>
                      <div style={{ opacity: revealed ? 1 : 0, transform: revealed ? "translateY(0)" : "translateY(24px)", transition: "opacity 0.5s ease, transform 0.5s cubic-bezier(0.16,1,0.3,1)", backgroundColor: "#479dff", borderRadius: 24, padding: "24px 28px", textAlign: "center", boxShadow: "0 14px 34px rgba(0,105,224,0.28)" }}>
                        <span style={{ fontFamily: "'Inter',sans-serif", fontSize: 12, fontWeight: 700, color: "rgba(255,255,255,0.75)", letterSpacing: "0.1em", textTransform: "uppercase" }}>Destination</span>
                        <h3 style={{ fontFamily: "'Inter',sans-serif", fontSize: 20, fontWeight: 700, color: "#fff", letterSpacing: "-0.03em", margin: "6px 0" }}>{s.title}</h3>
                        <p style={{ fontSize: 14, color: "rgba(255,255,255,0.85)", lineHeight: 1.6, maxWidth: 420, margin: "0 auto" }}>{s.body}</p>
                      </div>
                    </div>
                  );
                }

                const titleSide = s.side; // "left" | "right"
                const bodySide = s.side === "left" ? "right" : "left";
                const reveal = (extra?: CSSProperties): CSSProperties => ({
                  opacity: revealed ? 1 : 0,
                  transform: revealed ? "translateY(0)" : "translateY(24px)",
                  transition: "opacity 0.5s ease, transform 0.5s cubic-bezier(0.16,1,0.3,1)",
                  ...extra,
                });

                return (
                  <div key={s.title}>
                    {/* title — stays on the step's side */}
                    <div style={{ position: "absolute", top: `${topPct}%`, [titleSide]: "1%", width: "33%", transform: "translateY(-50%)", textAlign: titleSide === "left" ? "left" : "right", zIndex: 3 }}>
                      <div style={reveal()}>
                        <span style={{ fontFamily: "'Inter',sans-serif", fontSize: 13, fontWeight: 700, color: s.color, letterSpacing: "0.06em" }}>STEP {String(i + 1).padStart(2, "0")}</span>
                        <h3 style={{ fontFamily: "'Inter',sans-serif", fontSize: "clamp(20px, 2.4vw, 26px)", fontWeight: 700, color: "#0a0d12", letterSpacing: "-0.03em", marginTop: 6, lineHeight: 1.2 }}>{s.title}</h3>
                      </div>
                    </div>

                    {/* body — switched to the opposite side */}
                    <div style={{ position: "absolute", top: `${topPct}%`, [bodySide]: "1%", width: "33%", transform: "translateY(-50%)", textAlign: bodySide === "left" ? "left" : "right", zIndex: 3 }}>
                      <div style={reveal({ transitionDelay: "0.08s" })}>
                        <p style={{ fontSize: 15, color: "#535862", lineHeight: 1.65, letterSpacing: "-0.01em" }}>{s.body}</p>
                      </div>
                    </div>

                    {/* illustration — anchored to this step on the body side,
                        below the text, so it scrolls in and out with the step
                        (no more stacking at the bottom of the road) */}
                    {s.illo && (
                      <div style={{ position: "absolute", top: `${((node.y + 150) / ROAD_H) * 100}%`, [bodySide]: "2%", width: "40%", height: 240, transform: "translateY(-50%)", zIndex: 2, pointerEvents: "none" }}>
                        <img
                          src={s.illo}
                          alt={s.title}
                          style={{
                            width: "100%",
                            height: "100%",
                            objectFit: "contain",
                            objectPosition: bodySide === "left" ? "left center" : "right center",
                            outline: "none",
                            opacity: revealed ? 1 : 0,
                            transform: revealed ? "translateY(0)" : "translateY(28px)",
                            transition: "opacity 0.6s ease 0.1s, transform 0.6s cubic-bezier(0.16,1,0.3,1) 0.1s",
                          }}
                        />
                      </div>
                    )}
                  </div>
                );
              })}

              {/* destination pin — fades/pops in on top once the arrow arrives */}
              <div style={{ position: "absolute", top: "100%", left: "50%", transform: `translate(-50%, -60%) scale(${0.8 + 0.2 * Math.max(0, Math.min(1, (prog - 0.9) / 0.07))})`, display: "flex", flexDirection: "column", alignItems: "center", gap: 6, zIndex: 6, opacity: Math.max(0, Math.min(1, (prog - 0.9) / 0.07)), transition: "opacity 0.25s ease, transform 0.25s cubic-bezier(0.16,1,0.3,1)" }}>
                <div style={{ width: 40, height: 40, borderRadius: "50%", backgroundColor: "#0069e0", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 4px 14px rgba(0,105,224,0.4)" }}>
                  <MapPin size={20} color="#fff" />
                </div>
                <span style={{ fontSize: 12, fontWeight: 700, color: "#0069e0", letterSpacing: "0.04em", textTransform: "uppercase" }}>Your dashboard</span>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ── Destination: app skeleton (navbar + dashboard) ── */}
      <section style={{ padding: "60px 24px 90px" }}>
        <div style={{ maxWidth: 960, margin: "0 auto" }} className="dr-reveal">
          <AppSkeleton />
          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 12, marginTop: 28 }}>
            {[
              { Icon: Upload, tint: "#cce7ff", color: "#0069e0", label: "Upload material" },
              { Icon: Sparkles, tint: "#f1e6ff", color: "#9552e0", label: "Generate exams" },
              { Icon: Download, tint: "#d3f6e3", color: "#1aa06d", label: "Export to PDF / DOCX" },
            ].map((c) => (
              <div key={c.label} style={{ display: "inline-flex", alignItems: "center", gap: 8, backgroundColor: c.tint, borderRadius: 9999, padding: "8px 16px" }}>
                <c.Icon size={14} color={c.color} />
                <span style={{ fontSize: 13, fontWeight: 600, color: "#0a0d12", letterSpacing: "-0.01em" }}>{c.label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Final CTA ── */}
      <section style={{ padding: "40px 24px 100px" }}>
        <div style={{ maxWidth: 680, margin: "0 auto", textAlign: "center" }} className="dr-reveal">
          <div style={{ backgroundColor: "#479dff", borderRadius: 32, padding: "clamp(48px, 8vw, 64px) 40px" }}>
            <h2 style={{ fontFamily: "'Inter',sans-serif", fontSize: "clamp(28px, 4vw, 40px)", fontWeight: 700, color: "#fff", letterSpacing: "-0.04em", lineHeight: 1.12, marginBottom: 16, textWrap: "balance" }}>
              Ready to build your first exam?
            </h2>
            <p style={{ fontSize: 16, color: "rgba(255,255,255,0.85)", lineHeight: 1.6, marginBottom: 36, letterSpacing: "-0.01em" }}>
              Sign in with Google and go from uploaded notes to a finished exam in minutes.
            </p>
            <button
              onClick={openLogin}
              style={{ display: "inline-flex", alignItems: "center", gap: 8, backgroundColor: "#fff", color: "#181d27", borderRadius: 9999, padding: "15px 38px", fontSize: 15, fontWeight: 700, border: "none", cursor: "pointer", letterSpacing: "-0.02em", transition: "opacity 0.15s" }}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.9")}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
            >
              Sign in to start <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer style={{ borderTop: "1px solid rgba(83,88,98,0.1)", padding: "28px 24px", textAlign: "center" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, marginBottom: 10 }}>
          {/* <div style={{ backgroundColor: "#0069e0", borderRadius: 8, width: 26, height: 26, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <BookOpen size={12} color="#fff" strokeWidth={2.5} />
          </div> */}
          <span style={{ fontFamily: "'Inter',sans-serif", fontWeight: 700, fontSize: 15, color: "#0a0d12", letterSpacing: "-0.02em" }}>Droussi</span>
        </div>
        <p style={{ fontSize: 13, color: "#93979f" }}>AI-powered exam generation for educators and students.</p>
      </footer>

      {loginOpen && <LoginModal onClose={() => setLoginOpen(false)} onGoogleSignIn={onGoogleSignIn} />}
    </div>
  );
}

/* ── Skeleton of the real app: top navbar + dashboard ────────────────── */
function bar(w: number | string, h: number, color = "#cfe3f8", r = 6) {
  return <div className="dr-shimmer" style={{ width: w, height: h, borderRadius: r, backgroundColor: color }} />;
}

function AppSkeleton() {
  const statTints = ["#cce7ff", "#f1e6ff", "#d3f6e3"];
  const actionTints = ["#cce7ff", "#f1e6ff", "#ffe6d1", "#d3f6e3"];
  return (
    <div style={{ borderRadius: 20, border: "1px solid rgba(83,88,98,0.15)", boxShadow: "0 24px 60px -12px rgba(4,69,144,0.16)", overflow: "hidden", backgroundColor: "#ebf5ff" }}>
      {/* app navbar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", backgroundColor: "#fafdff", borderBottom: "1px solid rgba(83,88,98,0.1)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 30, height: 30, borderRadius: 9, backgroundColor: "#0069e0", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <BookOpen size={15} color="#fff" strokeWidth={2.5} />
          </div>
          {bar(72, 11, "#cce7ff")}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          {bar(46, 9)}
          {bar(46, 9)}
          {bar(46, 9)}
          <div style={{ width: 30, height: 30, borderRadius: "50%", backgroundColor: "#0069e0" }} />
        </div>
      </div>

      {/* dashboard body */}
      <div style={{ padding: "24px" }}>
        {/* greeting */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 22 }}>
          <div style={{ width: 44, height: 44, borderRadius: "50%", backgroundColor: "#cce7ff" }} />
          <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
            {bar(80, 8)}
            {bar(140, 12, "#cce7ff")}
          </div>
        </div>

        {/* stat cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14, marginBottom: 22 }}>
          {statTints.map((t, i) => (
            <div key={i} style={{ backgroundColor: "#fafdff", borderRadius: 16, border: "1px solid rgba(83,88,98,0.12)", padding: 18, display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ width: 38, height: 38, borderRadius: 12, backgroundColor: t }} />
              {bar(44, 18, "#cce7ff")}
              {bar("60%", 8)}
            </div>
          ))}
        </div>

        {/* quick actions */}
        <div style={{ marginBottom: 14 }}>{bar(120, 11, "#cce7ff")}</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14 }}>
          {actionTints.map((t, i) => (
            <div key={i} style={{ backgroundColor: "#fafdff", borderRadius: 16, border: "1px solid rgba(83,88,98,0.12)", padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: t }} />
              {bar("80%", 9)}
              {bar("55%", 8)}
              <div style={{ marginTop: 6 }}>{bar(16, 8)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
