import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider } from "antd";
import zhTW from "antd/locale/zh_TW";
import { HashRouter } from "react-router-dom";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhTW}>
      <HashRouter>
        <App />
      </HashRouter>
    </ConfigProvider>
  </React.StrictMode>,
);
