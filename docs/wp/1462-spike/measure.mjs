// Bundle each candidate's likely imports with esbuild --minify, report min and gzip -9 bytes.
import { build } from "esbuild";
import { gzipSync } from "node:zlib";
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const entries = {
  three_wp: `import { WebGLRenderer, Scene, OrthographicCamera, PerspectiveCamera, InstancedMesh, BufferGeometry, BufferAttribute, MeshLambertMaterial, LineSegments, LineBasicMaterial, AmbientLight, DirectionalLight, Raycaster, Vector2, Matrix4, Color } from "three";
import { TrackballControls } from "three/examples/jsm/controls/TrackballControls.js";
window.x = [WebGLRenderer, Scene, OrthographicCamera, PerspectiveCamera, InstancedMesh, BufferGeometry, BufferAttribute, MeshLambertMaterial, LineSegments, LineBasicMaterial, AmbientLight, DirectionalLight, Raycaster, Vector2, Matrix4, Color, TrackballControls];`,
  three_shader: `import { WebGLRenderer, Scene, OrthographicCamera, InstancedBufferGeometry, InstancedBufferAttribute, BufferAttribute, RawShaderMaterial, Mesh, Matrix4, Vector3, Color } from "three";
import { TrackballControls } from "three/examples/jsm/controls/TrackballControls.js";
window.x = [WebGLRenderer, Scene, OrthographicCamera, InstancedBufferGeometry, InstancedBufferAttribute, BufferAttribute, RawShaderMaterial, Mesh, Matrix4, Vector3, Color, TrackballControls];`,
  three_webgpu: `import { WebGPURenderer, Scene, OrthographicCamera, InstancedMesh, MeshLambertNodeMaterial, BufferGeometry } from "three/webgpu";
window.x = [WebGPURenderer, Scene, OrthographicCamera, InstancedMesh, MeshLambertNodeMaterial, BufferGeometry];`,
  ogl: `import { Renderer, Camera, Transform, Program, Mesh, Geometry, Orbit, Raycast, Sphere, Cylinder, Vec2, Mat4, Color } from "ogl";
window.x = [Renderer, Camera, Transform, Program, Mesh, Geometry, Orbit, Raycast, Sphere, Cylinder, Vec2, Mat4, Color];`,
  twgl: `import { createProgramInfo, createBufferInfoFromArrays, createVertexArrayInfo, setBuffersAndAttributes, setUniforms, drawBufferInfo, resizeCanvasToDisplaySize, m4, v3 } from "twgl.js";
window.x = [createProgramInfo, createBufferInfoFromArrays, createVertexArrayInfo, setBuffersAndAttributes, setUniforms, drawBufferInfo, resizeCanvasToDisplaySize, m4, v3];`,
  regl: `import createREGL from "regl"; window.x = createREGL;`,
  picogl: `import PicoGL from "picogl"; window.x = PicoGL;`,
  ngl: `import * as NGL from "ngl"; window.x = NGL;`,
  "3dmol": `import * as $3Dmol from "3dmol"; window.x = $3Dmol;`,
  uplot_ref: `import uPlot from "uplot"; window.x = uPlot;`,
  prototype: `import { createViewer } from "./viewer.js"; window.x = createViewer;`,
};

const only = process.argv.slice(2);
mkdirSync(join(here, "out"), { recursive: true });
for (const [name, src] of Object.entries(entries)) {
  if (only.length && !only.includes(name)) continue;
  try {
    const r = await build({
      stdin: { contents: src, resolveDir: here, loader: "js" },
      bundle: true, minify: true, format: "esm", write: false, logLevel: "silent",
      define: { "process.env.NODE_ENV": '"production"' },
    });
    const code = r.outputFiles[0].contents;
    writeFileSync(join(here, "out", name + ".js"), code);
    const gz = gzipSync(code, { level: 9 }).length;
    console.log(`${name.padEnd(14)} min ${String(code.length).padStart(9)}  gz ${String(gz).padStart(8)}`);
  } catch (e) {
    console.log(`${name.padEnd(14)} FAILED ${String(e.message).split("\n")[0]}`);
  }
}
