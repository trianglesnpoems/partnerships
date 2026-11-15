#!/usr/bin/env node
// Cut world-atlas countries down to the ones a North America hub map shows, as a small TopoJSON file.
// Usage: node prune_countries.js <world-atlas/countries-50m.json> <out.json>   (needs topojson-client and topojson-server)
const fs = require('fs'), path = require('path');
const libs = process.env.TRI_LIBS || path.join(process.cwd(), 'node_modules');
const tc = require(path.join(libs, 'topojson-client')), ts = require(path.join(libs, 'topojson-server'));
const [src, out] = process.argv.slice(2);
const KEEP = new Set(['United States of America', 'Canada', 'Mexico', 'Cuba', 'Bahamas', 'Guatemala', 'Belize', 'Greenland', 'Dominican Rep.', 'Haiti', 'Jamaica', 'Puerto Rico', 'Honduras', 'El Salvador']);
const world = JSON.parse(fs.readFileSync(src, 'utf8'));
const fc = tc.feature(world, world.objects.countries);
const kept = fc.features.filter(f => KEEP.has(f.properties.name));
const topo = ts.topology({ countries: { type: 'FeatureCollection', features: kept } }, 1e5);
fs.writeFileSync(out, JSON.stringify(topo));
console.log(`kept ${kept.length} of ${fc.features.length} countries: ${kept.map(f => f.properties.name).join(', ')} -> ${(fs.statSync(out).size / 1024).toFixed(0)} KB`);
