import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import i18n from "./i18n"; // 副作用：触发 i18next init
import "./styles/tokens.css";
import "./styles/global.css";
import "./styles/preview-replica.css";

const params = new URLSearchParams(window.location.search);
const windowKind = params.get("window");
const isCapsule = windowKind === "capsule";
const isQa = windowKind === "qa";

const root = ReactDOM.createRoot(document.getElementById("root")!);

const renderApp = () => {
  root.render(
    <React.StrictMode>
      <App isCapsule={isCapsule} isQa={isQa} />
    </React.StrictMode>,
  );
};

// i18n 必须就绪后才能渲染：否则首次渲染拿到的 t() 返回 key 字面量。
// react-i18next useSuspense=false 时不会自动等，只有事件触发后重渲染才能拿到译文。
if (i18n.isInitialized) {
  renderApp();
} else {
  i18n.on("initialized", renderApp);
}
