import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./filelist.scss";
import { useFetch } from "../hooks/fetchWithAuth";
import {  StethoscopeIcon, Trash2 } from "lucide-react"; // <-- library icons

import { useSource } from "../context/SourceContext";
import ItemActions from "./ItemActions";


function FileList({ refreshToken = 0 }) {
  const [files, setFiles] = useState([]);
  const [actionLoading, setActionLoading] = useState({});
  const { fetchWithAuth } = useFetch();
  const navigate = useNavigate();
    const { setSource } = useSource();

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
    }
  };

  useEffect(() => {
    fetchFiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshToken]);

  const handleSourceClick = (fileName, page) => {
    navigate(`/view-pdf?file=${encodeURIComponent(fileName)}&page=${page}`);
  };

  const handleDelete = async (file) => {
    if (!window.confirm(`Delete "${file.filename}"?`)) return;
    setActionLoading((s) => ({ ...s, [file.filename]: true }));
    try {
      const res = await fetchWithAuth(
        `http://localhost:8000/files/${encodeURIComponent(file.filename)}`,
        { method: "DELETE" }
      );
      if (!res || !res.ok) {
        const msg = res ? ` ${res.status} ${res.statusText}` : "";
        throw new Error("Delete failed." + msg);
      }
      setFiles((prev) => prev.filter((f) => f.filename !== file.filename));
    } catch (e) {
      console.error(e);
      alert(`Failed to delete "${file.filename}".`);
    } finally {
      setActionLoading((s) => ({ ...s, [file.filename]: false }));
    }
  };

  return (
    <div className="file-list-container">
      <div className="file-list-header">
        <div className="brand">
          
          <h2 className="file-list-title">Uploaded Files</h2>
        </div>
      </div>

      <div className="file-list-scroll">
        {files && files.length > 0 ? (
          <ul className="file-list">
            {files.map((file, index) => {
              const loading = !!actionLoading[file.filename];
              return (
                <li key={index} className="file-item">
                  <button
                    className="file-link"
                    onClick={() => handleSourceClick(file.filename, 1)}
                    title="Open"
                  >
                    {file.filename}
                  </button>

                  <ItemActions
    disabled={!!actionLoading[file.filename]}
    onUse={() => setSource(file.filename)}
    onDelete={() => handleDelete(file)}
  />
                </li>
              );
            })}
          </ul>
        ) : (
          <p>No files uploaded yet.</p>
        )}
      </div>
    </div>
  );
}

export default FileList;