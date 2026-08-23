import { useCallback, useState } from "react";

const STORAGE_KEY = "pr-warden-api-key";

export function useApiKey(): [string, (key: string) => void] {
  const [apiKey, setApiKeyState] = useState<string>(
    () => localStorage.getItem(STORAGE_KEY) ?? "",
  );

  const setApiKey = useCallback((key: string) => {
    setApiKeyState(key);
    if (key) {
      localStorage.setItem(STORAGE_KEY, key);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  return [apiKey, setApiKey];
}
