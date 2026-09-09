/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_EAM_URL?: string;
  readonly VITE_HTTP_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
