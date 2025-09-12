import React, { useEffect, useState } from "react";
import "./filelist.scss";
import { useFetch } from "../hooks/fetchWithAuth";

function FileList({ refreshToken = 0 }) {
  const [files, setFiles] = useState([]);
  const { fetchWithAuth } = useFetch();

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


  return (
    <div className="file-list-container">
      <h2 className="file-list-title">Uploaded Files</h2>
      <div className="file-list-scroll">
        {files && files.length > 0 ? (
          <ul>
            {files.map((file, index) => (
              <li key={index} className="file-item">
                <span>{file.filename}</span>
                <a
                  href={`http://localhost:8000/files/${file.filename}`}  // Download link
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => {
                    // Include the token in the download request by modifying the link
                    e.preventDefault();
                    fetch(`http://localhost:8000/files/${file.filename}`, {
                      method: "GET",
                      headers: {
                        "Authorization": `Bearer ${token}`,
                      },
                    })
                      .then((res) => res.blob())
                      .then((blob) => {
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = file.filename;  // Set the filename for download
                        document.body.appendChild(a);
                        a.click();
                        a.remove();
                      })
                      .catch((err) => {
                        console.error("Error downloading file:", err);
                        alert("Error downloading file.");
                      });
                  }}
                >
                  Download
                </a>
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
