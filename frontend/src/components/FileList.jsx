import React, { useEffect, useState } from "react";
import "./filelist.scss";

function FileList({ refreshToken = 0 }) {
  const [files, setFiles] = useState([]);

  const fetchFiles = () => {
    fetch("http://localhost:8000/files") // adjust port if needed
      .then((res) => res.json())
      .then((data) => setFiles(data.files))
      .catch((err) => console.error(err));
  };

  useEffect(() => {
    fetchFiles();
  }, [refreshToken]); // ⬅ refetch whenever parent changes refreshToken

  return (
    <div className="file-list-container">
      <h2 className="file-list-title">Uploaded Files</h2>
      <div className="file-list-scroll">
        {files.length > 0 ? (
          <ul>
            {files.map((file, index) => (
              <li key={index} className="file-item">
                <span>{file.filename}</span>
                <a
                  href={`http://localhost:8000/download/${file.filename}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
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
