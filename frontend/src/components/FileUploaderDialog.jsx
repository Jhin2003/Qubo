import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

import toast from "react-hot-toast";
import "./FileUploaderDialog.scss";

// src/config.js
export const API_URL = import.meta.env.VITE_API_URL;

export default function FileUploaderDialog({
  open,
  onClose,
  uploadUrl = `${API_URL}/upload`,
  onUpload,
}) {
  const [files, setFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);
  const dialogRef = useRef(null);

  // This is already correctly configured for all file types
  const accept = ["application/pdf", ".pdf"].join(",");

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && onClose?.();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (open) dialogRef.current?.focus();
  }, [open]);

  // --- CHANGE: Update validation logic to accept all specified types ---
  const addFiles = useCallback((fileList) => {
    if (!fileList || fileList.length === 0) return;
    const incoming = Array.from(fileList);
    const allowedExtensions = [".pdf", ".docx", ".txt"];

    const filtered = incoming.filter((f) => {
      const fileNameLower = f.name.toLowerCase();
      // Check if the file name ends with any of the allowed extensions
      const isValid = allowedExtensions.some((ext) =>
        fileNameLower.endsWith(ext),
      );
      if (!isValid) {
        alert(`❌ Skipped unsupported file type: ${f.name}`);
      }
      return isValid;
    });

    setFiles((prev) => {
      const map = new Map(
        prev.map((p) => [`${p.name}-${p.size}-${p.lastModified}`, p]),
      );
      for (const f of filtered) {
        const key = `${f.name}-${f.size}-${f.lastModified}`;
        if (!map.has(key)) map.set(key, f);
      }
      return Array.from(map.values());
    });
  }, []); // The 'accept' dependency is removed as it's constant

  const handleFileChange = (e) => {
    addFiles(e.target.files);
    e.target.value = "";
  };
  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };
  const handleDragLeave = () => setIsDragging(false);
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    addFiles(e.dataTransfer.files);
  };

  const removeFile = (idx) =>
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  const clearAll = () => setFiles([]);

  const handleSendAll = async () => {
    const toastId = toast.loading("Uploading files...");
    if (files.length === 0 || isUploading) return;
    setIsUploading(true);
    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));
    const token = localStorage.getItem("auth_token");

    try {
      const res = await fetch("http://localhost:8000/upload", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });
      if (!res.ok) throw new Error(`Upload failed with status ${res.status}`);
      const data = await safeJson(res);

      const results = data.results;
      console.log(results)

      if (Array.isArray(results)) {
        results.forEach((file) => {
          if (file.status === "error") {
            toast.error(`${file.filename}: ${file.error}`, { id: toastId });
          } else {
            toast.success(`Uploaded: ${file.filename}`, { id: toastId });
          }
        });
      } else {
        console.error("Unexpected response format:", data);
      }

      onUpload && onUpload(data);
      clearAll();
      onClose && onClose();
    } catch (err) {
      console.error("Error uploading files:", err);

      toast.error("Upload failed. Please try again.", { id: toastId });
    } finally {
      setIsUploading(false);
      toast.success(
        `Uploaded ${files.length} ${files.length > 1 ? "files" : "file"} successfully`,
        { id: toastId },
      );
    }
  };

  const totalSize = useMemo(
    () => files.reduce((acc, f) => acc + f.size, 0),
    [files],
  );

  const prettyBytes = (num) => {
    if (!Number.isFinite(num)) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let i = 0;
    while (num >= 1024 && i < units.length - 1) {
      num /= 1024;
      i++;
    }
    return `${num.toFixed(num < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
  };

  if (!open) return null;

  // --- CHANGE: Update UI text to be more generic ---
  const dialog = (
    <div
      className="uploader-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose?.();
      }}
    >
      <div
        className="uploader-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="uploader-title"
        ref={dialogRef}
        tabIndex={-1}
      >
        <div className="uploader-header">
          <h3 id="uploader-title">Upload Files</h3>
          <button
            type="button"
            className="uploader-close"
            aria-label="Close"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <div className="uploader-body">
          <div
            role="button"
            tabIndex={0}
            className={`drag-drop-zone ${isDragging ? "dragging" : ""}`}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
            }}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            aria-label="Drag and drop files here or click to select"
          >
            {files.length > 0 ? (
              <div className="file-list">
                <ul>
                  {files.map((f, i) => (
                    <li
                      key={`${f.name}-${f.size}-${f.lastModified}`}
                      className="file-item"
                    >
                      <div className="file-meta">
                        <span className="file-name">{f.name}</span>
                        <span className="file-size">{prettyBytes(f.size)}</span>
                      </div>
                      <button
                        type="button"
                        className="remove-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          removeFile(i);
                        }}
                        aria-label={`Remove ${f.name}`}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
                <div className="summary-row">
                  <span>
                    {files.length} file{files.length > 1 ? "s" : ""} selected
                  </span>
                  <span>Total: {prettyBytes(totalSize)}</span>
                </div>
              </div>
            ) : (
              <p>Drag and drop files here, or click to select</p>
            )}
          </div>

          <input
            ref={inputRef}
            type="file"
            accept={accept}
            multiple
            onChange={handleFileChange}
            style={{ display: "none" }}
          />
        </div>

        <div className="uploader-footer">
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={isUploading}
          >
            Select Files
          </button>
          <button
            type="button"
            onClick={clearAll}
            disabled={isUploading || files.length === 0}
          >
            Clear
          </button>
          <button
            type="button"
            onClick={handleSendAll}
            disabled={isUploading || files.length === 0}
          >
            {isUploading
              ? "Uploading..."
              : files.length === 1
                ? "Send"
                : "Send All"}
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(dialog, document.body);
}

async function safeJson(res) {
  try {
    return await res.json();
  } catch {
    return null;
  }
}
