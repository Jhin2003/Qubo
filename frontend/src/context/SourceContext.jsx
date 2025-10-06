// src/context/SourceContext.jsx
import { createContext, useContext, useMemo, useState } from "react";

const SourceCtx = createContext(null);

export function SourceProvider({ children }) {
  const [source, setSource] = useState(null); // filename or full path
  const value = useMemo(
    () => ({ source, setSource, clearSource: () => setSource(null) }),
    [source]
  );
  return <SourceCtx.Provider value={value}>{children}</SourceCtx.Provider>;
}

export function useSource() {
  const ctx = useContext(SourceCtx);
  if (!ctx) throw new Error("useSource must be used within <SourceProvider>");
  return ctx;
}
