// Reads a JSON array of {tex, display} from stdin and prints a JSON array of error strings (null = renders) using the
// same KaTeX the web app ships. Usage: node check_katex.mjs <path to apps/web/package.json>
import { createRequire } from "node:module";

const katex = createRequire(process.argv[2])("katex");
let raw = "";
process.stdin.setEncoding("utf8");
for await (const chunk of process.stdin) raw += chunk;
const out = JSON.parse(raw).map(({ tex, display }) => {
  try {
    katex.renderToString(tex, { throwOnError: true, strict: "ignore", trust: false, displayMode: !!display });
    return null;
  } catch (e) {
    return String(e.message).slice(0, 200);
  }
});
process.stdout.write(JSON.stringify(out));
