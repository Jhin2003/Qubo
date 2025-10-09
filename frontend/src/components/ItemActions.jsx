// Tiny per-item action menu
import React, { useEffect, useRef, useState } from "react";
import { MoreVertical, Trash2, StethoscopeIcon } from "lucide-react";
import "./ItemActions.scss"
function ItemActions({ onUse, onDelete, disabled }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  // close when clicking outside
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
        className="kebab-btn"
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
            className="menu__item"
            onClick={() => { setOpen(false); onUse?.(); }}
            disabled={disabled}
          >
            <StethoscopeIcon size={16} aria-hidden="true" />
            <span>Use</span>
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
