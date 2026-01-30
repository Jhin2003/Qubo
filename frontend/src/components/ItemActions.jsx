// Tiny per-item action menu
import React, { useEffect, useRef, useState } from "react";
import { MoreVertical, Trash2 } from "lucide-react";
import { RiFocus3Line, RiFocus3Fill } from "react-icons/ri"; // Import a 'Fill' version for active state
import "./ItemActions.scss";

function ItemActions({ onUse, onDelete, disabled, isActive }) { // <--- Added isActive prop
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onDocClick = (e) => {
      if (open && ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onEsc = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  return (
    <div className="item-actions" ref={ref}>
      <button
        className={`kebab-btn ${open ? "active" : ""}`}
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        title="Actions"
      >
        <MoreVertical size={18} />
      </button>

      {open && (
        <div className="menu" role="menu">
          <button
            role="menuitem"
            className={`menu__item ${isActive ? "is-active" : ""}`} // Add a class for styling if active
            onClick={() => { setOpen(false); onUse?.(); }}
            disabled={disabled}
          >
            {/* Toggle Icon and Text based on isActive */}
            {isActive ? (
              <>
                <RiFocus3Fill size={16} aria-hidden="true" style={{ color: "#5BB5AE" }} />
                <span>Unuse</span>
              </>
            ) : (
              <>
                <RiFocus3Line size={16} aria-hidden="true" />
                <span>Use</span>
              </>
            )}
          </button>
          
          <button
            role="menuitem"
            className="menu__item menu__item--danger"
            onClick={() => { setOpen(false); onDelete?.(); }}
            disabled={disabled}
          >
            <Trash2 size={16} aria-hidden="true" />
            <span>Delete</span>
          </button>
        </div>
      )}
    </div>
  );
}

export default ItemActions;