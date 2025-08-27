import React, { useState } from 'react';
import './fileUploader.scss';  // Ensure you have the corresponding styles

export default function FileUploader({ onUpload }) {
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false); // Track dragging state

  // Handle file input change
  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile && selectedFile.type === 'application/pdf') {
      setFile(selectedFile);
    } else {
      alert('Please upload a valid PDF file.');
    }
  };

  // Handle drag over
  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);  // Set dragging state to true when dragging over
  };

  // Handle drag leave
  const handleDragLeave = () => {
    setIsDragging(false);  // Reset dragging state when leaving the area
  };

  // Handle file drop
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);  // Reset dragging state
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.type === 'application/pdf') {
      setFile(droppedFile);
    } else {
      alert('Please drop a valid PDF file.');
    }
  };

  // Handle file upload
  const handleUpload = async () => {
    if (!file) return;

    setIsUploading(true);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('http://localhost:8000/upload', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        alert('File uploaded successfully!');
      } else {
        alert('Failed to upload file');
      }
    } catch (error) {
      console.error('Error uploading file:', error);
      alert('An error occurred during the upload.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="pdf-uploader">
      <h3>Upload a PDF</h3>

      {/* Drag-and-Drop Zone */}
      <div
        className={`drag-drop-zone ${isDragging ? 'dragging' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        {file ? (
          <div>File selected: {file.name}</div>
        ) : (
          <p>Drag and drop a PDF file here, or click to select</p>
        )}
      </div>

      {/* Hidden file input */}
      <input
        type="file"
        accept="application/pdf"
        onChange={handleFileChange}
        style={{ display: 'none' }}
        id="file-input"
      />

      {/* Upload button triggers file selection and upload */}
      <button
        onClick={() => {
          document.getElementById('file-input').click(); // Trigger file input
        }}
        disabled={isUploading || file === null} // Disable button when uploading or no file
      >
        Select PDF
      </button>

      {/* Upload PDF button to trigger file upload */}
      <button
        onClick={handleUpload} // Call handleUpload when button is clicked
        disabled={isUploading || !file}
      >
        {isUploading ? 'Uploading...' : 'Upload PDF'}
      </button>
    </div>
  );
}
