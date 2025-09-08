import React, { useCallback, useMemo, useRef, useState } from "react";
import "./fileUploader.scss"; // keep using your existing stylesheet

/**
 * Multi-file PDF uploader with drag & drop, list management, and "Send All".
 *
 * Props
 * - uploadUrl?: string (default: "http://localhost:8000/upload")
 * - onUpload?: (result: any) => void  // called after successful upload
 */
export default function FileUploader({ uploadUrl = "http://localhost:8000/upload", onUpload }) {
  const [files, setFiles] = useState([]); // File[]
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);

  const accept = "application/pdf";

  const addFiles = useCallback((fileList) => {
    if (!fileList || fileList.length === 0) return;

    const incoming = Array.from(fileList);

    // Filter only PDFs and dedupe by name + size + lastModified
    const filtered = incoming.filter((f) => {
      const isPdf = f.type === accept || f.name.toLowerCase().endsWith(".pdf");
      if (!isPdf) {
        alert(`❌ Skipped non-PDF: ${f.name}`);
      }
      return isPdf;
    });

    setFiles((prev) => {
      const map = new Map(prev.map((p) => [`${p.name}-${p.size}-${p.lastModified}`, p]));
      for (const f of filtered) {
        const key = `${f.name}-${f.size}-${f.lastModified}`;
        if (!map.has(key)) map.set(key, f);
      }
      return Array.from(map.values());
    });
  }, []);

  // Handlers: file input
  const handleFileChange = (e) => {
    addFiles(e.target.files);
    // reset the input so selecting the same files again re-triggers change
    e.target.value = "";
  };

  // Drag & drop
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

  // Remove one file
  const removeFile = (idx) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  // Clear all
  const clearAll = () => setFiles([]);

  // Upload all in one request as multipart/form-data
  const handleSendAll = async () => {
    if (files.length === 0 || isUploading) return;
    setIsUploading(true);

    const formData = new FormData();
    // backend can read as `files` (array). If your server expects `file[]`, change below
    files.forEach((f) => formData.append("files", f));

    try {
      const res = await fetch(uploadUrl, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error(`Upload failed with status ${res.status}`);

      const data = await safeJson(res);
      alert("✅ Files uploaded successfully!");
      onUpload && onUpload(data);
      clearAll();
    } catch (err) {
      console.error("Error uploading files:", err);
      alert(`⚠️ An error occurred during upload: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const totalSize = useMemo(() => files.reduce((acc, f) => acc + f.size, 0), [files]);

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

  return (
    <div className="pdf-uploader" aria-live="polite">
      <h3>Upload PDFs</h3>

      {/* Drag-and-Drop Zone (clickable) */}
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
        aria-label="Drag and drop PDF files here or click to select"
      >
        {files.length > 0 ? (
          <div className="file-list">
            <ul>
              {files.map((f, i) => (
                <li key={`${f.name}-${f.size}-${f.lastModified}`} className="file-item">
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
              <span>{files.length} file{files.length > 1 ? "s" : ""} selected</span>
              <span>Total: {prettyBytes(totalSize)}</span>
            </div>
          </div>
        ) : (
          <p>Drag and drop PDF files here, or click to select</p>
        )}
      </div>

      {/* Hidden file input */}
      <input
        ref={inputRef}
        id="file-input"
        type="file"
        accept={accept}
        multiple
        onChange={handleFileChange}
        style={{ display: "none" }}
      />

      {/* Controls */}
      <div className="actions">
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={isUploading}
        >
          Select PDFs
        </button>

        <button type="button" onClick={clearAll} disabled={isUploading || files.length === 0}>
          Clear
        </button>

        <button
          type="button"
          onClick={handleSendAll}
          disabled={isUploading || files.length === 0}
        >
          {isUploading ? "Uploading..." : "Send All"}
        </button>
      </div>
    </div>
  );
}

async function safeJson(res) {
  try {
    return await res.json();
  } catch (_) {
    return null;
  }
}
