import { isValidLaunchToken } from "./api-client";

interface BIDRRuntimeConfiguration {
  apiToken?: string;
}

declare global {
  interface Window {
    __BIDR_RUNTIME__?: BIDRRuntimeConfiguration;
  }
}

export function readLaunchToken(): string {
  const token = window.__BIDR_RUNTIME__?.apiToken;
  return typeof token === "string" && isValidLaunchToken(token) ? token : "";
}

export {};
