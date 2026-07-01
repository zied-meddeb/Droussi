import { AlertCircle, X } from "lucide-react";
import { useEffect, useState } from "react";
import { onApiError } from "../../lib/errorBus";

interface Toast {
  id: number;
  message: string;
}

let nextId = 1;
const AUTO_DISMISS_MS = 6000;

/**
 * Listens for API errors on the error bus and shows them as dismissable
 * popups in the top-right corner. Mounted once, near the app root, so every
 * failed API call surfaces an indicative message no matter where it happened.
 */
export function ToastHost() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = (id: number) => setToasts((cur) => cur.filter((t) => t.id !== id));

  useEffect(() => {
    return onApiError((message) => {
      setToasts((cur) => {
        // Don't stack the exact same message on top of itself (e.g. polling).
        if (cur.some((t) => t.message === message)) return cur;
        const id = nextId++;
        window.setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
        return [...cur, { id, message }];
      });
    });
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 16,
        right: 16,
        zIndex: 2000,
        display: "flex",
        flexDirection: "column",
        gap: 10,
        maxWidth: "min(380px, calc(100vw - 32px))",
        pointerEvents: "none",
      }}
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="alert"
          className="dr-toast"
          style={{
            pointerEvents: "auto",
            display: "flex",
            alignItems: "flex-start",
            gap: 12,
            backgroundColor: "#fff5f2",
            border: "1px solid rgba(242,97,16,0.35)",
            borderRadius: 16,
            boxShadow: "rgba(120,40,0,0.14) 0px 12px 28px 0px",
            padding: "14px 14px 14px 16px",
            fontFamily: "'Geist','Inter',sans-serif",
          }}
        >
          <div style={{ flexShrink: 0, marginTop: 1 }}>
            <AlertCircle size={18} color="#e05a00" />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ fontFamily: "'Inter',sans-serif", fontSize: 13, fontWeight: 700, color: "#0a0d12", letterSpacing: "-0.02em", marginBottom: 2 }}>
              Something went wrong
            </p>
            <p style={{ fontSize: 13, color: "#535862", lineHeight: 1.45, letterSpacing: "-0.01em", wordBreak: "break-word" }}>
              {toast.message}
            </p>
          </div>
          <button
            onClick={() => dismiss(toast.id)}
            aria-label="Dismiss"
            style={{
              flexShrink: 0,
              width: 24,
              height: 24,
              borderRadius: "50%",
              border: "none",
              backgroundColor: "transparent",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "background-color 0.12s ease",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "rgba(224,90,0,0.12)")}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
          >
            <X size={14} color="#93979f" />
          </button>
        </div>
      ))}
    </div>
  );
}
