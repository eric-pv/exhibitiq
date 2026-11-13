import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider } from "antd";
import zhTW from "antd/locale/zh_TW";
import { HashRouter } from "react-router-dom";
import App from "./App";
import { antdTheme } from "./theme/tokens";
import "./theme/print.css";
import favicon from "./assets/brand/exhibitiq-icon-dark.svg";

// Brand icon in the browser tab (an inlined data URI, so it also works in the single-file build).
const icon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
if (icon) { icon.href = favicon; icon.type = "image/svg+xml"; }

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhTW} theme={antdTheme}>
      <HashRouter>
        <App />
      </HashRouter>
    </ConfigProvider>
  </React.StrictMode>,
);
