import { Component, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.jsx";

// Catches unexpected render errors so users never see a blank white page.
class ErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    // Hook your monitoring here (Sentry, LogRocket, etc.)
    console.error("Unhandled UI error:", error, info);
  }

  render() {
    if (!this.state.failed) return this.props.children;

    return (
      <div className="dp-crash">
        <h1>Something went wrong</h1>
        <p>DataPilot AI hit an unexpected problem. Reload the page to continue.</p>
        <button type="button" onClick={() => window.location.reload()}>
          Reload page
        </button>
      </div>
    );
  }
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>
);