import { useEffect, useRef, useState } from "react";
import FileUploaderDialog from "./FileUploaderDialog"; // <- ensure correct path/file name
import "./SideMenu.scss";
import FileList from "./FileList";

export default function SideMenu() {
  const [open, setOpen] = useState(false);
  const [openDialog, setOpenDialog] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);
  const [hoverOpen, setHoverOpen] = useState(false); // Used to trigger hover expansion
  const [showContent, setShowContent] = useState(false); // Control when content is displayed

  const asideRef = useRef(null);
  const hoverTimerRef = useRef(null);

  const handleUploaded = () => setRefreshToken((t) => t + 1);

  // Handle mouse enter event to trigger hover expansion
  const onMouseEnter = (e) => {
    if (open) return;  // Don't trigger hover if already open
    if (e.target.closest(".menu-toggle")) return;  // Skip the button hover
    clearHoverTimer();
    hoverTimerRef.current = setTimeout(() => setHoverOpen(true), 200); // Expand after 200ms delay
  };

  // Handle mouse leave event to collapse sidebar
  const onMouseLeave = () => {
    clearHoverTimer();
    setHoverOpen(false);  // Collapse sidebar immediately when mouse leaves
  };

  // Clear the hover timer on cleanup
  const clearHoverTimer = () => {
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
  };

  // When the width transition ends, show content
  useEffect(() => {
    const el = asideRef.current;
    if (!el) return;

    const onTransitionEnd = (e) => {
      if (e.propertyName === "width") {
        if (open || hoverOpen) {
          setShowContent(true); // Show content after transition ends
        } else {
          setShowContent(false); // Hide content when collapsing
        }
      }
    };

    el.addEventListener("transitionend", onTransitionEnd);
    return () => el.removeEventListener("transitionend", onTransitionEnd);
  }, [open, hoverOpen]);

  // CSS class for sidebar based on open/hover states
  const className = `side-menu ${open ? "open" : "collapsed"} ${!open && hoverOpen ? "hover-open" : ""}`;

  return (
    <aside
      ref={asideRef}
      className={className}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <button className="menu-toggle" onClick={() => setOpen((v) => !v)} aria-label="Toggle menu">
        <img src="/logos/menu-burger.svg" alt="menu" />
      </button>

      {/* Only render content once the hover expansion is completed */}
      {(open || hoverOpen) && showContent && (
        <>
          <FileList refreshToken={refreshToken} />
          <button onClick={() => setOpenDialog(true)}>Upload PDFs</button>
        </>
      )}

      {/* The dialog will render in a portal above everything */}
      <FileUploaderDialog
        open={openDialog}
        onClose={() => setOpenDialog(false)}  
        uploadUrl="http://localhost:8000/upload"
        onUpload={(data) => {
          console.log("Uploaded:", data);
          handleUploaded();
        }}
      />
    </aside>
  );
}
