// SideMenu.jsx
import { useEffect, useRef, useState } from "react";
import FileUploader from "./FileUploader";
import "./SideMenu.scss";
import FileList from "./FileList";

export default function SideMenu() {
  const [open, setOpen] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);
  const [hoverOpen, setHoverOpen] = useState(false);
  const [showContent, setShowContent] = useState(false); // 👈 render-gate
  const asideRef = useRef(null);
  const hoverTimerRef = useRef(null);

  const handleUploaded = () => setRefreshToken(t => t + 1);

  const clearHoverTimer = () => {
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
  };

  const onMouseEnter = (e) => {
    if (open) return;
    if (e.target.closest(".menu-toggle")) return;
    clearHoverTimer();
    hoverTimerRef.current = setTimeout(() => setHoverOpen(true), 200); // intent delay
  };

  const onMouseLeave = () => {
    clearHoverTimer();
    setHoverOpen(false);
    // hide content immediately on hover-out
    if (!open) setShowContent(false);
  };

  // When width transition finishes, reveal content
  useEffect(() => {
    const el = asideRef.current;
    if (!el) return;

    const onTransitionEnd = (e) => {
      if (e.propertyName !== "width") return;
      if (open || hoverOpen) {
        setShowContent(true);  // finished expanding
      } else {
        setShowContent(false); // finished collapsing
      }
    };

    el.addEventListener("transitionend", onTransitionEnd);
    return () => el.removeEventListener("transitionend", onTransitionEnd);
  }, [open, hoverOpen]);

  // If user clicks to open, we can show content right after width anim ends too.
  const toggleOpen = () => {
    clearHoverTimer();
    setHoverOpen(false);
    setShowContent(false); // wait for transition
    setOpen(v => !v);
  };

  useEffect(() => () => clearHoverTimer(), []);

  const className = `side-menu ${open ? "open" : "collapsed"} ${!open && hoverOpen ? "hover-open" : ""}`;

  return (
    <aside
      ref={asideRef}
      className={className}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <button
        className="menu-toggle"
        onClick={toggleOpen}
        aria-label="Toggle menu"
      >
        {open ? "«" : "»"}
      </button>

      {(open || hoverOpen) && showContent && (
        <>
          <FileList refreshToken={refreshToken} />
          <FileUploader
            uploadUrl="http://localhost:8000/upload"
            onUpload={handleUploaded}
          />
        </>
      )}
    </aside>
  );
}
