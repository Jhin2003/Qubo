import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./filelist.scss";
import { useFetch } from "../hooks/fetchWithAuth";

function FileList({ refreshToken = 0 }) {
  const [files, setFiles] = useState([]);
  const { fetchWithAuth } = useFetch();
  const navigate = useNavigate();

  const fetchFiles = async () => {
    try {
      const response = await fetchWithAuth("http://localhost:8000/files", {
        method: "GET",
      });

      if (!response) return;

      const data = await response.json();
      setFiles(data.files);
    } catch (error) {
      console.error("Error fetching files:", error);
      alert("Failed to fetch files.");
    }
  };

  useEffect(() => {
    fetchFiles();
  }, [refreshToken]);

  const handleSourceClick = (fileName, page) => {
    navigate(`/view-pdf?file=${encodeURIComponent(fileName)}&page=${page}`);
  };

  return (
    <div className="file-list-container">
      <h2 className="file-list-title">Uploaded Files</h2>
      <div className="file-list-scroll">
        {files && files.length > 0 ? (
          <ul>
            {files.map((file, index) => (
              <li key={index} className="file-item">
                <span
                  className="file-link"
                  onClick={() => handleSourceClick(file.filename, 1)} // pass a function
                >
                  {file.filename}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p>No files uploaded yet.</p>
        )}
      </div>
    </div>
  );
}

export default FileList;
