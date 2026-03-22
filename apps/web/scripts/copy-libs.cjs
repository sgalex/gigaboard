/**
 * Копирует vendor-библиотеки из node_modules в public/libs/ для виджетов (iframe /libs/...).
 * См. docs/WIDGET_GENERATION_SYSTEM.md — локальные копии вместо CDN.
 */
const fs = require("fs");
const path = require("path");

const repoRoot = path.join(__dirname, "..", "..", "..");
const nm = path.join(repoRoot, "node_modules");
const pub = path.join(__dirname, "..", "public", "libs");

fs.mkdirSync(path.join(pub, "fonts"), { recursive: true });
fs.mkdirSync(path.join(pub, "images"), { recursive: true });

fs.cpSync(path.join(nm, "echarts", "dist", "echarts.min.js"), path.join(pub, "echarts.min.js"));

fs.cpSync(path.join(nm, "leaflet", "dist", "leaflet.css"), path.join(pub, "leaflet.css"));
fs.cpSync(path.join(nm, "leaflet", "dist", "leaflet.js"), path.join(pub, "leaflet.js"));
fs.cpSync(path.join(nm, "leaflet", "dist", "images"), path.join(pub, "images"), { recursive: true });

const interFiles = [
  "inter-latin-wght-normal",
  "inter-latin-ext-wght-normal",
  "inter-cyrillic-wght-normal",
  "inter-cyrillic-ext-wght-normal",
];
for (const f of interFiles) {
  fs.cpSync(
    path.join(nm, "@fontsource-variable", "inter", "files", `${f}.woff2`),
    path.join(pub, "fonts", `${f}.woff2`),
  );
}
