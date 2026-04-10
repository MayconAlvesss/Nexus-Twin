/**
 * App — Root application component
 * ==================================
 * Composes the full NexusTwin dashboard layout:
 *   - Full-screen 3D building scene (background)
 *   - Overlay header with global KPIs
 *   - Slide-in InfoPanel when an element is selected
 *
 * Selection state is lifted here so Header, Scene, and InfoPanel
 * all share the same selected element ID.
 */

import { useState }         from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { BuildingScene }    from "./components/Scene/BuildingScene";
import { Header }           from "./components/Header/Header";
import { InfoPanel }        from "./components/InfoPanel/InfoPanel";
import "./index.css";

// Single React Query client for the whole app — 30s stale time by default
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime:  30_000,
      retry:      1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  return (
    <QueryClientProvider client={queryClient}>
      <div className="app-root">
        {/* Gradient background */}
        <div className="bg-gradient" />

        {/* 3D Scene fills the entire viewport */}
        <div className="scene-container">
          <BuildingScene
            selectedId={selectedId}
            onSelect={(id) => setSelectedId((prev) => (prev === id ? null : id))}
          />
        </div>

        {/* Overlays */}
        <Header />

        {selectedId && (
          <InfoPanel
            elementId={selectedId}
            onClose={() => setSelectedId(null)}
          />
        )}

        {/* Empty-state hint */}
        {!selectedId && (
          <div className="hint">
            Click an element to inspect its structural health
          </div>
        )}
      </div>
    </QueryClientProvider>
  );
}
