import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider } from "antd";
import zhTW from "antd/locale/zh_TW";
import { HashRouter } from "react-router-dom";
import App from "./App";
import { antdTheme } from "./theme/tokens";
import "./theme/print.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhTW} theme={antdTheme}>
      <HashRouter>
        <App />
      </HashRouter>
    </ConfigProvider>
  </React.StrictMode>,
);
