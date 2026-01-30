import React, { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import "./filelist.scss";
import { useFetch } from "../hooks/fetchWithAuth";
import { useSource } from "../context/SourceContext";
import ItemActions from "./ItemActions";
// 1. IMPORT NEW ICONS HERE
import { FaTrashAlt, FaFilePdf, FaFileWord, FaFileAlt } from "react-icons/fa";
import { CiFileOn, CiSquareCheck } from "react-icons/ci";
import { FiPlus } from "react-icons/fi"; // Added FiPlus import
import { MdClose } from "react-icons/md";

import FileUploaderDialog from "./FileUploaderDialog"; 

function FileList({ refreshToken = 0, onLoadingChange }) {
  const [files, setFiles] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [actionLoading, setActionLoading] = useState({});
  const { fetchWithAuth } = useFetch();
  const [isLoading, setIsLoading] = useState(true);

  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [openDialog, setOpenDialog] = useState(false);

  const navigate = useNavigate();
  const { source, setSource } = useSource();
  const fileInputRef = useRef(null);

  const fetchFiles = async () => {
    try {
      const response = await fetchWithAuth("http://localhost:8000/files", {
        method: "GET",
      });
      if (!response) return;
      const data = await response.json();
      setFiles(data.files || []);
    } catch (error) {
      console.error("Error fetching files:", error);
      alert("Failed to fetch files.");
    } finally {
      setIsLoading(false);
      onLoadingChange(false);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, [refreshToken]);

  // --- FIX: Define the missing handleUploaded function ---
  const handleUploaded = () => {
    // Refresh the list after a successful upload
    fetchFiles();
  };

  const toggleSelectionMode = () => {
    if (isSelectionMode) {
      setSelectedFiles([]);
      setIsSelectionMode(false);
    } else {
      setIsSelectionMode(true);
    }
  };

  const handleSelectAll = (e) => {
    if (e.target.checked) {
      setSelectedFiles(files.map((f) => f.filename));
    } else {
      setSelectedFiles([]);
    }
  };

  const handleToggleFile = (filename) => {
    setSelectedFiles((prev) =>
      prev.includes(filename)
        ? prev.filter((name) => name !== filename)
        : [...prev, filename],
    );
  };

  const handleBulkDelete = async () => {
    if (!window.confirm(`Delete ${selectedFiles.length} selected files?`))
      return;
    const loadingState = {};
    selectedFiles.forEach((name) => (loadingState[name] = true));
    setActionLoading((prev) => ({ ...prev, ...loadingState }));

    try {
      const deletePromises = selectedFiles.map((filename) =>
        fetchWithAuth(
          `http://localhost:8000/files/${encodeURIComponent(filename)}`,
          { method: "DELETE" },
        ),
      );
      await Promise.all(deletePromises);
      setFiles((prev) =>
        prev.filter((f) => !selectedFiles.includes(f.filename)),
      );
      setSelectedFiles([]);
      setIsSelectionMode(false);
      alert("Selected files deleted successfully.");
    } catch (e) {
      console.error(e);
      alert("An error occurred during bulk deletion.");
    } finally {
      setActionLoading({});
    }
  };

  const handleDelete = async (file) => {
    if (!window.confirm(`Delete "${file.filename}"?`)) return;
    setActionLoading((s) => ({ ...s, [file.filename]: true }));
    try {
      const res = await fetchWithAuth(
        `http://localhost:8000/files/${encodeURIComponent(file.filename)}`,
        { method: "DELETE" },
      );
      if (!res || !res.ok) throw new Error("Delete failed.");
      setFiles((prev) => prev.filter((f) => f.filename !== file.filename));
      setSelectedFiles((prev) => prev.filter((name) => name !== file.filename));
    } catch (e) {
      console.error(e);
      alert(`Failed to delete "${file.filename}".`);
    } finally {
      setActionLoading((s) => ({ ...s, [file.filename]: false }));
    }
  };

  const handleSourceClick = (fileName, page) => {
    navigate(`/view-pdf?file=${encodeURIComponent(fileName)}&page=${page}`);
  };

  const handleFileChange = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    console.log("File selected:", file.name);
    // You might want to trigger upload dialog or logic here depending on your flow
  };

  const getFileIcon = (filename) => {
    const lowerName = filename.toLowerCase();
    if (lowerName.endsWith(".pdf")) {
      return (
        <FaFilePdf
          className="file-type-icon pdf-icon"
          style={{ color: "#e15b64", marginRight: "8px" }}
        />
      );
    } else if (lowerName.endsWith(".doc") || lowerName.endsWith(".docx")) {
      return (
        <FaFileWord
          className="file-type-icon word-icon"
          style={{ color: "#4b8add", marginRight: "8px" }}
        />
      );
    } else {
      return (
        <FaFileAlt
          className="file-type-icon default-icon"
          style={{ color: "#888", marginRight: "8px" }}
        />
      );
    }
  };

  return (
    // --- FIX: Added React Fragment (<> ... </>) to wrap multiple children ---
    <>
      <div className="file-list-container">
        <div className="file-list-header">
          <div className="brand">
            <CiFileOn className="file-icon-logo" />
            <p className="file-list-title">Files</p>
          </div>

          <div className="file-list-controls">
            {!isSelectionMode ? (
              <button className="mode-toggle-btn" onClick={toggleSelectionMode}>
                <CiSquareCheck className="icon" />
                <span>Select</span>
              </button>
            ) : (
              <>
                <label className="select-all-container">
                  <input
                    type="checkbox"
                    className="checkbox-input"
                    onChange={handleSelectAll}
                    checked={
                      files.length > 0 && selectedFiles.length === files.length
                    }
                  />
                  <span>All</span>
                </label>

                <button
                  className="delete-button"
                  onClick={handleBulkDelete}
                  disabled={selectedFiles.length === 0}
                >
                  <FaTrashAlt />
                  {selectedFiles.length > 0 && (
                    <span>({selectedFiles.length})</span>
                  )}
                </button>

                <button
                  className="cancel-mode-btn"
                  onClick={toggleSelectionMode}
                  title="Cancel"
                >
                  <MdClose />
                </button>
              </>
            )}
          </div>
        </div>

        <div className="file-list-scroll">
          {isLoading ? (
            <p>Loading files...</p>
          ) : (
            <ul className="file-list">
              {files.map((file, index) => {
                const isActive = source === file.filename;
                const isSelected = selectedFiles.includes(file.filename);

                return (
                  <li
                    key={index}
                    className={`file-item ${isActive ? "file-item--active" : ""}`}
                  >
                    <div className="file-item-left">
                      {isSelectionMode && (
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleToggleFile(file.filename)}
                          className="item-checkbox"
                        />
                      )}

                      {getFileIcon(file.filename)}

                      {!isLoading && (
                        <button
                          className="file-link"
                          onClick={() => handleSourceClick(file.filename, 1)}
                          title="Open"
                        >
                          {file.filename}
                        </button>
                      )}
                    </div>

                    {!isSelectionMode && (
                      <div className="actions-wrapper">
                        <ItemActions
                          disabled={!!actionLoading[file.filename]}
                          isActive={isActive}
                          onUse={() => setSource(isActive ? null : file.filename)}
                          onDelete={() => handleDelete(file)}
                        />
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            style={{ display: "none" }}
            accept=".pdf,.doc,.docx"
          />
        </div>

        <button className="upload-pdf-button" onClick={() => setOpenDialog(true)}>
          <span className="btn-icon">
            <FiPlus size={18} strokeWidth={3} />
          </span>
          <span>Upload Files</span>
        </button>
      </div>

      <FileUploaderDialog
        open={openDialog}
        onClose={() => setOpenDialog(false)}
        uploadUrl="http://localhost:8000/upload"
        onUpload={(data) => {
          console.log("Uploaded:", data);
          handleUploaded();
        }}
      />
    </>
  );
}

export default FileList;