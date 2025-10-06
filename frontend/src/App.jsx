import "./App.scss";

import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Container from "./components/Container";
import Chatbot from "./components/Chatbot";
import SideMenu from "./components/SideMenu";
import PdfViewer from "./components/PdfViewer";
import { UserProvider } from "./context/UserContext";
import { SourceProvider } from "./context/SourceContext";

function App() {
  return (
    <UserProvider>
      <SourceProvider>
        <Router>
          <Routes>
            {/* Define route for viewing PDF */}
            <Route path="/view-pdf" element={<PdfViewer />} />

            {/* Default route */}
            <Route
              path="/"
              element={
                <Container>
                  <SideMenu />
                  <Chatbot />
                </Container>
              }
            />
          </Routes>
        </Router>
      </SourceProvider>
    </UserProvider>
  );
}

export default App;
