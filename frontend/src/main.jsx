import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./styles.css";
import Upload from "./pages/Upload.jsx";
import JobProgress from "./pages/JobProgress.jsx";
import TKPReview from "./pages/TKPReview.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Upload />} />
        <Route path="/jobs/:jobId" element={<JobProgress />} />
        <Route path="/tkp/:tkpId" element={<TKPReview />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
