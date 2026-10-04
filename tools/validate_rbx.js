// Valida um .rbxmx com o rbx-dom (reflexão oficial da API do Roblox) e grava o .rbxm binário.
// Uso: node tools/validate_rbx.js arquivo.rbxmx [--binary]
const fs = require("fs");
const { Dom, Attributes } = require("rbx-dom");
const file = process.argv[2];
const dom = Dom.fromXml(fs.readFileSync(file), { propertyBehavior: "errorOnUnknown" });
const counts = {};
let attrs = null;
for (const inst of dom.descendants()) {
  counts[inst.className] = (counts[inst.className] || 0) + 1;
  const a = inst.properties.Attributes;
  if (a && inst.className === "Model") attrs = a;
}
console.log(JSON.stringify(counts));
if (attrs) console.log("attributes:", JSON.stringify(attrs).slice(0, 300));
if (process.argv.includes("--binary")) {
  const out = file.replace(/\.rbxmx$/, ".rbxm");
  fs.writeFileSync(out, dom.toBinary());
  const back = Dom.fromBinary(fs.readFileSync(out));
  console.log("rbxm ok:", out, back.instanceCount, "instances");
}
