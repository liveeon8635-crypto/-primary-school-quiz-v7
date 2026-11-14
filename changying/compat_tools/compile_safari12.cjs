/* Offline only. npm install --prefix /tmp/ios12-build --no-audit --no-fund
 * @babel/core@7.28.5 @babel/preset-env@7.28.5 acorn@8.15.0
 */
const fs=require('fs'),path=require('path'),zlib=require('zlib');
const modules=path.resolve(process.argv[2]),babel=require(path.join(modules,'@babel/core')),
 preset=require(path.join(modules,'@babel/preset-env')),acorn=require(path.join(modules,'acorn'));
if(babel.version!=='7.28.5')throw Error('Use the pinned Babel 7.28.5 compiler');
const input=JSON.parse(fs.readFileSync(0,'utf8')),out=path.join(__dirname,'../web/safari12_assets');
const manifest={compiler:'@babel/core 7.28.5 / @babel/preset-env 7.28.5; target iOS 12',routes:input.routes,scripts:{}};
const scripts={};
for(const [key,source] of Object.entries(input.scripts)){
 let unchanged=true;try{acorn.parse(source,{ecmaVersion:2019,allowReturnOutsideFunction:false})}catch{unchanged=false}
 let code=source;
 if(!unchanged){code=babel.transformSync(source,{presets:[[preset,{targets:{ios:'12'},modules:false,bugfixes:true,useBuiltIns:false}]],sourceType:'script',comments:false,compact:true,babelrc:false,configFile:false}).code;
 acorn.parse(code,{ecmaVersion:2019});fs.writeFileSync(path.join(out,key+'.js.gz.b64'),zlib.gzipSync(code,{level:9,mtime:0}).toString('base64')+'\n');}
 if(/\(\?<([=!])/.test(code))throw Error('Untranslated regexp lookbehind in '+key);
 scripts[key]={unchanged,sourceBytes:Buffer.byteLength(source),compiledBytes:Buffer.byteLength(code)};
}
// Sort by script hash so a rebuild on another host or in another process writes a
// byte-identical manifest instead of a reordering-only diff.
for(const key of Object.keys(scripts).sort())manifest.scripts[key]=scripts[key];
fs.writeFileSync(path.join(out,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({routes:Object.keys(input.routes).length,scripts:Object.keys(input.scripts).length,compiled:Object.values(manifest.scripts).filter(s=>!s.unchanged).length}));
