/**
 * main.tsx — React entry point
 * Mounts the App into the #root div with StrictMode enabled.
 */
import { StrictMode } from "react";
import { createRoot }  from "react-dom/client";
import "./index.css";
import App             from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
