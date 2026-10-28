// Load src components in Node with the existing Vite JSX compiler and no server.
// Relative imports are resolved recursively: .jsx files are compiled, .js
// modules are imported from disk so tests share the same module instances.
import { readFile } from 'node:fs/promises'
import { transformWithOxc } from 'vite'

const REACT = JSON.stringify(import.meta.resolve('react'))
const compiled = new Map()

async function moduleUrl(file) {
  if (file.endsWith('.js')) return new URL(`../src/${file}`, import.meta.url).href
  if (compiled.has(file)) return compiled.get(file)
  const source = await readFile(new URL(`../src/${file}`, import.meta.url), 'utf8')
  const { code } = await transformWithOxc(source, file, { jsx: { runtime: 'classic' } })
  let output = code.replace(/(['"])react\1/g, REACT)
  for (const [, quote, target] of [...output.matchAll(/from\s+(['"])\.\/([\w.]+)\1/g)]) {
    const url = await moduleUrl(/\.(jsx?|css)$/.test(target) ? target : `${target}.jsx`)
    output = output.replaceAll(`${quote}./${target}${quote}`, JSON.stringify(url))
  }
  const url = `data:text/javascript;base64,${Buffer.from(output).toString('base64')}`
  compiled.set(file, url)
  return url
}

export async function loadComponent(name) {
  return import(await moduleUrl(`${name}.jsx`))
}
