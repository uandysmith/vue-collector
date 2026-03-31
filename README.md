# vue-collector

A pure-Python tool for compiling [Vue single-file components](https://vuejs.org/guide/scaling-up/sfc.html) (`.vue` files) into browser-ready assets — **no Node.js, no npm, no build toolchain required**.

## Purpose

vue-collector is a **stepping stone before Vite**. It lets you write Vue components using standard `.vue` files and compile them from Python, without setting up a JavaScript build pipeline. When your project outgrows vue-collector, moving to Vite requires **no rewriting** — the same `.vue` files work in both environments.

**What it is:**
- A quick way to add Vue components to a Python backend (Flask, FastAPI, Django, etc.)
- Suitable for internal tools, dashboards, and prototypes where plain JS is enough
- Write real `.vue` files from day one, migrate to Vite later with zero friction

**What it is not:**
- A replacement for Vite, Webpack, or Rollup
- Production-ready: no tree-shaking, no code splitting, no hot-reload, no module resolution

**When to use it:**
- You want a few interactive Vue pieces in a Python app without touching npm
- Simplicity and zero JS tooling beats optimal bundle size for your current stage
- You expect to migrate to a proper Vite project as the frontend grows

---

## Vite migration path

vue-collector is designed so that every `.vue` file you write is a valid Vite component:

- **Options API** `export default { ... }` is fully supported in Vue 3 / Vite
- **`import` statements** are silently stripped by vue-collector — you can add them in advance for Vite compatibility, and vue-collector will ignore them
- **`components: { ... }`** (local component registration) is silently stripped — same principle
- **`name` property** is silently stripped — vue-collector auto-generates component names from filenames
- **`<style lang="less">`** is required — this ensures Vite knows to use the LESS preprocessor (install `less` as a dev dependency in your Vite project)

When you're ready to switch to Vite:
1. Set up a Vite project (`npm create vite@latest`)
2. Copy your `.vue` files — they work as-is
3. The `import` statements and `components` registrations you added for forward-compatibility are now active
4. Run `npm install less --save-dev` if your styles use LESS

---

## Component format

Components use a simplified subset of the Vue SFC format:

- **`export default { ... }`** is the only supported component definition — no `defineComponent()`, no `<script setup>`
- **`<style lang="less">`** is required when using styles — ensures Vite compatibility. `<style scoped lang="less">` for scoped styles
- **No `@import`** in `<style>` — inline styles only
- **One** `<template>`, `<script>`, and `<style>` section per file
- **No TypeScript** — `<script lang="ts">` raises an error; plain JavaScript only
- Vue directives (`v-for`, `v-if`, `@click`, `:bind`) pass through unchanged
- Named slots via nested `<template #slot>` are supported
- Multiple root elements (Vue 3 fragments) are supported

**Silently stripped** (allowed for Vite compatibility, ignored by vue-collector):
- `import` statements in `<script>`
- `components: { ... }` in `export default`
- `name` property in `export default`

```vue
<!-- components/Counter.vue -->
<template>
  <div class="counter">
    <span>{{ count }}</span>
    <button @click="increment">+</button>
  </div>
</template>

<style scoped lang="less">
.counter { display: flex; gap: 8px; }
button { cursor: pointer; }
</style>

<script>
export default {
  data() {
    return { count: 0 }
  },
  methods: {
    increment() { this.count++ }
  }
}
</script>
```

---

## Build mode 1 — HTML file

All components are injected into a single `index.html` produced from your `template.html`.

**template.html:**
```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
  <style><|style|></style>
</head>
<body>
  <div id="app">
    <counter />
  </div>

  <|templates|>

  <script>
    <|variables|>
    const app = Vue.createApp({});
    <|components|>
    app.mount('#app');
  </script>
</body>
</html>
```

Templates are stored as `<template id="...">` tags and referenced by selector from `app.component()`.

**Python:**
```python
from vue_collector import prepare_compiled

with open('template.html') as f:
    html = prepare_compiled(f.read(), vue_dir='vue/')

with open('index.html', 'w') as f:
    f.write(html)
```

**Project layout for this mode:**
```
project/
├── template.html       # your HTML skeleton with <|placeholders|>
├── index.html          # generated output
└── vue/
    ├── Counter.vue
    └── Card.vue
```

---

## Build mode 2 — Standalone JS + CSS assets

Components are compiled into two files named by a content hash, so filenames change automatically whenever any `.vue` file changes (safe for long-term browser caching).

Templates are **inlined** as backtick strings inside `app.component()` — no `<template id>` tags needed. The JS file exports a single `initComponents(app)` function.

**Python:**
```python
from vue_collector import write_assets

js_file, css_file = write_assets(
    vue_dir='vue/',      # directory containing .vue files
    output_dir='static', # writes files here
    extra_js='',         # optional JS prepended verbatim (e.g. app init code)
)
# js_file  → 'components.a3f9c1d2e4b5f678.js'
# css_file → 'components.a3f9c1d2e4b5f678.css'
```

Or in-memory:
```python
from vue_collector import prepare_assets

js_content, css_content = prepare_assets(vue_dir='vue/')
```

**Generated JS structure:**
```javascript
// extra_js content goes here (if provided)

// module-level constants (code outside export default in .vue scripts)
const PAGE_SIZE = 10

function initComponents(app) {
    app.component('Counter', {template: `
  <div class="counter">
    <span>{{ count }}</span>
    <button @click="increment">+</button>
  </div>
`,
data() { return { count: 0 } },
methods: { increment() { this.count++ } }});
}
```

**HTML page using generated assets:**
```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
  <link rel="stylesheet" href="/static/components.a3f9c1d2e4b5f678.css">
</head>
<body>
  <div id="app">
    <counter />
  </div>
  <script src="/static/components.a3f9c1d2e4b5f678.js"></script>
  <script>
    const app = Vue.createApp({});
    initComponents(app);
    app.mount('#app');
  </script>
</body>
</html>
```

**Project layout for this mode:**
```
project/
├── static/
│   ├── components.a3f9c1d2e4b5f678.js    # generated
│   └── components.a3f9c1d2e4b5f678.css   # generated
└── vue/
    ├── Counter.vue
    └── Card.vue
```

---

## Flask integration example

```python
from flask import Flask, render_template_string
from vue_collector import write_assets, VueSectionError

app = Flask(__name__)

try:
    js_file, css_file = write_assets(vue_dir='vue/', output_dir='static')
except VueSectionError as e:
    print(f'Component error: {e}')
    raise

PAGE = """
<!DOCTYPE html>
<html>
<head>
  <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
  <link rel="stylesheet" href="/static/{{ css }}">
</head>
<body>
  <div id="app"><my-counter /></div>
  <script src="/static/{{ js }}"></script>
  <script>
    const app = Vue.createApp({});
    initComponents(app);
    app.mount('#app');
  </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(PAGE, js=js_file, css=css_file)
```

### Auto-reload with watchdog

`find_vue_files` is useful for watching `.vue` files with a file watcher:

```python
from vue_collector import find_vue_files, write_assets

# Get all .vue paths to pass to your watchdog observer
paths_to_watch = find_vue_files('vue/')
```

---

## Multiple source directories

All functions that accept `vue_dir` also accept a list of directories. This enables shared component libraries across builds:

```
project/
├── shared/           # components used by all builds
│   ├── Button.vue
│   └── Card.vue
├── admin/            # admin-only components
│   └── UserTable.vue
└── static/
```

```python
from vue_collector import write_assets

# Public build — shared components only
js, css = write_assets(vue_dir='shared/', output_dir='static')

# Admin build — shared + admin components
js, css = write_assets(vue_dir=['shared/', 'admin/'], output_dir='static')
```

**Name conflicts — last directory wins.** If two directories contain a component with the same name, the last directory in the list takes priority:

```
shared/Button.vue   ← base version
admin/Button.vue    ← overrides shared version in admin build
```

```python
# admin/Button.vue is used; shared/Button.vue is ignored for this build
js, css = write_assets(vue_dir=['shared/', 'admin/'], output_dir='static')
```

---

## Low-level API

```python
from vue_collector import VueComponent, collect_vue, VueSectionError

# Parse a single component
with open('vue/Counter.vue') as f:
    vc = VueComponent('Counter.vue', f.read())

print(vc.name)          # 'Counter'
print(vc.style)         # '.counter{display:flex;gap:8px;}'
print(vc.raw_template)  # '<div class="counter">...</div>'  (for JS inline use)
print(vc.template)      # '<template id="template-counter">...</template>'  (for HTML mode)

# Iterate all components in a directory — yields VueComponent objects
for component in collect_vue('vue/'):
    print(component.name, component.style)

# Errors always come as VueSectionError
try:
    VueComponent('Bad.vue', '<template><div></template>')
except VueSectionError as e:
    print(e.file_name)  # 'Bad.vue'
    print(e.section)    # None (structural error), or 'script' / 'style'
    print(e.message)    # human-readable description
```

---

## Installation

```bash
pip install vue-collector
```

---

## CLI

### `vue-collector format <dir>`

Format all `.vue` files in a directory in-place. Sections are reordered to `<template>` → `<style>` → `<script>`, each property/tag gets its own indented line, and trailing whitespace is removed.

```bash
vue-collector format path/to/components/

# via uv:
uv run vue-collector format path/to/components/

# via Python module:
python -m vue_collector format path/to/components/
```

Files already correctly formatted are left untouched (idempotent).

**Note:** The formatter is intentionally simple. It applies a small fixed set of rules — consistent section order, basic indentation, no trailing whitespace — with no configuration and no understanding of JavaScript or CSS semantics beyond what is needed for that. It is not a substitute for Prettier or ESLint: it won't reformat complex expressions, enforce style preferences, or catch logic issues. For a project that has graduated to a Node-based toolchain, use Prettier with the Vue plugin instead.

---

## Limitations

| Feature | Status |
|---|---|
| LESS compilation | Supported — `<style lang="less">` required |
| `<style scoped>` | Supported |
| Vue directives (`v-for`, `v-if`, `@click`, `:bind`) | Pass-through (not validated) |
| Named slots (`<template #slot>`) | Supported |
| Multiple root elements (Vue 3 fragments) | Supported |
| `export default {}` as component definition | Supported (only supported form) |
| `import` in `<script>` | Silently stripped |
| `components: {}` in `export default` | Silently stripped |
| `name` in `export default` | Silently stripped |
| `defineComponent()` / `<script setup>` | Not supported |
| `@import` in `<style>` | Not supported |
| TypeScript | Not supported |
| SCSS / Sass / Stylus | Not supported |
| CSS Modules | Not supported |

## License

MIT
