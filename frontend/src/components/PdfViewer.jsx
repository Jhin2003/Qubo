import React from "react";
import { useLocation } from "react-router-dom";

const PdfViewer = () => {
  const { search } = useLocation();
  const queryParams = new URLSearchParams(search);
  const fileName = queryParams.get("file");
  const page = queryParams.get("page") || 1;

  const pdfUrl = `http://localhost:8000/files/${fileName}#page=${page}`;

  return (
    <div>
      <h3>Viewing PDF: {fileName}</h3>

      {/* Embed PDF using <object> */}
      <object
        data={pdfUrl}
        type="application/pdf"
        width="100%"
        height="800px"
      >
        <p>Your browser does not support PDFs. <a href={pdfUrl}>Download the PDF</a>.</p>
      </object>
      
      {/* Alternatively, you can use <iframe> */}
      {/* <iframe src={pdfUrl} width="100%" height="800px" /> */}
    </div>
  );
};

export default PdfViewer;
